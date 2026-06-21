"""
parts_finder.py
===============
Look up parts across suppliers — with caching.

WHY:
Mechanics need prices FAST while on a lift. No time to browse 4 tabs.
We aggregate from:
- RockAuto (scraped)
- Amazon (placeholder / simulated — real scraping needs auth)
- Local inventory CSV (user-maintained)

HOW:
1. Try local inventory first (cheapest, fastest)
2. Check cache (SQLite TTL 24h)
3. Hit web sources (RockAuto scrape via httpx + beautifulsoup)
4. Cache results, return ranked list

MOCK MODE:
If no internet or --simulate, return realistic simulated prices so
the mechanic still gets a workflow demonstration.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# NOTE: We import heavy deps inside methods so the module can be imported
# without them being installed. This keeps the test environment happy.


@dataclass
class PartResult:
    """One part offer from one supplier."""
    supplier: str
    part_number: str
    part_name: str
    price: float
    availability: str     # "In stock", "Ships in 2 days", etc.
    url: str | None
    shipping_days: int
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "supplier": self.supplier,
            "part_number": self.part_number,
            "part_name": self.part_name,
            "price": self.price,
            "availability": self.availability,
            "url": self.url,
            "shipping_days": self.shipping_days,
            "notes": self.notes,
        }


class PartsFinder:
    """
    Part lookup with caching and tiered suppliers.

    Usage:
        finder = PartsFinder()
        results = finder.lookup("thermostat", make="Toyota", year=1996)
        for r in results:
            print(f"{r.supplier}: {r.part_name} — ${r.price}")
    """

    def __init__(self, mock_mode: bool = False) -> None:
        self.mock_mode = mock_mode
        self._cache = _PartCache()

    def lookup(
        self,
        part_name: str,
        make: str | None = None,
        year: int | None = None,
        engine: str | None = None,
    ) -> list[PartResult]:
        """
        Search for a part across all configured suppliers.

        Returns list of PartResult, cheapest first.
        """
        results: list[PartResult] = []

        # Build cache key
        key = self._cache_key(part_name, make, year, engine)

        # 1. Check cache
        cached = self._cache.get(key)
        if cached:
            return [PartResult(**d) for d in cached]

        # 2. Local inventory CSV
        local = self._search_local_inventory(part_name, make, year, engine)
        results.extend(local)

        if not self.mock_mode:
            # 3. RockAuto
            try:
                rockauto = self._search_rockauto(part_name, make, year, engine)
                results.extend(rockauto)
            except Exception as e:
                # Silently degrade — mechanic on a lift doesn't care about 403s
                pass

            # 4. Amazon (placeholder — would need proper auth + API)
            # amazon = self._search_amazon(...)
            # results.extend(amazon)
        else:
            # Mock mode: inject realistic simulated results
            results.extend(self._mock_results(part_name))

        # Sort by price
        results.sort(key=lambda r: r.price)

        # Cache the serialized result
        self._cache.put(key, [r.to_dict() for r in results])

        return results

    # ─── Suppliers ─────────────────────────────────────────────────────────────

    def _search_local_inventory(
        self,
        part_name: str,
        make: str | None,
        year: int | None,
        engine: str | None,
    ) -> list[PartResult]:
        """
        Search a local CSV file for parts.
        
        CSV format expected:
        part_name,part_number,make,year,engine,price,qty,location
        """
        results: list[PartResult] = []

        inv_path = Path.home() / ".config" / "wrench-voice" / "inventory.csv"
        if not inv_path.exists():
            return results

        try:
            import csv
            with inv_path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Fuzzy match on part name
                    if part_name.lower() not in row.get("part_name", "").lower():
                        continue
                    # Filter by make/year if provided
                    if make and make.lower() not in row.get("make", "").lower():
                        continue
                    if year and str(year) not in str(row.get("year", "")):
                        continue

                    results.append(
                        PartResult(
                            supplier="Local Inventory",
                            part_number=row.get("part_number", "N/A"),
                            part_name=row.get("part_name", "Unknown"),
                            price=float(row.get("price", 0)),
                            availability=f"Qty: {row.get('qty', '?')} @ {row.get('location', '?')}",
                            url=None,
                            shipping_days=0,
                            notes="On shelf",
                        )
                    )
        except Exception:
            # Malformed CSV? Skip it. We're on a lift — no time to debug.
            pass

        return results

    def _search_rockauto(
        self,
        part_name: str,
        make: str | None,
        year: int | None,
        engine: str | None,
    ) -> list[PartResult]:
        """
        Scrape RockAuto search results.

        NOTE: This is fragile — RockAuto may change their HTML.
        We handle 403/404 gracefully and fall through.
        """
        import httpx
        from bs4 import BeautifulSoup

        results: list[PartResult] = []

        query = f"{part_name} {make or ''} {year or ''}".strip().replace(" ", "+")
        url = f"https://www.rockauto.com/en/catalog/{make.lower()}" if make else "https://www.rockauto.com"

        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux aarch64) "
                        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                    ),
                })
                if resp.status_code >= 400:
                    return results

                soup = BeautifulSoup(resp.text, "html.parser")
                # RockAuto listings vary — this is a best-effort pattern
                for item in soup.select(".listing")[:5]:
                    try:
                        name_tag = item.select_one(".listing-name, .ra-txt")
                        price_tag = item.select_one(".listing-price, .ra-price")
                        number_tag = item.select_one(".listing-part, .ra-part")

                        if name_tag and price_tag:
                            price_str = price_tag.get_text(strip=True).replace("$", "").replace(",", "")
                            price = float(price_str) if price_str.replace(".", "").isdigit() else 0.0
                            results.append(
                                PartResult(
                                    supplier="RockAuto",
                                    part_number=number_tag.get_text(strip=True) if number_tag else "N/A",
                                    part_name=name_tag.get_text(strip=True),
                                    price=price,
                                    availability="Ships in 1–3 days",
                                    url=resp.url,
                                    shipping_days=3,
                                )
                            )
                    except Exception:
                        continue

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException):
            # Network issue? Return empty and let other suppliers fill the gap.
            pass

        return results

    def _mock_results(self, part_name: str) -> list[PartResult]:
        """
        Simulated results when we're in mock mode or offline.
        Realistic enough to demonstrate the workflow.
        """
        # A small price table for common parts
        base_prices: dict[str, float] = {
            "thermostat": 12.99,
            "oil filter": 6.49,
            "spark plug": 4.99,
            "head gasket": 49.99,
            "water pump": 67.00,
            "alternator": 129.99,
            "brake pads": 34.99,
            "serpentine belt": 28.50,
            "ignition coil": 38.99,
            "fuel pump": 89.99,
            "timing belt kit": 145.00,
            "motor mount": 24.99,
            "oxygen sensor": 52.00,
            "radiator fan": 75.00,
        }

        # Find closest match
        price = base_prices.get(part_name.lower())
        if price is None:
            # Fuzzy fallback: match any containing word
            for key, val in base_prices.items():
                if key in part_name.lower() or part_name.lower() in key:
                    price = val
                    break
            if price is None:
                price = 25.00  # Generic placeholder

        part_display = part_name.title()

        return [
            PartResult(
                supplier="Simulated-RockAuto",
                part_number=f"RK-{part_name.upper()[:3]}-001",
                part_name=f"{part_display} (Aftermarket)",
                price=round(price * 0.9, 2),
                availability="Ships in 2 days",
                url=None,
                shipping_days=2,
                notes="Simulated — connect to real supplier for live prices",
            ),
            PartResult(
                supplier="Simulated-OReilly",
                part_number=f"ORL-{part_name.upper()[:3]}-002",
                part_name=f"{part_display} (Premium)",
                price=round(price * 1.1, 2),
                availability="In stock",
                url=None,
                shipping_days=1,
                notes="Simulated",
            ),
            PartResult(
                supplier="Simulated-Advance",
                part_number=f"ADV-{part_name.upper()[:3]}-003",
                part_name=f"{part_display} (Value)",
                price=round(price * 0.85, 2),
                availability="Ships in 3 days",
                url=None,
                shipping_days=3,
                notes="Simulated",
            ),
        ]

    # ─── Cache ───────────────────────────────────────────────────────────────────

    def _cache_key(self, part_name: str, make: str | None, year: int | None, engine: str | None) -> str:
        raw = f"{part_name}|{make}|{year}|{engine}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class _PartCache:
    """
    SQLite cache for parts lookup results.
    TTL: 24 hours (86400 seconds).
    """

    TTL_SECONDS = 86400

    def __init__(self) -> None:
        self._db_path = self._get_db_path()
        self._init_table()

    @staticmethod
    def _get_db_path() -> Path:
        env = os.environ.get("WRENCH_CACHE_DIR")
        if env:
            return Path(env) / "parts-cache.db"
        return Path.home() / ".cache" / "wrench-voice" / "parts-cache.db"

    def _connection(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self._db_path)

    def _init_table(self) -> None:
        with self._connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS parts_cache ("
                "  key TEXT PRIMARY KEY,"
                "  data TEXT,"
                "  created INTEGER"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created ON parts_cache(created)"
            )
            conn.commit()

    def get(self, key: str) -> list[dict[str, Any]] | None:
        import time
        with self._connection() as conn:
            row = conn.execute(
                "SELECT data, created FROM parts_cache WHERE key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            data, created = row
            if int(time.time()) - created > self.TTL_SECONDS:
                # Expired — delete and return None
                conn.execute("DELETE FROM parts_cache WHERE key = ?", (key,))
                conn.commit()
                return None
            return json.loads(data)

    def put(self, key: str, data: list[dict[str, Any]]) -> None:
        import time
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO parts_cache (key, data, created) VALUES (?, ?, ?)",
                (key, json.dumps(data), int(time.time())),
            )
            conn.commit()
