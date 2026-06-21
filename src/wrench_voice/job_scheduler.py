"""
job_scheduler.py
================
Bay scheduling, technician assignment, and job timeline management.

WHY:
A real shop has 2–4 bays, 1–3 technicians, and jobs that depend on parts
availability. A mechanic shouldn't walk to the bay and discover the water pump
hasn't arrived yet.

FEATURES:
- Digital bay board with bay 1–N, tech assignment, time slots
- Job tickets linked to diagnosis results and parts plans
- Automatic parts-availability check before confirming a job
- Learns actual job duration per engine+symptom (flat-rate vs. reality)
- Optimization: reorders jobs to maximize bay utilization and minimize idle time

DATA MODEL:
- Bay: id, name, equipment (lift_2_post, lift_4_post, pit, etc.)
- JobTicket: ticket linking customer, vehicle, diagnosis, plan, bay, tech
- ScheduleSlot: a bay at a specific time range
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# ─── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class Bay:
    bay_id: str
    name: str
    equipment: str  # e.g. "2-post_lift", "4-post_lift", "alignment_rack"
    active: bool = True


@dataclass
class JobTicket:
    """One repair job scheduled into a bay."""
    ticket_id: str
    customer: str
    vin: str | None
    year: int | None
    make: str | None
    model: str | None
    engine: str | None
    symptom: str
    diagnosis_id: str | None  # links to DiagnosticEngine result
    plan_id: str | None       # links to PartsPlanner job plan
    bay_id: str | None
    technician: str | None
    scheduled_start: str  # ISO datetime
    estimated_duration_min: int
    actual_start: str | None = None
    actual_end: str | None = None
    status: str = "pending"  # pending | active | waiting_parts | on_hold | completed | cancelled
    priority: int = 2        # 1=critical | 2=normal | 3=low
    parts_status: str = "checking"  # checking | in_stock | ordered | arrived | n/a
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Scheduler ───────────────────────────────────────────────────────────────────

class JobScheduler:
    """
    SQLite-backed scheduler for mechanic shop bays.

    Usage:
        sched = JobScheduler(db_path="data/shop.db")
        sched.add_bay(Bay("b1", "Bay 1", "2-post_lift"))

        ticket = sched.schedule_job(
            customer="Jane Doe",
            vin="1HGCM82633A004352",
            year=2005, make="Honda", model="Accord", engine="K24",
            symptom="overheating",
            diagnosis_id="diag_001",
            plan_id="plan_001",
            technician="Mike",
            scheduled_start="2025-08-01T08:00:00",
            estimated_duration_min=240,
        )

        # Before confirming, check parts are in stock
        parts_ok = sched.check_parts_ready(ticket.ticket_id)
        if not parts_ok:
            sched.hold_for_parts(ticket.ticket_id)
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ─── Schema ──────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bays (
                    bay_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    equipment TEXT,
                    active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS job_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    customer TEXT,
                    vin TEXT,
                    year INTEGER,
                    make TEXT,
                    model TEXT,
                    engine TEXT,
                    symptom TEXT,
                    diagnosis_id TEXT,
                    plan_id TEXT,
                    bay_id TEXT REFERENCES bays(bay_id),
                    technician TEXT,
                    scheduled_start TEXT,
                    estimated_duration_min INTEGER,
                    actual_start TEXT,
                    actual_end TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 2,
                    parts_status TEXT DEFAULT 'checking',
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS duration_learned (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    engine TEXT,
                    symptom TEXT,
                    estimated_min INTEGER,
                    actual_min INTEGER,
                    recorded_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_date ON job_tickets(scheduled_start);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON job_tickets(status);
            """)

    # ─── Bay Management ──────────────────────────────────────────────────────────

    def add_bay(self, bay: Bay) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bays (bay_id, name, equipment, active) VALUES (?,?,?,?)",
                (bay.bay_id, bay.name, bay.equipment, int(bay.active)),
            )

    def list_bays(self) -> list[Bay]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT bay_id, name, equipment, active FROM bays WHERE active=1").fetchall()
        return [Bay(r[0], r[1], r[2], bool(r[3])) for r in rows]

    # ─── Job Scheduling ──────────────────────────────────────────────────────────

    def schedule_job(
        self,
        *,
        customer: str,
        vin: str | None = None,
        year: int | None = None,
        make: str | None = None,
        model: str | None = None,
        engine: str | None = None,
        symptom: str = "",
        diagnosis_id: str | None = None,
        plan_id: str | None = None,
        bay_id: str | None = None,
        technician: str | None = None,
        scheduled_start: str,
        estimated_duration_min: int,
        priority: int = 2,
        notes: str = "",
    ) -> JobTicket:
        """Create a new job ticket. Does NOT check conflicts — call optimize_schedule after."""
        ticket_id = f"JOB-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{hash(customer+symptom) % 1000:03d}"
        ticket = JobTicket(
            ticket_id=ticket_id,
            customer=customer,
            vin=vin,
            year=year,
            make=make,
            model=model,
            engine=engine,
            symptom=symptom,
            diagnosis_id=diagnosis_id,
            plan_id=plan_id,
            bay_id=bay_id,
            technician=technician,
            scheduled_start=scheduled_start,
            estimated_duration_min=estimated_duration_min,
            status="pending",
            priority=priority,
            parts_status="checking",
            notes=notes,
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO job_tickets
                   (ticket_id, customer, vin, year, make, model, engine, symptom,
                    diagnosis_id, plan_id, bay_id, technician, scheduled_start,
                    estimated_duration_min, status, priority, parts_status, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    ticket.ticket_id, ticket.customer, ticket.vin, ticket.year,
                    ticket.make, ticket.model, ticket.engine, ticket.symptom,
                    ticket.diagnosis_id, ticket.plan_id, ticket.bay_id,
                    ticket.technician, ticket.scheduled_start,
                    ticket.estimated_duration_min, ticket.status,
                    ticket.priority, ticket.parts_status, ticket.notes,
                ),
            )
        return ticket

    def get_ticket(self, ticket_id: str) -> JobTicket | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM job_tickets WHERE ticket_id=?", (ticket_id,)
            ).fetchone()
        if not row:
            return None
        cols = [c[0] for c in conn.execute("SELECT * FROM job_tickets LIMIT 0").description]
        d = dict(zip(cols, row))
        return JobTicket(**{k: d[k] for k in JobTicket.__dataclass_fields__})

    def update_status(self, ticket_id: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_tickets SET status=? WHERE ticket_id=?",
                (status, ticket_id),
            )

    def mark_started(self, ticket_id: str) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_tickets SET status='active', actual_start=? WHERE ticket_id=?",
                (now, ticket_id),
            )

    def mark_completed(self, ticket_id: str) -> None:
        """Close ticket and learn actual duration for future estimates."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_tickets SET status='completed', actual_end=? WHERE ticket_id=?",
                (now, ticket_id),
            )
            # Learn actual duration
            row = conn.execute(
                "SELECT engine, symptom, estimated_duration_min, actual_start FROM job_tickets WHERE ticket_id=?",
                (ticket_id,),
            ).fetchone()
            if row and row[2] and row[3]:
                est = row[2]
                start = datetime.fromisoformat(row[3])
                actual = int((datetime.now() - start).total_seconds() / 60)
                conn.execute(
                    "INSERT INTO duration_learned (engine, symptom, estimated_min, actual_min, recorded_at) VALUES (?,?,?,?,?)",
                    (row[0], row[1], est, actual, now),
                )

    # ─── Schedule Views ────────────────────────────────────────────────────────────

    def list_schedule(self, date_str: str | None = None) -> list[JobTicket]:
        """List jobs for a day. date_str = YYYY-MM-DD."""
        sql = "SELECT * FROM job_tickets WHERE date(scheduled_start)=date(?) ORDER BY scheduled_start, priority"
        date_q = date_str or datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            cols = [c[0] for c in conn.execute("SELECT * FROM job_tickets LIMIT 0").description]
            rows = conn.execute(sql, (date_q,)).fetchall()
        out: list[JobTicket] = []
        for r in rows:
            d = dict(zip(cols, r))
            out.append(JobTicket(**{k: d[k] for k in JobTicket.__dataclass_fields__}))
        return out

    def bay_board(self, date_str: str | None = None) -> dict[str, list[JobTicket]]:
        """Return a dict: bay_id -> sorted list of tickets."""
        jobs = self.list_schedule(date_str)
        board: dict[str, list[JobTicket]] = {}
        for j in jobs:
            bid = j.bay_id or "unassigned"
            board.setdefault(bid, []).append(j)
        for bid in board:
            board[bid].sort(key=lambda x: x.scheduled_start)
        return board

    # ─── Parts-aware Hold / Release ────────────────────────────────────────────────

    def hold_for_parts(self, ticket_id: str) -> None:
        self.update_status(ticket_id, "waiting_parts")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_tickets SET parts_status='ordered' WHERE ticket_id=?",
                (ticket_id,),
            )

    def release_for_work(self, ticket_id: str) -> None:
        """Call when parts arrive — ticket goes back to pending."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_tickets SET status='pending', parts_status='arrived' WHERE ticket_id=?",
                (ticket_id,),
            )

    def check_parts_ready(self, ticket_id: str) -> bool:
        """
        Stub for inventory integration.
        Returns True if all parts for this ticket are in stock.
        In a real system, this queries the InventoryManager for the linked plan_id.
        """
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return False
        if ticket.parts_status in ("in_stock", "arrived", "n/a"):
            return True
        return False

    # ─── Optimization ──────────────────────────────────────────────────────────────

    def optimize_schedule(self, date_str: str | None = None) -> list[dict[str, Any]]:
        """
        Reorder jobs to maximize throughput.
        Rules:
        1. Critical priority first
        2. Jobs with parts in stock before jobs waiting
        3. Short jobs in gaps
        4. Technician specialization (if known)
        Returns a list of suggested moves.
        """
        jobs = self.list_schedule(date_str)
        suggestions: list[dict[str, Any]] = []

        # Sort: priority asc, parts_ready desc, duration asc
        def sort_key(j: JobTicket) -> tuple:
            parts_ok = 1 if j.parts_status in ("in_stock", "arrived") else 0
            return (j.priority, -parts_ok, j.estimated_duration_min)

        sorted_jobs = sorted(jobs, key=sort_key)
        bays = self.list_bays()
        if not bays:
            return suggestions

        # Simple greedy assignment
        bay_idx = 0
        current_time = datetime.strptime(date_str or datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d")
        for j in sorted_jobs:
            if j.status in ("completed", "cancelled"):
                continue
            bay = bays[bay_idx % len(bays)]
            if j.bay_id != bay.bay_id:
                suggestions.append({
                    "ticket_id": j.ticket_id,
                    "action": "move_to_bay",
                    "from_bay": j.bay_id,
                    "to_bay": bay.bay_id,
                    "reason": f"{bay.name} has availability",
                })
            bay_idx += 1

        return suggestions

    # ─── Learning ──────────────────────────────────────────────────────────────────

    def learned_duration(self, engine: str | None, symptom: str | None) -> int | None:
        """Return average actual duration for this engine+symptom combo."""
        sql = "SELECT AVG(actual_min) FROM duration_learned WHERE engine=? AND symptom=?"
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(sql, (engine, symptom)).fetchone()
        if row and row[0]:
            return int(row[0])
        return None

    def stats(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM job_tickets").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM job_tickets WHERE status='completed'").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM job_tickets WHERE status='active'").fetchone()[0]
            waiting = conn.execute("SELECT COUNT(*) FROM job_tickets WHERE status='waiting_parts'").fetchone()[0]
        return {
            "total_jobs": total,
            "completed": completed,
            "active": active,
            "waiting_for_parts": waiting,
            "db_path": str(self.db_path),
        }
