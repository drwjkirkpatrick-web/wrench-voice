"""
vehicle_history.py
==================
Per-VIN service history tracking — CRM lite for the mechanic shop.

WHY:
A returning customer says "it's doing that thing again." The mechanic
needs to know what "that thing" was, what was done, and whether it
worked. Per-VIN history prevents repeat misdiagnoses and enables
predictive maintenance recommendations.

FEATURES:
- Full service record per VIN: symptoms, diagnoses, parts used, labor performed
- Predictive alerts: "brake pads last changed 45k miles ago — suggest inspection"
- Recurring issue detection: "3rd thermostat failure in 2 years — check cooling system"
- Odometer validation: flag rollbacks via Carfax (stub)
- Customer contact info linked to vehicle
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class VehicleHistory:
    """
    Service history database per VIN.

    Usage:
        vh = VehicleHistory()
        vh.add_visit(vin="1HGCM82633A004352", customer="Jane Doe",
                       symptom="overheating", diagnosis="bad thermostat",
                       parts_used=["thermostat", "coolant"], labor="1.2 hrs",
                       odometer=124500, cost=340)
        visits = vh.lookup(vin="1HGCM82633A004352")
        alerts = vh.predictive_alerts(vin="1HGCM82633A004352", current_odometer=128000)
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    # Recommended service intervals by category (miles)
    SERVICE_INTERVALS: dict[str, int] = {
        "brake_pads": 45000, "brake_rotors": 70000,
        "timing_belt": 60000, "timing_chain": 120000,
        "spark_plugs_iridium": 105000, "spark_plugs_copper": 30000,
        "coolant_exchange": 60000, "transmission_fluid": 30000,
        "air_filter": 30000, "cabin_filter": 15000,
        "serpentine_belt": 60000, "water_pump": 100000,
    }

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS vehicles (
                    vin TEXT PRIMARY KEY,
                    customer TEXT,
                    year INTEGER,
                    make TEXT,
                    model TEXT,
                    engine TEXT,
                    phone TEXT,
                    email TEXT
                );

                CREATE TABLE IF NOT EXISTS service_visits (
                    visit_id TEXT PRIMARY KEY,
                    vin TEXT REFERENCES vehicles(vin),
                    visit_date TEXT,
                    odometer INTEGER,
                    symptom TEXT,
                    diagnosis TEXT,
                    parts_used TEXT,  -- JSON list
                    labor_description TEXT,
                    labor_hours REAL,
                    cost_parts REAL,
                    cost_labor REAL,
                    notes TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_visit_vin ON service_visits(vin, visit_date);
            """)

    def register_vehicle(
        self, vin: str, customer: str, year: int, make: str, model: str,
        engine: str = "", phone: str = "", email: str = "",
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO vehicles
                   (vin, customer, year, make, model, engine, phone, email)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (vin, customer, year, make, model, engine, phone, email),
            )

    def add_visit(
        self,
        vin: str,
        odometer: int,
        symptom: str,
        diagnosis: str,
        parts_used: list[str],
        labor_description: str = "",
        labor_hours: float = 0.0,
        cost_parts: float = 0.0,
        cost_labor: float = 0.0,
        notes: str = "",
    ) -> str:
        visit_id = f"VISIT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(2).hex()}"
        now = datetime.now().isoformat()
        parts_json = "; ".join(parts_used) if isinstance(parts_used, list) else str(parts_used)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO service_visits
                   (visit_id, vin, visit_date, odometer, symptom, diagnosis,
                    parts_used, labor_description, labor_hours,
                    cost_parts, cost_labor, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (visit_id, vin, now, odometer, symptom, diagnosis,
                 parts_json, labor_description, labor_hours,
                 cost_parts, cost_labor, notes),
            )
        return visit_id

    def lookup(self, vin: str, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT visit_date, odometer, symptom, diagnosis, parts_used,
                          labor_hours, cost_parts, cost_labor, notes
                   FROM service_visits WHERE vin=? ORDER BY visit_date DESC LIMIT ?""",
                (vin, limit),
            ).fetchall()
        return [
            {
                "date": r[0], "odometer": r[1], "symptom": r[2], "diagnosis": r[3],
                "parts": r[4].split("; ") if r[4] else [], "labor_hours": r[5],
                "cost_parts": r[6], "cost_labor": r[7], "notes": r[8],
            }
            for r in rows
        ]

    def vehicle_summary(self, vin: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            veh = conn.execute("SELECT * FROM vehicles WHERE vin=?", (vin,)).fetchone()
            visits = conn.execute(
                "SELECT COUNT(*), MAX(odometer), MIN(odometer) FROM service_visits WHERE vin=?", (vin,)
            ).fetchone()
        if not veh:
            return {"error": "VIN not registered"}
        return {
            "vin": vin,
            "customer": veh[1],
            "year": veh[2], "make": veh[3], "model": veh[4], "engine": veh[5],
            "phone": veh[6], "email": veh[7],
            "total_visits": visits[0],
            "max_odometer": visits[1],
            "min_odometer": visits[2],
        }

    def predictive_alerts(self, vin: str, current_odometer: int) -> list[dict[str, Any]]:
        """Suggest upcoming services based on last visit per category."""
        history = self.lookup(vin)
        alerts = []
        for svc, interval in self.SERVICE_INTERVALS.items():
            # Find last visit mentioning this service category
            last = None
            for h in history:
                if svc.replace("_", " ") in h["diagnosis"].lower() or svc.replace("_", " ") in h["symptom"].lower():
                    if any(svc.replace("_", " ") in p.lower() for p in h["parts"]):
                        last = h
                        break
            if last:
                miles_since = current_odometer - (last["odometer"] or 0)
                if miles_since >= interval:
                    alerts.append({
                        "service": svc,
                        "last_done_at": last["odometer"],
                        "miles_since": miles_since,
                        "interval": interval,
                        "urgency": "overdue",
                        "message": f"{svc.replace('_', ' ').title()} overdue by {miles_since - interval:,} miles. Last done at {last['odometer']:,}.",
                    })
                elif miles_since >= interval * 0.8:
                    alerts.append({
                        "service": svc,
                        "last_done_at": last["odometer"],
                        "miles_since": miles_since,
                        "interval": interval,
                        "urgency": "soon",
                        "message": f"{svc.replace('_', ' ').title()} due soon. {interval - miles_since:,} miles remaining.",
                    })
        return alerts

    def recurring_issues(self, vin: str, threshold: int = 2) -> list[dict[str, Any]]:
        """Find symptoms/diagnoses that appear more than N times."""
        history = self.lookup(vin, limit=100)
        from collections import Counter
        sym_counts = Counter(h["symptom"] for h in history)
        diag_counts = Counter(h["diagnosis"] for h in history)
        recurring = []
        for s, c in sym_counts.items():
            if c >= threshold:
                recurring.append({"type": "symptom", "text": s, "occurrences": c})
        for d, c in diag_counts.items():
            if c >= threshold:
                recurring.append({"type": "diagnosis", "text": d, "occurrences": c})
        return recurring
