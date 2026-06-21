"""
price_tracker.py
================
Historical part price tracking, trend analysis, and sale detection.

WHY:
A mechanic shop buys thousands of dollars in parts monthly. Knowing whether
a "sale" is real or fake saves real money. Tracking 90-day price history
reveals supplier pricing patterns.

FEATURES:
- Records every price observation: supplier, part, price, date
- Trend detection: rising, falling, stable
- Sale validation: current vs. 90-day average
- Supplier volatility score (how often prices change)
- Alert thresholds: "notify when X drops below $Y"

DB SCHEMA:
    price_observations: sku, supplier, price, currency, observed_at
    price_alerts: alert_id, sku, supplier, condition, threshold, active
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, stdev
from typing import Any


@dataclass
class PriceObservation:
    sku: str
    supplier: str
    price: float
    currency: str
    part_name: str
    observed_at: str


@dataclass
class PriceTrend:
    sku: str
    supplier: str
    current_price: float
    avg_30d: float
    avg_90d: float
    min_90d: float
    max_90d: float
    trend: str  # "rising" | "falling" | "stable"
    sale_detected: bool  # current is at least 15% below 90d avg
    volatility: float   # coefficient of variation (std/mean)


class PriceTracker:
    """
    Track part prices over time and detect trends.

    Usage:
        tracker = PriceTracker()
        tracker.record("NGK-BKR7E", "RockAuto", 6.99, "spark plug")
        trend = tracker.trend("NGK-BKR7E", "RockAuto")
        alerts = tracker.check_alerts()
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS price_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT,
                    supplier TEXT,
                    price REAL,
                    currency TEXT DEFAULT 'USD',
                    part_name TEXT,
                    observed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_price_sku ON price_observations(sku, supplier);
                CREATE INDEX IF NOT EXISTS idx_price_date ON price_observations(observed_at);

                CREATE TABLE IF NOT EXISTS price_alerts (
                    alert_id TEXT PRIMARY KEY,
                    sku TEXT,
                    supplier TEXT,
                    condition TEXT,  -- 'below' | 'above' | 'any_sale'
                    threshold REAL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
            """)

    def record(self, sku: str, supplier: str, price: float, part_name: str = "", currency: str = "USD") -> None:
        """Log a price observation. Call after every parts lookup or receipt."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO price_observations (sku, supplier, price, currency, part_name, observed_at) VALUES (?,?,?,?,?,?)",
                (sku, supplier, price, currency, part_name, now),
            )

    def trend(self, sku: str, supplier: str | None = None) -> PriceTrend | None:
        """
        Compute price trend for a SKU. If supplier is None, aggregates all suppliers.
        """
        sql = """SELECT price FROM price_observations
                 WHERE sku=? {} AND observed_at > datetime('now', '-90 days')
                 ORDER BY observed_at""".format("AND supplier=?" if supplier else "")
        params = (sku, supplier) if supplier else (sku,)

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        if len(rows) < 2:
            return None

        prices = [r[0] for r in rows]
        avg_90 = mean(prices)
        current = prices[-1]

        # 30-day subset
        recent = prices[-min(len(prices), 10):]
        avg_30 = mean(recent)

        vol = stdev(prices) / avg_90 if avg_90 > 0 else 0.0

        if avg_90 == 0:
            trend = "stable"
        elif current < avg_90 * 0.90:
            trend = "falling"
        elif current > avg_90 * 1.10:
            trend = "rising"
        else:
            trend = "stable"

        sale = current <= avg_90 * 0.85

        return PriceTrend(
            sku=sku,
            supplier=supplier or "all",
            current_price=round(current, 2),
            avg_30d=round(avg_30, 2),
            avg_90d=round(avg_90, 2),
            min_90d=round(min(prices), 2),
            max_90d=round(max(prices), 2),
            trend=trend,
            sale_detected=sale,
            volatility=round(vol, 3),
        )

    def compare_suppliers(self, sku: str) -> list[dict[str, Any]]:
        """Return all supplier trends for a SKU side-by-side."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT supplier FROM price_observations WHERE sku=?",
                (sku,),
            ).fetchall()
        out = []
        for (supplier,) in rows:
            t = self.trend(sku, supplier)
            if t:
                out.append({
                    "supplier": t.supplier,
                    "current": t.current_price,
                    "avg_30d": t.avg_30d,
                    "trend": t.trend,
                    "sale": t.sale_detected,
                })
        return sorted(out, key=lambda x: x["current"])

    def add_alert(self, sku: str, supplier: str | None, condition: str, threshold: float | None) -> str:
        alert_id = f"ALERT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO price_alerts (alert_id, sku, supplier, condition, threshold, created_at) VALUES (?,?,?,?,?,?)",
                (alert_id, sku, supplier, condition, threshold, now),
            )
        return alert_id

    def check_alerts(self) -> list[dict[str, Any]]:
        """Return all triggered alerts."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT alert_id, sku, supplier, condition, threshold FROM price_alerts WHERE active=1"
            ).fetchall()

        triggered = []
        for aid, sku, supplier, cond, thresh in rows:
            t = self.trend(sku, supplier)
            if not t:
                continue
            if cond == "below" and thresh and t.current_price <= thresh:
                triggered.append({"alert_id": aid, "sku": sku, "current": t.current_price, "threshold": thresh})
            elif cond == "above" and thresh and t.current_price >= thresh:
                triggered.append({"alert_id": aid, "sku": sku, "current": t.current_price, "threshold": thresh})
            elif cond == "any_sale" and t.sale_detected:
                triggered.append({"alert_id": aid, "sku": sku, "current": t.current_price, "reason": "Sale detected"})
        return triggered

    def purge_old(self, days: int = 365) -> int:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.execute(
                "DELETE FROM price_observations WHERE observed_at < datetime('now', '-{} days')".format(days)
            )
            return c.rowcount
