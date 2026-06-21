"""
customer_notifier.py
====================
SMS and text-based customer notifications using Twilio or SMTP.

WHY:
Customers want to know:
1. "Your car is ready." → immediate text
2. "We found an additional issue." → approval request via SMS
3. "Parts arrived." → job can start
4. "Estimate: $487. Approve? Reply YES or CALL." → async approval

This module provides a unified notification pipeline:
- Status updates (automated from job_scheduler events)
- Approval requests (interactive, with YES/NO/CALL responses)
- Review requests (after pickup, automated)
- Templates for voice-to-text conversion

BACKENDS:
- Twilio (SMS)
- SMTP (email fallback)
- Local file (testing, demo mode)
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class CustomerNotifier:
    """
    Customer notification system.

    Usage:
        notifier = CustomerNotifier(mock_mode=True)  # for testing
        notifier.send_status(to="+15555551234",
                             message="Your brake job is complete. Total: $487. Ready for pickup.")
        notifier.request_approval(to="+15555551234",
                                  job_ticket="JOB-001",
                                  text="Seized caliper bracket needs replacement. Additional $120. Approve? Reply YES or CALL.")
    """

    DEFAULT_DB = Path.home() / ".cache" / "wrench-voice" / "shop.db"

    # Message templates optimized for SMS (short, actionable)
    TEMPLATES: dict[str, str] = {
        "job_complete": "Your {make} {model} is ready! Total: ${total}. Ready for pickup during business hours.",
        "parts_arrived": "Good news — parts for your {make} {model} arrived. We'll start work today.",
        "approval_request": "Additional work needed: {description}. Cost: ${cost}. Approve? Reply YES, NO, or CALL {shop_phone}.",
        "estimate_ready": "Estimate for {symptom} on your {make} {model}: ${estimate}. Reply APPROVE to proceed or CALL to discuss.",
        "job_started": "Work has begun on your {make} {model}. Estimated completion: {eta}.",
        "pickup_reminder": "Reminder: Your {make} {model} has been ready since {ready_time}. Please pick up today.",
        "review_request": "Thanks for choosing {shop_name}! We'd love your feedback: {review_link}",
    }

    def __init__(self, db_path: str | None = None, mock_mode: bool = False) -> None:
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self.mock_mode = mock_mode
        self.twilio_sid = os.environ.get("TWILIO_SID", "")
        self.twilio_token = os.environ.get("TWILIO_TOKEN", "")
        self.twilio_from = os.environ.get("TWILIO_FROM", "")
        self.shop_phone = os.environ.get("SHOP_PHONE", "503-555-0100")
        self.shop_name = os.environ.get("SHOP_NAME", "Wrench Auto")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    to_number TEXT,
                    message TEXT,
                    template TEXT,
                    job_ticket TEXT,
                    sent_at TEXT,
                    status TEXT,  -- queued | sent | delivered | failed
                    response TEXT,
                    responded_at TEXT
                )
            """)

    def _render(self, template_name: str, context: dict[str, Any]) -> str:
        tmpl = self.TEMPLATES.get(template_name, template_name)
        context.setdefault("shop_phone", self.shop_phone)
        context.setdefault("shop_name", self.shop_name)
        try:
            return tmpl.format(**context)
        except KeyError:
            return tmpl

    def send(self, to: str, message: str, template: str = "custom", job_ticket: str = "") -> dict[str, Any]:
        """Send a notification. Returns status dict."""
        now = datetime.now().isoformat()
        if self.mock_mode:
            status = "sent"
            sid = f"MOCK-{now.replace(':','')}"
        else:
            status, sid = self._send_twilio(to, message)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO notifications (to_number, message, template, job_ticket, sent_at, status) VALUES (?,?,?,?,?,?)",
                (to, message, template, job_ticket, now, status),
            )

        return {"status": status, "sid": sid, "to": to, "message": message}

    def send_status(self, to: str, **ctx) -> dict[str, Any]:
        msg = self._render("job_complete", ctx)
        return self.send(to, msg, "job_complete", ctx.get("job_ticket", ""))

    def request_approval(self, to: str, job_ticket: str, description: str, cost: float, **ctx) -> dict[str, Any]:
        ctx.update({"description": description, "cost": cost, "job_ticket": job_ticket})
        msg = self._render("approval_request", ctx)
        return self.send(to, msg, "approval_request", job_ticket)

    def send_estimate(self, to: str, **ctx) -> dict[str, Any]:
        msg = self._render("estimate_ready", ctx)
        return self.send(to, msg, "estimate_ready", ctx.get("job_ticket", ""))

    def _send_twilio(self, to: str, message: str) -> tuple[str, str]:
        """Real Twilio send. Requires env vars."""
        if not self.twilio_sid or not self.twilio_token:
            return ("failed", "no_credentials")
        try:
            from twilio.rest import Client
            client = Client(self.twilio_sid, self.twilio_token)
            msg = client.messages.create(
                body=message,
                from_=self.twilio_from,
                to=to,
            )
            return ("sent", msg.sid)
        except Exception as e:
            return ("failed", str(e))

    def record_response(self, phone: str, response: str) -> dict[str, Any]:
        """Record an incoming SMS response. Used by webhook handler."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE notifications SET response=?, responded_at=? WHERE to_number=? AND responded_at IS NULL ORDER BY sent_at DESC LIMIT 1",
                (response.strip().upper(), now, phone),
            )
        # Interpret response
        resp = response.strip().upper()
        return {
            "action": "approve" if resp in ("YES", "Y", "APPROVE", "OK") else
                      "decline" if resp in ("NO", "N", "DECLINE") else
                      "call_requested" if "CALL" in resp else
                      "unclear",
            "raw": response,
            "recorded": now,
        }

    def pending_approvals(self) -> list[dict[str, Any]]:
        """Approval requests awaiting customer response."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT to_number, message, job_ticket, sent_at
                   FROM notifications
                   WHERE template='approval_request' AND responded_at IS NULL
                   ORDER BY sent_at"""
            ).fetchall()
        return [
            {"phone": r[0], "message": r[1], "ticket": r[2], "sent": r[3]}
            for r in rows
        ]

    def mock_send_queue(self) -> list[dict[str, Any]]:
        """For mock_mode: return all messages that WOULD have been sent."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT to_number, message, template, job_ticket, sent_at FROM notifications ORDER BY sent_at DESC LIMIT 50"
            ).fetchall()
        return [
            {"to": r[0], "message": r[1], "template": r[2], "ticket": r[3], "sent": r[4]}
            for r in rows
        ]
