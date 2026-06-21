"""
warranty_tracker.py
===================
Track part warranties and core charge returns.

WHY:
Parts fail. When they do, you need to know:
1. Is this part still under warranty?
2. What is the core charge and have we returned it?
3. When does the warranty expire?

This prevents lost money from missed warranty claims and unreturned cores.

FEATURES:
- Warranty database: part, supplier, purchase date, warranty term
- Expiration alerts: daily scan for expiring warranties
- Core tracking: parts with core charges, return status, return deadlines
- Warranty claim documentation: link to invoice, job ticket, failure photo
- Bulk export for supplier warranty submission
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class WarrantyTracker:
    """
    Track part warranties and core returns.

    Usage:
        wt = WarrantyTracker()
        wt.register_part(sku="ALT-REMAN-001", part_name="Alternator reman",
                         supplier="RockAuto", warranty_months=24, core_charge=35.0,
                         job_ticket="JOB-001")
        # Later...
        expired = wt.expiring(days=30)
        overdue_cores = wt.overdue_cores(days=90)
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS warranties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT,
                    part_name TEXT,
                    supplier TEXT,
                    purchase_date TEXT,
                    warranty_months INTEGER DEFAULT 12,
                    expires_at TEXT,
                    core_charge REAL DEFAULT 0,
                    core_returned INTEGER DEFAULT 0,
                    core_deadline TEXT,
                    job_ticket TEXT,
                    invoice_reference TEXT,
                    notes TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_warranty_expiry ON warranties(expires_at);
                CREATE INDEX IF NOT EXISTS idx_warranty_core ON warranties(core_returned);
            """)

    def register_part(
        self,
        sku: str,
        part_name: str,
        supplier: str,
        warranty_months: int = 12,
        core_charge: float = 0.0,
        core_deadline_days: int = 365,
        job_ticket: str = "",
        invoice_reference: str = "",
        notes: str = "",
    ) -> int:
        """Register a part with warranty. Returns the warranty record ID."""
        now = datetime.now()
        expires = (now + timedelta(days=warranty_months * 30)).isoformat()
        core_deadline = (now + timedelta(days=core_deadline_days)).isoformat() if core_charge > 0 else None
        with sqlite3.connect(self.db_path) as conn:
            c = conn.execute(
                """INSERT INTO warranties
                   (sku, part_name, supplier, purchase_date, warranty_months,
                    expires_at, core_charge, core_deadline, job_ticket,
                    invoice_reference, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (sku, part_name, supplier, now.isoformat(), warranty_months,
                 expires, core_charge, core_deadline, job_ticket,
                 invoice_reference, notes),
            )
            return c.lastrowid

    def expiring(self, days: int = 30) -> list[dict[str, Any]]:
        """Warranties expiring in the next N days."""
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, sku, part_name, supplier, expires_at, job_ticket
                   FROM warranties
                   WHERE expires_at < ? AND expires_at > datetime('now')
                   ORDER BY expires_at""",
                (cutoff,),
            ).fetchall()
        return [
            {"id": r[0], "sku": r[1], "part": r[2], "supplier": r[3],
             "expires": r[4], "ticket": r[5]}
            for r in rows
        ]

    def expired(self) -> list[dict[str, Any]]:
        """Warranties that have already expired."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, sku, part_name, supplier, expires_at, job_ticket
                   FROM warranties WHERE expires_at < datetime('now')"""
            ).fetchall()
        return [
            {"id": r[0], "sku": r[1], "part": r[2], "supplier": r[3],
             "expired": r[4], "ticket": r[5]}
            for r in rows
        ]

    def overdue_cores(self, days: int = 90) -> list[dict[str, Any]]:
        """Core charges not returned, deadline approaching."""
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, sku, part_name, supplier, core_charge, core_deadline, job_ticket
                   FROM warranties
                   WHERE core_charge > 0 AND core_returned = 0 AND core_deadline < ?
                   ORDER BY core_deadline""",
                (cutoff,),
            ).fetchall()
        return [
            {"id": r[0], "sku": r[1], "part": r[2], "supplier": r[3],
             "core_charge": r[4], "deadline": r[5], "ticket": r[6]}
            for r in rows
        ]

    def mark_core_returned(self, warranty_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE warranties SET core_returned=1 WHERE id=?",
                (warranty_id,),
            )

    def summary(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM warranties").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM warranties WHERE expires_at > datetime('now')"
            ).fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM warranties WHERE expires_at < datetime('now')"
            ).fetchone()[0]
            cores_outstanding = conn.execute(
                "SELECT SUM(core_charge) FROM warranties WHERE core_returned=0 AND core_charge > 0"
            ).fetchone()[0] or 0.0
        return {
            "total_warranties": total,
            "active": active,
            "expired": expired,
            "outstanding_core_charges": round(cores_outstanding, 2),
        }
