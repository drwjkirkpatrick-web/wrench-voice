"""
carfax_stub.py
==============
Stub for Carfax / AutoCheck vehicle history integration.

WHY:
Checking service history helps:
1. Avoid misdiagnosing a problem the dealer already "fixed"
2. Verify odometer consistency
3. Identify vehicles with hidden accident/frame damage
4. Build trust with customers by showing you did homework

CURRENT STATUS: STUB — requires Carfax API subscription ($15–50/lookup).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class CarfaxStub:
    """
    Carfax / AutoCheck integration stub with local cache.

    Usage:
        cf = CarfaxStub(mock_mode=True)
        report = cf.lookup(vin="1HGCM82633A004352")
        # Returns mock data for testing
        # Real: cf.lookup(vin=...) with API key
    """

    def __init__(self, api_key: str = "", mock_mode: bool = True) -> None:
        self.api_key = api_key
        self.mock_mode = mock_mode
        self.cache_dir = Path.home() / ".cache" / "wrench-voice" / "carfax_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def lookup(self, vin: str) -> dict[str, Any]:
        cache_path = self.cache_dir / f"{vin}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text())

        if self.mock_mode:
            report = self._mock_report(vin)
        else:
            report = self._real_lookup(vin)

        cache_path.write_text(json.dumps(report))
        return report

    def _mock_report(self, vin: str) -> dict[str, Any]:
        # Deterministic mock based on VIN hash for consistent testing
        h = int(hashlib.sha256(vin.encode()).hexdigest(), 16)
        service_count = h % 12
        return {
            "vin": vin,
            "source": "carfax_mock",
            "owners": (h % 4) + 1,
            "service_records": service_count,
            "last_service_miles": (h % 150) * 1000,
            "last_service_date": f"202{h % 5}-{h % 12 + 1:02d}-{(h % 28) + 1:02d}",
            "accidents": (h % 5) == 0,
            "frame_damage": (h % 17) == 0,
            "odometer_consistent": True,
            "salvage": False,
            "fleet": (h % 8) == 0,
            "recalls_open": h % 3,
            "title_brands": [],
            "warnings": ["Possible fleet vehicle"] if (h % 8) == 0 else [],
        }

    def _real_lookup(self, vin: str) -> dict[str, Any]:
        if not self.api_key:
            return {"error": "No Carfax API key configured"}
        # Future: implement Carfax Partner API call
        return {"error": "not_implemented", "message": "Set CARFAX_API_KEY env var and implement _real_lookup"}

    def check_odometer(self, vin: str, reported_odometer: int) -> dict[str, Any]:
        """Verify odometer hasn't rolled back."""
        report = self.lookup(vin)
        if "error" in report:
            return report
        last_recorded = report.get("last_service_miles", 0)
        if reported_odometer < last_recorded:
            return {
                "vin": vin,
                "status": "rollback_suspected",
                "reported": reported_odometer,
                "last_recorded": last_recorded,
                "discrepancy": last_recorded - reported_odometer,
            }
        return {
            "vin": vin,
            "status": "consistent",
            "reported": reported_odometer,
            "last_recorded": last_recorded,
        }
