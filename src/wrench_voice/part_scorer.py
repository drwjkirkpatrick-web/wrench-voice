"""
part_scorer.py
==============
Score parts on price, quality, brand reputation, warranty, and delivery speed.

WHY:
The cheapest part isn't always the best value. A $12 water pump that fails
in 6 months costs more than a $45 OEM pump that lasts 5 years. This module
builds a quality score per brand/SKU from:
- Return rates (tracked in our system)
- Price vs. warranty length ratio
- Brand reputation (static knowledge + learned returns)
- Delivery speed consistency

SCORING:
    score = (warranty_score * 0.25) + (return_penalty * -0.35) + (price_value * 0.20) + (delivery_score * 0.20)
    Normalized to 0–100.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class PartScorer:
    """
    Quality and value scoring for parts.

    Usage:
        scorer = PartScorer()
        result = scorer.score("water_pump_22RE", supplier="RockAuto", brand="AISIN", price=45.0, warranty_years=2)
        # result = {"score": 78, "tier": "good", "concerns": [], "recommendation": "Solid choice."}
    """

    # Static brand reputation base scores (0-100)
    BRAND_REPUTATION: dict[str, float] = {
        "OEM / Toyota": 95.0,
        "OEM / Honda": 95.0,
        "OEM / Ford": 90.0,
        "AISIN": 88.0,
        "NGK": 92.0,
        "Denso": 90.0,
        "Bosch": 85.0,
        "Gates": 82.0,
        "Dayco": 78.0,
        "Continental": 80.0,
        "Koyo": 75.0,
        "Timken": 85.0,
        "SKF": 87.0,
        "Febi Bilstein": 72.0,
        "URO Parts": 55.0,
        "Dorman": 65.0,
        "Motorcraft": 82.0,
        "ACDelco": 75.0,
        "Mopar": 80.0,
        "Beck/Arnley": 60.0,
        "Standard": 58.0,
        "Pep Boys": 45.0,
        "Unknown / No Brand": 30.0,
    }

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS part_returns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT,
                    supplier TEXT,
                    brand TEXT,
                    reason TEXT,
                    replaced_under_warranty INTEGER,
                    recorded_at TEXT
                )
            """)

    def score(
        self,
        sku: str,
        supplier: str,
        brand: str,
        price: float,
        warranty_years: float = 1.0,
        part_category: str = "general",
    ) -> dict[str, Any]:
        """
        Compute a quality/value score for a part.
        """
        # Brand reputation (static + learned)
        base_rep = self.BRAND_REPUTATION.get(brand, 50.0)
        learned_return_rate = self._return_rate(sku, brand)
        adjusted_rep = base_rep * (1 - learned_return_rate * 2)

        # Warranty score (0–100 based on years)
        warranty_score = min(warranty_years * 40, 100)  # 2.5 years = 100

        # Price value (cheaper isn't always better — use price vs. median for category)
        price_value = self._price_value_score(price, part_category)

        # Delivery score (placeholder — would integrate with delivery_predictor)
        delivery_score = 70.0  # Neutral baseline

        # Composite score
        score = (
            adjusted_rep * 0.30 +
            warranty_score * 0.25 +
            price_value * 0.25 +
            delivery_score * 0.20
        )
        score = max(0, min(100, score))

        # Tier and concerns
        tier = "excellent" if score >= 85 else "good" if score >= 70 else "fair" if score >= 50 else "poor"
        concerns: list[str] = []
        if learned_return_rate > 0.10:
            concerns.append(f"High return rate: {learned_return_rate*100:.0f}%")
        if warranty_years < 1:
            concerns.append("Short warranty")
        if price < 15 and part_category in ("water_pump", "timing_belt", "head_gasket"):
            concerns.append("Suspiciously cheap for critical component")
        if brand not in self.BRAND_REPUTATION:
            concerns.append("Unknown brand — limited reliability data")

        rec = {
            "excellent": "Best-in-class. Buy with confidence.",
            "good": "Reliable choice. Good value.",
            "fair": "Acceptable for budget repairs. Monitor closely.",
            "poor": "Avoid. High failure risk or poor value.",
        }[tier]

        return {
            "sku": sku,
            "brand": brand,
            "supplier": supplier,
            "price": price,
            "score": round(score, 1),
            "tier": tier,
            "adjusted_reputation": round(adjusted_rep, 1),
            "warranty_score": round(warranty_score, 1),
            "price_value": round(price_value, 1),
            "delivery_score": round(delivery_score, 1),
            "return_rate": round(learned_return_rate, 3),
            "concerns": concerns,
            "recommendation": rec,
        }

    def _return_rate(self, sku: str, brand: str) -> float:
        """Fraction of this SKU+brand that was returned."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM part_returns WHERE sku=? AND brand=?", (sku, brand)
            ).fetchone()[0]
            if total < 3:
                return 0.0  # Insufficient data
            returns = conn.execute(
                "SELECT COUNT(*) FROM part_returns WHERE sku=? AND brand=?", (sku, brand)
            ).fetchone()[0]
        return returns / total

    def _price_value_score(self, price: float, category: str) -> float:
        """Simple heuristic: very cheap = suspicious, very expensive = poor value."""
        # Category medians (rough industry averages)
        medians = {
            "brake_pads": 45.0, "water_pump": 55.0, "timing_belt_kit": 85.0,
            "head_gasket": 45.0, "ignition_coil": 35.0, "spark_plugs": 6.0,
            "oxygen_sensor": 65.0, "fuel_pump": 90.0, "alternator": 120.0,
            "starter": 110.0, "general": 40.0,
        }
        med = medians.get(category, 40.0)
        if price <= med * 0.3:
            return 20.0  # Too cheap
        if price <= med * 0.7:
            return 65.0
        if price <= med * 1.3:
            return 90.0  # Sweet spot
        if price <= med * 2.0:
            return 70.0
        return 40.0  # Overpriced

    def record_return(self, sku: str, supplier: str, brand: str, reason: str, warranty: bool = False) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO part_returns (sku, supplier, brand, reason, replaced_under_warranty, recorded_at) VALUES (?,?,?,?,?,?)",
                (sku, supplier, brand, reason, int(warranty), now),
            )

    def brand_rankings(self) -> list[dict[str, Any]]:
        """Static brand reputation table for quick reference."""
        return [
            {"brand": b, "base_score": s, "tier": "premium" if s >= 85 else "mid" if s >= 65 else "budget"}
            for b, s in sorted(self.BRAND_REPUTATION.items(), key=lambda x: -x[1])
        ]
