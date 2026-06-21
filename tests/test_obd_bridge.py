"""
Tests for the OBD-II bridge.

Verifies:
1. Mock mode returns realistic DTCs without hardware
2. DTC knowledge base resolves known codes
3. Unknown codes degrade gracefully
4. Full scan produces OBDScanResult with all fields
5. Clear DTCs returns True in mock mode
"""

import pytest

from wrench_voice.obd_bridge import OBDBridge, DTC, _resolve_dtc


class TestOBDBridge:
    """OBD-II scanner tests."""

    def test_mock_scan_returns_dtcs(self):
        """
        Mock mode should return at least one DTC with full metadata.
        """
        bridge = OBDBridge(mock_mode=True)
        result = bridge.full_scan()

        assert len(result.dtcs) >= 1
        assert isinstance(result.dtcs[0], DTC)
        assert result.dtcs[0].code.startswith("P")
        assert result.protocol == "Mock"

    def test_mock_scan_has_live_data(self):
        """
        Live data should include RPM and coolant temp.
        """
        bridge = OBDBridge(mock_mode=True)
        result = bridge.full_scan()

        pid_names = {p.pid_name for p in result.live_data}
        assert "RPM" in pid_names
        assert "Coolant Temp" in pid_names
        assert "O2 Voltage" in pid_names

    def test_mock_scan_has_readiness(self):
        """
        Readiness monitors should be populated.
        """
        bridge = OBDBridge(mock_mode=True)
        result = bridge.full_scan()

        assert "misfire" in result.readiness
        assert "catalyst" in result.readiness

    def test_mock_clear_returns_true(self):
        """
        Clearing DTCs in mock mode should succeed.
        """
        bridge = OBDBridge(mock_mode=True)
        assert bridge.clear_dtcs() is True

    def test_resolve_known_dtc(self):
        """
        A known code like P0301 should have full metadata.
        """
        dtc = _resolve_dtc("P0301")
        assert dtc.code == "P0301"
        assert "misfire" in dtc.description.lower()
        assert len(dtc.probable_causes) >= 1
        assert len(dtc.suggested_tests) >= 1

    def test_resolve_unknown_dtc(self):
        """
        An unknown code should not crash.
        """
        dtc = _resolve_dtc("P9999")
        assert dtc.code == "P9999"
        assert dtc.severity == "info"
        assert "unknown" in dtc.description.lower()

    def test_mock_scan_warnings(self):
        """
        A scan with critical codes should trigger warnings.
        """
        bridge = OBDBridge(mock_mode=True)
        result = bridge.full_scan()
        # P0171 (lean) should trigger a warning
        if any(d.code in ("P0171", "P0174") for d in result.dtcs):
            assert any("lean" in w.lower() for w in result.warnings)
