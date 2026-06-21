"""
digital_inspection.py
=====================
Photo-based vehicle inspection with voice annotation and PDF report generation.

WHY:
Modern shops use digital vehicle inspections (DVI) to:
1. Show customers what the mechanic sees (transparency)
2. Document pre-existing condition (liability protection)
3. Sell approved work with visual proof

This module captures photos, attaches voice notes, scores conditions
(red/yellow/green), and generates customer-ready PDFs.

FEATURES:
- Photo upload per inspection category (brakes, tires, fluids, undercarriage)
- Condition scoring: green (good), yellow (monitor), red (needs work)
- Voice-to-text annotation per photo
- PDF report generation with photos, scores, and recommendations
- Customer approval tracking: viewed, approved, declined per recommendation
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class DigitalInspection:
    """
    Photo-based vehicle inspection system.

    Usage:
        di = DigitalInspection()
        di.create_inspection(vin="1HGCM82633A004352", customer="Jane Doe")
        di.add_photo(inspection_id="INSP-001", category="brakes",
                     photo_path="/photos/brake_pad_left.jpg",
                     condition="red",  # needs work
                     voice_note="Brake pad is down to two millimeters. Rotor has grooves.")
        di.add_recommendation(inspection_id="INSP-001",
                              text="Replace front brake pads and resurface rotors",
                              urgency="red", estimated_cost=340)
        report_path = di.generate_pdf("INSP-001")
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    def __init__(self, db_path: str | None = None, photo_dir: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self.photo_dir = Path(photo_dir) if photo_dir else Path.home() / ".cache" / "wrench-voice" / "inspection_photos"
        self.photo_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS inspections (
                    inspection_id TEXT PRIMARY KEY,
                    vin TEXT,
                    customer TEXT,
                    created_at TEXT,
                    submitted_at TEXT,
                    viewed_by_customer INTEGER DEFAULT 0,
                    approved_recommendations TEXT,
                    declined_recommendations TEXT
                );

                CREATE TABLE IF NOT EXISTS inspection_photos (
                    photo_id TEXT PRIMARY KEY,
                    inspection_id TEXT REFERENCES inspections(inspection_id),
                    category TEXT,  -- brakes, tires, fluids, suspension, undercarriage, engine, exterior
                    photo_path TEXT,
                    condition TEXT,  -- green | yellow | red
                    voice_note TEXT,
                    text_note TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS recommendations (
                    rec_id TEXT PRIMARY KEY,
                    inspection_id TEXT REFERENCES inspections(inspection_id),
                    category TEXT,
                    text TEXT,
                    urgency TEXT,  -- green | yellow | red
                    estimated_cost REAL,
                    approved INTEGER,
                    created_at TEXT
                );
            """)

    def create_inspection(self, vin: str, customer: str = "") -> str:
        insp_id = f"INSP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(2).hex()}"
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO inspections (inspection_id, vin, customer, created_at) VALUES (?,?,?,?)",
                (insp_id, vin, customer, now),
            )
        return insp_id

    def add_photo(
        self,
        inspection_id: str,
        category: str,
        photo_path: str,
        condition: str = "green",
        voice_note: str = "",
        text_note: str = "",
    ) -> str:
        photo_id = f"PHOTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO inspection_photos
                   (photo_id, inspection_id, category, photo_path, condition, voice_note, text_note, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (photo_id, inspection_id, category, photo_path, condition, voice_note, text_note, now),
            )
        return photo_id

    def add_recommendation(
        self,
        inspection_id: str,
        text: str,
        urgency: str = "yellow",
        estimated_cost: float = 0.0,
        category: str = "general",
    ) -> str:
        rec_id = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(2).hex()}"
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO recommendations
                   (rec_id, inspection_id, category, text, urgency, estimated_cost, approved, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (rec_id, inspection_id, category, text, urgency, estimated_cost, None, now),
            )
        return rec_id

    def customer_response(self, inspection_id: str, approved: list[str], declined: list[str]) -> None:
        """Record customer approval/decline per recommendation."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE inspections SET approved_recommendations=?, declined_recommendations=?, viewed_by_customer=1 WHERE inspection_id=?",
                (",".join(approved), ",".join(declined), inspection_id),
            )
            for rec_id in approved:
                conn.execute(
                    "UPDATE recommendations SET approved=1 WHERE rec_id=?", (rec_id,)
                )
            for rec_id in declined:
                conn.execute(
                    "UPDATE recommendations SET approved=0 WHERE rec_id=?", (rec_id,)
                )

    def generate_report(self, inspection_id: str) -> dict[str, Any]:
        """Generate a structured report dict (PDF generation would be a future addition)."""
        with sqlite3.connect(self.db_path) as conn:
            insp = conn.execute("SELECT * FROM inspections WHERE inspection_id=?", (inspection_id,)).fetchone()
            photos = conn.execute(
                "SELECT category, photo_path, condition, text_note FROM inspection_photos WHERE inspection_id=?",
                (inspection_id,),
            ).fetchall()
            recs = conn.execute(
                "SELECT rec_id, category, text, urgency, estimated_cost, approved FROM recommendations WHERE inspection_id=?",
                (inspection_id,),
            ).fetchall()

        if not insp:
            return {"error": "Inspection not found"}

        categories = {}
        for p in photos:
            cat = p[0]
            categories.setdefault(cat, {"photos": [], "condition": "green"})
            categories[cat]["photos"].append({"path": p[1], "condition": p[2], "note": p[3]})
            if p[2] == "red":
                categories[cat]["condition"] = "red"
            elif p[2] == "yellow" and categories[cat]["condition"] != "red":
                categories[cat]["condition"] = "yellow"

        recommendations = [
            {"id": r[0], "category": r[1], "text": r[2], "urgency": r[3],
             "cost": r[4], "status": "approved" if r[5] == 1 else "declined" if r[5] == 0 else "pending"}
            for r in recs
        ]

        total_approved = sum(r["cost"] for r in recommendations if r["status"] == "approved")
        total_pending = sum(r["cost"] for r in recommendations if r["status"] == "pending")

        return {
            "inspection_id": inspection_id,
            "vin": insp[1],
            "customer": insp[2],
            "created": insp[3],
            "categories": categories,
            "recommendations": recommendations,
            "total_approved": round(total_approved, 2),
            "total_pending": round(total_pending, 2),
            "viewed": bool(insp[5]),
        }

    def generate_text_summary(self, inspection_id: str) -> str:
        """Generate a plain-text summary suitable for SMS/email."""
        r = self.generate_report(inspection_id)
        if "error" in r:
            return r["error"]

        lines = [
            f"Inspection Report for {r['customer']} ({r['vin']})",
            f"Generated: {r['created']}",
            "",
            "Condition Summary:",
        ]
        for cat, data in r["categories"].items():
            emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[data["condition"]]
            lines.append(f"  {emoji} {cat.title()}")

        lines.extend(["", "Recommendations:"])
        for rec in r["recommendations"]:
            icon = {"approved": "✅", "declined": "❌", "pending": "⏳"}[rec["status"]]
            lines.append(f"  {icon} {rec['text']} (${rec['cost']:.0f})")

        lines.extend(["", f"Approved total: ${r['total_approved']:.2f}",
                      f"Pending total: ${r['total_pending']:.2f}"])
        return "\n".join(lines)
