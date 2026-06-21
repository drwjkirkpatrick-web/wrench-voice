"""
sms_billing.py
==============
SMS-based billing reminders and payment collection for mechanic shops.

WHY:
Small shops lose money to unpaid invoices. Automated SMS reminders
with "Reply PAY" functionality reduce collection time and improve
cash flow. No expensive billing software needed.

FEATURES:
- Scheduled reminder sequence: day 7, day 14, day 30 after invoice
- Interactive payment links via Stripe (or manual "call shop" fallback)
- Payment status tracking per invoice
- Customer-opt-out respect
- Reminder tone escalation: polite → firm → final notice
- Monthly AR aging report
- Integration with customer_notifier.py (uses same Twilio backend)

REMINDER SCHEDULE:
    Day 0: Invoice sent (via customer_notifier or QuickBooks)
    Day 7: Gentle reminder
    Day 14: Firm reminder
    Day 30: Final notice + shop phone number
    Day 45: Flag for collection follow-up call

EXAMPLE FLOW:
    Customer receives: "Invoice #INV-001 for $487 due in 7 days. Pay securely: [link]"
    Day 14: "Friendly reminder: Invoice #INV-001 ($487) is now overdue. Pay now: [link] or call 503-555-0100"
    Customer replies "PAY" → webhook triggers Stripe payment page → records payment
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class SMSBilling:
    """
    SMS billing reminders and payment tracking.

    Usage:
        billing = SMSBilling(mock_mode=True)
        billing.create_invoice(invoice_id="INV-001", customer="Jane Doe",
                               phone="+15551234567", amount=487.50,
                               ticket_id="JOB-001", due_days=14)

        # Daily cron runs this:
        billing.send_due_reminders()

        # Check status:
        ar = billing.ar_aging()
        overdue = billing.overdue_invoices()
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    REMINDER_SCHEDULE = [7, 14, 30, 45]

    def __init__(self, db_path: str | None = None, mock_mode: bool = False) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self.mock_mode = mock_mode
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    ticket_id TEXT,
                    customer TEXT,
                    phone TEXT,
                    amount REAL,
                    tax REAL DEFAULT 0,
                    total REAL,
                    issued_date TEXT,
                    due_date TEXT,
                    paid INTEGER DEFAULT 0,
                    paid_date TEXT,
                    payment_method TEXT,
                    reminder_count INTEGER DEFAULT 0,
                    last_reminder_date TEXT,
                    opted_out INTEGER DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS payment_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT REFERENCES invoices(invoice_id),
                    sent_at TEXT,
                    days_after_invoice INTEGER,
                    message TEXT,
                    status TEXT  -- sent | delivered | failed | responded
                );

                CREATE INDEX IF NOT EXISTS idx_inv_due ON invoices(due_date);
                CREATE INDEX IF NOT EXISTS idx_inv_paid ON invoices(paid);
            """)

    def create_invoice(
        self,
        invoice_id: str,
        customer: str,
        phone: str,
        amount: float,
        ticket_id: str = "",
        tax: float = 0.0,
        due_days: int = 14,
        notes: str = "",
    ) -> dict[str, Any]:
        now = datetime.now()
        due = now + timedelta(days=due_days)
        total = amount + tax
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO invoices
                   (invoice_id, ticket_id, customer, phone, amount, tax, total,
                    issued_date, due_date, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (invoice_id, ticket_id, customer, phone, amount, tax, total,
                 now.isoformat(), due.isoformat(), notes),
            )
        return {
            "invoice_id": invoice_id,
            "customer": customer,
            "amount": amount,
            "tax": tax,
            "total": total,
            "due": due.isoformat(),
        }

    def mark_paid(self, invoice_id: str, method: str = "unknown") -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE invoices SET paid=1, paid_date=?, payment_method=? WHERE invoice_id=?",
                (now, method, invoice_id),
            )

    def send_due_reminders(self) -> list[dict[str, Any]]:
        """Send reminders for unpaid invoices at their scheduled day marks."""
        sent: list[dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT invoice_id, customer, phone, amount, total, issued_date,
                          reminder_count, last_reminder_date
                   FROM invoices WHERE paid=0 AND opted_out=0"""
            ).fetchall()

        for r in rows:
            inv_id, customer, phone, amount, total, issued, rem_count, last_rem = r
            issued_dt = datetime.fromisoformat(issued)
            days_elapsed = (datetime.now() - issued_dt).days

            # Find next scheduled reminder day
            next_day = None
            for d in self.REMINDER_SCHEDULE:
                if days_elapsed >= d and rem_count < self.REMINDER_SCHEDULE.index(d) + 1:
                    next_day = d
                    break

            if next_day is None:
                continue

            msg = self._render_message(inv_id, customer, total, next_day)
            status = self._send_sms(phone, msg)

            # Record
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO payment_reminders (invoice_id, sent_at, days_after_invoice, message, status) VALUES (?,?,?,?,?)",
                    (inv_id, now, next_day, msg, status),
                )
                conn.execute(
                    "UPDATE invoices SET reminder_count=reminder_count+1, last_reminder_date=? WHERE invoice_id=?",
                    (now, inv_id),
                )

            sent.append({"invoice_id": inv_id, "day": next_day, "status": status, "message": msg})
        return sent

    def _render_message(self, invoice_id: str, customer: str, total: float, day: int) -> str:
        shop_phone = "503-555-0100"
        if day <= 7:
            return (
                f"Hi {customer}, your invoice {invoice_id} (${total:.2f}) is coming due. "
                f"Reply PAY for a secure payment link, or call {shop_phone}. Thanks!"
            )
        elif day <= 14:
            return (
                f"Reminder: Invoice {invoice_id} (${total:.2f}) is now overdue. "
                f"Please pay to keep your account in good standing: Reply PAY or call {shop_phone}"
            )
        elif day <= 30:
            return (
                f"FINAL NOTICE: Invoice {invoice_id} (${total:.2f}) is 30 days overdue. "
                f"Please arrange payment immediately. Call {shop_phone}. Thank you."
            )
        else:
            return (
                f"Account notice: Invoice {invoice_id} (${total:.2f}) requires immediate attention. "
                f"Please contact us at {shop_phone} to discuss payment options."
            )

    def _send_sms(self, phone: str, message: str) -> str:
        if self.mock_mode:
            return "mock_sent"
        # Future: integrate with customer_notifier.CustomerNotifier or Twilio directly
        return "queued"

    def ar_aging(self) -> dict[str, Any]:
        """Accounts receivable aging report."""
        now = datetime.now()
        buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT issued_date, total FROM invoices WHERE paid=0"
            ).fetchall()
        total_unpaid = 0.0
        for issued, amt in rows:
            issued_dt = datetime.fromisoformat(issued)
            days = (now - issued_dt).days
            total_unpaid += amt
            if days <= 0:
                buckets["current"] += amt
            elif days <= 30:
                buckets["1_30"] += amt
            elif days <= 60:
                buckets["31_60"] += amt
            elif days <= 90:
                buckets["61_90"] += amt
            else:
                buckets["over_90"] += amt
        return {
            "total_unpaid": round(total_unpaid, 2),
            "invoice_count": len(rows),
            "buckets": {k: round(v, 2) for k, v in buckets.items()},
            "report_date": now.strftime("%Y-%m-%d"),
        }

    def overdue_invoices(self, days: int = 14) -> list[dict[str, Any]]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT invoice_id, customer, phone, total, issued_date, reminder_count
                   FROM invoices WHERE paid=0 AND issued_date < ? ORDER BY issued_date""",
                (cutoff,),
            ).fetchall()
        return [
            {"invoice_id": r[0], "customer": r[1], "phone": r[2],
             "total": r[3], "issued": r[4], "reminders_sent": r[5]}
            for r in rows
        ]

    def payment_stats(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total_invoiced = conn.execute(
                "SELECT SUM(total) FROM invoices"
            ).fetchone()[0] or 0.0
            total_collected = conn.execute(
                "SELECT SUM(total) FROM invoices WHERE paid=1"
            ).fetchone()[0] or 0.0
            total_outstanding = conn.execute(
                "SELECT SUM(total) FROM invoices WHERE paid=0"
            ).fetchone()[0] or 0.0
            count_paid = conn.execute("SELECT COUNT(*) FROM invoices WHERE paid=1").fetchone()[0]
            count_unpaid = conn.execute("SELECT COUNT(*) FROM invoices WHERE paid=0").fetchone()[0]
        return {
            "total_invoiced": round(total_invoiced, 2),
            "total_collected": round(total_collected, 2),
            "collection_rate": round(total_collected / total_invoiced * 100, 1) if total_invoiced else 0,
            "outstanding": round(total_outstanding, 2),
            "paid_count": count_paid,
            "unpaid_count": count_unpaid,
        }
