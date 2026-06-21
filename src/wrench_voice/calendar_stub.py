"""
calendar_stub.py
================
Stub for Google Calendar / Outlook calendar sync.

WHY:
Techs need to see their assignments on their phones.
Shop managers need to see bay utilization at a glance.
Calendar sync pushes scheduled jobs to shared calendars.

CURRENT STATUS: STUB — requires Google OAuth2 or Microsoft Graph API.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class CalendarStub:
    """
    Calendar sync stub.

    Usage:
        cal = CalendarStub(mock_mode=True)
        cal.create_event(ticket_id="JOB-001", bay="Bay 2", tech="Mike",
                         start="2025-08-01T08:00:00", duration_min=240,
                         title="Timing belt - Honda Accord")
        # Real: cal.sync_to_google() or cal.sync_to_outlook()
    """

    def __init__(self, mock_mode: bool = True) -> None:
        self.mock_mode = mock_mode
        self.events: list[dict[str, Any]] = []
        self.cache_path = Path.home() / ".cache" / "wrench-voice" / "calendar_events.json"

    def create_event(
        self,
        ticket_id: str,
        title: str,
        bay: str,
        tech: str,
        start_iso: str,
        duration_min: int,
        customer: str = "",
        vehicle: str = "",
    ) -> dict[str, Any]:
        start = datetime.fromisoformat(start_iso)
        end = start + timedelta(minutes=duration_min)
        event = {
            "id": f"EVT-{ticket_id}",
            "ticket_id": ticket_id,
            "title": title,
            "bay": bay,
            "tech": tech,
            "start": start_iso,
            "end": end.isoformat(),
            "customer": customer,
            "vehicle": vehicle,
            "synced": False,
        }
        self.events.append(event)
        self._save()
        return event

    def list_events(self, date_str: str | None = None) -> list[dict[str, Any]]:
        if not date_str:
            return self.events
        return [e for e in self.events if e["start"].startswith(date_str)]

    def sync_to_google(self, calendar_id: str = "primary") -> list[dict[str, Any]]:
        """Push events to Google Calendar. Requires OAuth2."""
        if self.mock_mode:
            for e in self.events:
                e["synced"] = True
                e["google_event_id"] = f"GOOGLE-MOCK-{e['id']}"
            self._save()
            return [{"status": "mock_synced", "event": e["id"]} for e in self.events]
        # Future: Google Calendar API
        return [{"status": "not_implemented", "message": "Configure Google OAuth2"}]

    def _save(self) -> None:
        self.cache_path.write_text(json.dumps(self.events, indent=2))

    def load(self) -> None:
        if self.cache_path.exists():
            self.events = json.loads(self.cache_path.read_text())
