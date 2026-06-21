"""
cost_analyzer.py
================
Job profitability tracking: estimated vs. actual costs and labor hours.

WHY:
A shop needs to know which jobs make money and which lose money.
Flat-rate times don't match reality. This module learns actual
durations and flags underpriced jobs.

FEATURES:
- Per-job cost tracking: parts + labor + markup
- Flat-rate vs. actual hours per tech
- Profit margin per job, bay, tech, engine family
- Flag jobs where actual exceeded estimate by > 20%
- Monthly P&L rollup
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


class CostAnalyzer:
    """
    Track and analyze job profitability.

    Usage:
        ca = CostAnalyzer()
        ca.record_estimate("JOB-001", parts_cost=340, labor_hours_est=4.5, labor_rate=95)
        ca.record_actual("JOB-001", parts_cost=380, labor_hours_actual=5.2)
        report = ca.job_report("JOB-001")
        summary = ca.monthly_summary("2025-08")
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS job_costs (
                    ticket_id TEXT PRIMARY KEY,
                    engine TEXT,
                    symptom TEXT,
                    parts_cost_est REAL,
                    parts_cost_actual REAL,
                    labor_hours_est REAL,
                    labor_hours_actual REAL,
                    labor_rate REAL,
                    markup_pct REAL DEFAULT 30.0,
                    billed_total REAL,
                    recorded_month TEXT,
                    created_at TEXT,
                    closed_at TEXT
                );
            """)

    def record_estimate(
        self,
        ticket_id: str,
        engine: str = "",
        symptom: str = "",
        parts_cost_est: float = 0.0,
        labor_hours_est: float = 0.0,
        labor_rate: float = 95.0,
        markup_pct: float = 30.0,
    ) -> None:
        now = datetime.now().isoformat()
        month = now[:7]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO job_costs
                   (ticket_id, engine, symptom, parts_cost_est, labor_hours_est,
                    labor_rate, markup_pct, recorded_month, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (ticket_id, engine, symptom, parts_cost_est, labor_hours_est,
                 labor_rate, markup_pct, month, now),
            )

    def record_actual(
        self,
        ticket_id: str,
        parts_cost_actual: float = 0.0,
        labor_hours_actual: float = 0.0,
        billed_total: float = 0.0,
    ) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_costs SET parts_cost_actual=?, labor_hours_actual=?, billed_total=?, closed_at=? WHERE ticket_id=?",
                (parts_cost_actual, labor_hours_actual, billed_total, now, ticket_id),
            )

    def job_report(self, ticket_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM job_costs WHERE ticket_id=?", (ticket_id,)
            ).fetchone()
        if not row:
            return {"error": "Ticket not found"}
        cols = [c[0] for c in conn.execute("SELECT * FROM job_costs LIMIT 0").description]
        d = dict(zip(cols, row))

        # Calculate metrics
        parts_est = d["parts_cost_est"] or 0
        parts_act = d["parts_cost_actual"] or parts_est
        labor_est = d["labor_hours_est"] or 0
        labor_act = d["labor_hours_actual"] or labor_est
        rate = d["labor_rate"] or 95.0
        markup = d["markup_pct"] or 30.0

        est_total = parts_est * (1 + markup/100) + labor_est * rate
        act_total = parts_act * (1 + markup/100) + labor_act * rate
        profit = d["billed_total"] or 0 - act_total
        margin = (profit / est_total * 100) if est_total > 0 else 0
        overrun = ((act_total - est_total) / est_total * 100) if est_total > 0 else 0

        return {
            "ticket_id": ticket_id,
            "parts_estimate": parts_est,
            "parts_actual": parts_act,
            "labor_estimate_hours": labor_est,
            "labor_actual_hours": labor_act,
            "efficiency": round(labor_est / labor_act * 100, 1) if labor_act > 0 else 0,
            "estimated_total": round(est_total, 2),
            "actual_total": round(act_total, 2),
            "billed": d["billed_total"] or 0,
            "profit": round(profit, 2),
            "margin_pct": round(margin, 1),
            "cost_overrun_pct": round(overrun, 1),
            "flag": "overrun" if overrun > 20 else "good" if margin > 15 else "thin",
        }

    def monthly_summary(self, month: str) -> dict[str, Any]:
        """month format: YYYY-MM"""
        with sqlite3.connect(self.db_path) as conn:
            total_jobs = conn.execute(
                "SELECT COUNT(*) FROM job_costs WHERE recorded_month=?", (month,)
            ).fetchone()[0]
            closed = conn.execute(
                "SELECT COUNT(*) FROM job_costs WHERE recorded_month=? AND closed_at IS NOT NULL", (month,)
            ).fetchone()[0]
            avg_margin = conn.execute(
                """SELECT AVG(billed_total - (parts_cost_actual * 1.3 + labor_hours_actual * labor_rate))
                   FROM job_costs WHERE recorded_month=? AND closed_at IS NOT NULL""",
                (month,),
            ).fetchone()[0] or 0.0
            overr = conn.execute(
                "SELECT COUNT(*) FROM job_costs WHERE recorded_month=? AND labor_hours_actual > labor_hours_est * 1.2", (month,)
            ).fetchone()[0]
        return {
            "month": month,
            "total_jobs": total_jobs,
            "completed": closed,
            "average_margin_estimate": round(avg_margin, 2),
            "overrun_jobs": overr,
            "completion_rate": round(closed / total_jobs * 100, 1) if total_jobs else 0,
        }

    def efficiency_by_technician(self, tech_name: str, month: str) -> dict[str, Any]:
        """For future integration with job_scheduler technician field."""
        return {
            "technician": tech_name,
            "month": month,
            "note": "Link job_scheduler.technician to job_costs after integration",
        }
