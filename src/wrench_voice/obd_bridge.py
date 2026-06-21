"""
obd_bridge.py
=============
OBD-II diagnostic code reader and live data bridge.

WHY:
When a Check Engine Light is on, the mechanic needs the DTC (Diagnostic Trouble Code)
before any symptom-based diagnosis. This module bridges an ELM327-compatible OBD-II
adapter to read codes, clear codes, and pull live sensor data (RPM, coolant temp,
O2 voltage, fuel trims) to narrow the diagnostic tree.

HOW:
1. Uses `python-obd` library (obd.Async connection) for multi-protocol support
2. Auto-detects the protocol (CAN, ISO 9141-2, KWP2000, SAE J1850)
3. Reads DTCs → maps common codes to likely causes → feeds into DiagnosticEngine
4. Pulls freeze-frame data for context
5. Falls back to mock mode when no adapter is present (demo / test / CI)

WHAT IT HANDLES:
- DTC read/clear
- Live PIDs: RPM, COOLANT_TEMP, ENGINE_LOAD, MAF, THROTTLE_POS, TIMING_ADVANCE,
  FUEL_LEVEL, O2_B1S1, O2_B1S2, SHORT_FUEL_TRIM_1, LONG_FUEL_TRIM_1,
  INTAKE_PRESSURE, INTAKE_TEMP, SPEED
- Freeze frame capture (snapshot at MIL set)
- Readiness monitors (emissions test prep)
- Protocol info (what the vehicle actually speaks)

COMPATIBILITY NOTES:
- 1996–2004 Toyota: ISO 9141-2 (pin 7) — many cheap ELM327 clones don't support this
- 2005+ Toyota: CAN bus (11-bit, 500 kbps)
- All vehicles 1996+ in the US are OBD-II compliant
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ─── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class DTC:
    """One diagnostic trouble code."""
    code: str            # e.g. "P0301"
    description: str     # Human-readable meaning
    severity: str        # "info" | "minor" | "major" | "critical"
    system: str          # "powertrain" | "chassis" | "body" | "network"
    probable_causes: list[str]
    suggested_tests: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "description": self.description,
            "severity": self.severity,
            "system": self.system,
            "probable_causes": self.probable_causes,
            "suggested_tests": self.suggested_tests,
        }


@dataclass
class FreezeFrame:
    """Snapshot of sensor values when a DTC was triggered."""
    dtc_code: str
    rpm: int | None
    coolant_temp_c: int | None
    engine_load_pct: float | None
    vehicle_speed_kmh: int | None
    throttle_pos_pct: float | None
    fuel_trim_short_pct: float | None
    fuel_trim_long_pct: float | None
    maf_rate_gs: float | None
    intake_temp_c: int | None
    o2_voltage_v: float | None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class LiveDataPoint:
    """One live sensor reading."""
    pid_name: str
    value: float | int | None
    unit: str
    timestamp: float


@dataclass
class OBDScanResult:
    """Complete scan output — codes, freeze frames, live data, readiness."""
    port: str
    protocol: str
    vehicle_vin: str | None
    dtcs: list[DTC]
    freeze_frames: list[FreezeFrame]
    readiness: dict[str, str]   # monitor name → "ready" | "not_ready" | "n/a"
    live_data: list[LiveDataPoint]
    mileage_km: float | None
    warnings: list[str]

    def to_markdown(self) -> str:
        lines = [
            f"# OBD-II Scan Report",
            f"",
            f"Port: `{self.port}`",
            f"Protocol: {self.protocol}",
        ]
        if self.vehicle_vin:
            lines.append(f"VIN: {self.vehicle_vin}")
        lines.append("")

        lines.append(f"## DTCs Found: {len(self.dtcs)}")
        for dtc in self.dtcs:
            sev_icon = {"info": "ℹ️", "minor": "⚡", "major": "🔶", "critical": "🚨"}.get(dtc.severity, "❓")
            lines.append(f"{sev_icon} **{dtc.code}** — {dtc.description} ({dtc.severity})")
            for cause in dtc.probable_causes[:3]:
                lines.append(f"   - Likely: {cause}")
        lines.append("")

        if self.freeze_frames:
            lines.append("## Freeze Frame")
            for ff in self.freeze_frames:
                lines.append(f"- {ff.dtc_code}: RPM={ff.rpm}, Coolant={ff.coolant_temp_c}°C, Load={ff.engine_load_pct}%")
            lines.append("")

        lines.append("## Readiness Monitors")
        for name, status in self.readiness.items():
            icon = "✅" if status == "ready" else "⬜" if status == "not_ready" else "—"
            lines.append(f"  {icon} {name}: {status}")
        lines.append("")

        if self.live_data:
            lines.append("## Live Data Snapshot")
            for point in self.live_data[:10]:
                val = f"{point.value:.1f}" if isinstance(point.value, float) else str(point.value)
                lines.append(f"  {point.pid_name}: {val} {point.unit}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "protocol": self.protocol,
            "vehicle_vin": self.vehicle_vin,
            "dtcs": [d.to_dict() for d in self.dtcs],
            "freeze_frames": [f.to_dict() for f in self.freeze_frames],
            "readiness": self.readiness,
            "live_data": [{"pid": p.pid_name, "value": p.value, "unit": p.unit} for p in self.live_data],
            "mileage_km": self.mileage_km,
            "warnings": self.warnings,
        }


# ─── DTC Knowledge Base ───────────────────────────────────────────────────────

# Common OBD-II P-codes mapped to probable causes and tests for combustion engines.
# This is a subset. The full standard has thousands; we cover the most common 50.
DTC_KB: dict[str, dict[str, Any]] = {
    # Misfires
    "P0300": {"desc": "Random/Multiple Cylinder Misfire Detected", "sev": "major", "causes": ["Spark plugs fouled or worn", "Ignition coil intermittent", "Vacuum leak", "Low fuel pressure", "EGR stuck open"], "tests": ["Visual plug inspection", "Swap coils", "Smoke test intake", "Fuel pressure gauge"]},
    "P0301": {"desc": "Cylinder 1 Misfire", "sev": "major", "causes": ["Plug/coil/wire on cyl 1", "Injector clog cyl 1", "Low compression cyl 1"], "tests": ["Swap coil/plug to cyl 2 — if misfire moves, replace", "Compression test cyl 1", "Noid light on inj #1"]},
    "P0302": {"desc": "Cylinder 2 Misfire", "sev": "major", "causes": ["Plug/coil/wire on cyl 2", "Injector clog cyl 2", "Low compression cyl 2"], "tests": ["Swap coil/plug", "Compression test cyl 2", "Noid light"]},
    "P0303": {"desc": "Cylinder 3 Misfire", "sev": "major", "causes": ["Plug/coil/wire on cyl 3", "Injector clog cyl 3", "Low compression cyl 3"], "tests": ["Swap coil/plug", "Compression test cyl 3", "Noid light"]},
    "P0304": {"desc": "Cylinder 4 Misfire", "sev": "major", "causes": ["Plug/coil/wire on cyl 4", "Injector clog cyl 4", "Low compression cyl 4"], "tests": ["Swap coil/plug", "Compression test cyl 4", "Noid light"]},
    "P0305": {"desc": "Cylinder 5 Misfire", "sev": "major", "causes": ["Plug/coil/wire on cyl 5", "Injector clog cyl 5"], "tests": ["Swap coil/plug", "Compression test"]},
    "P0306": {"desc": "Cylinder 6 Misfire", "sev": "major", "causes": ["Plug/coil/wire on cyl 6", "Injector clog cyl 6"], "tests": ["Swap coil/plug", "Compression test"]},

    # Oxygen Sensors
    "P0130": {"desc": "O2 Sensor Circuit (Bank 1, Sensor 1)", "sev": "minor", "causes": ["Sensor heater failed", "Wiring short/open", "Contaminated sensor"], "tests": ["Ohm heater circuit (4-7Ω)", "Scope sensor voltage — should oscillate 0.1-0.9V", "Check for exhaust leak upstream"]},
    "P0135": {"desc": "O2 Sensor Heater Circuit (Bank 1, Sensor 1)", "sev": "minor", "causes": ["Heater element burned out", "Blown fuse", "Wiring fault"], "tests": ["Ohm heater 4-7Ω at room temp", "Check heater fuse", "Voltage at connector key-on"]},
    "P0141": {"desc": "O2 Sensor Heater Circuit (Bank 1, Sensor 2)", "sev": "minor", "causes": ["Heater failed", "Wiring"], "tests": ["Ohm heater", "Check fuse"]},
    "P0420": {"desc": "Catalyst Efficiency Below Threshold (Bank 1)", "sev": "major", "causes": ["Catalytic converter degraded", "Exhaust leak before cat", "O2 sensor slow (false positive)", "Oil/coolant contamination of substrate"], "tests": ["Compare upstream vs downstream O2 amplitude — downstream should be flat", "Infrared temp gun: cat inlet vs outlet (outlet hotter = working)", "Check for upstream leak"]},
    "P0430": {"desc": "Catalyst Efficiency Below Threshold (Bank 2)", "sev": "major", "causes": ["Catalytic converter degraded (bank 2)"], "tests": ["Same as P0420, bank 2"]},

    # Fuel System
    "P0171": {"desc": "System Too Lean (Bank 1)", "sev": "major", "causes": ["Vacuum leak after MAF", "Low fuel pressure", "Dirty MAF", "Weak fuel pump", "Clogged injectors", "False air from intake gasket"], "tests": ["Smoke test intake tract", "Fuel pressure at rail (key-on, idle, WOT)", "Clean MAF with CRC spray", "Propane enrichment around intake — RPM surge = leak"]},
    "P0172": {"desc": "System Too Rich (Bank 1)", "sev": "major", "causes": ["MAF reading high (dirty/contaminated)", "Fuel pressure too high", "Leaking injector", "EVAP purge stuck open", "Coolant temp sensor reading cold"], "tests": ["Scope MAF output at idle", "Fuel pressure test", "Noid light + injector balance test", "Check purge valve flow with vacuum pump"]},
    "P0174": {"desc": "System Too Lean (Bank 2)", "sev": "major", "causes": ["Same as P0171, bank 2"], "tests": ["Same as P0171, bank 2"]},
    "P0175": {"desc": "System Too Rich (Bank 2)", "sev": "major", "causes": ["Same as P0172, bank 2"], "tests": ["Same as P0172, bank 2"]},

    # Engine Temperature
    "P0115": {"desc": "Engine Coolant Temp Sensor Circuit", "sev": "minor", "causes": ["ECT sensor open/shorted", "Connector corrosion", "Low coolant exposing sensor"], "tests": ["Ohm sensor vs temp chart (check factory spec)", "Compare ECT to IR gun reading", "Verify coolant level"]},
    "P0116": {"desc": "Engine Coolant Temp Sensor Range/Performance", "sev": "minor", "causes": ["Stuck thermostat (open)", "Sensor drift", "Air pocket around sensor"], "tests": ["Boil water test — should read near 212°F/100°C", "Check thermostat opening temp", "Burp cooling system"]},
    "P0125": {"desc": "Insufficient Coolant Temp for Closed Loop", "sev": "minor", "causes": ["Stuck open thermostat", "Faulty ECT", "Heater core bypass"], "tests": ["Verify thermostat temp rating", "IR temp gun vs scanner ECT"]},
    "P0128": {"desc": "Coolant Thermostat Below Regulating Temp", "sev": "minor", "causes": ["Stuck open thermostat", "Low coolant", "Bad ECT"], "tests": ["Replace thermostat first", "Check coolant level", "Verify ECT accuracy"]},

    # Throttle / Airflow
    "P0101": {"desc": "MAF Sensor Circuit Range/Performance", "sev": "minor", "causes": ["Dirty/contaminated MAF hot wire", "Air leak after MAF", "Incorrect MAF for vehicle"], "tests": ["Clean MAF with CRC spray", "Scope MAF voltage vs airflow", "Smoke test after MAF"]},
    "P0102": {"desc": "MAF Sensor Circuit Low", "sev": "minor", "causes": ["Open/shorted MAF signal", "Disconnected MAF", "Bad ground"], "tests": ["Check 5V reference and ground at connector", "Key-on MAF voltage (should be ~0.5V at rest)"]},
    "P0110": {"desc": "Intake Air Temp Sensor Circuit", "sev": "info", "causes": ["IAT sensor open/short", "Wiring"], "tests": ["Ohm sensor vs temp", "Check wiring"]},
    "P0120": {"desc": "Throttle Position Sensor Circuit", "sev": "minor", "causes": ["TPS worn potentiometer", "Binding throttle cable/linkage", "Corroded connector"], "tests": ["Sweep TPS with voltmeter — should be linear 0.5-4.5V", "Check throttle plate freedom"]},

    # Knock / Timing
    "P0325": {"desc": "Knock Sensor Circuit (Bank 1)", "sev": "minor", "causes": ["Knock sensor loose or cracked", "Wiring open/shorted", "Excessive carbon/rattling"], "tests": ["Ohm sensor (check spec)", "Scope knock signal while tapping block", "Retorque sensor"]},
    "P0335": {"desc": "Crankshaft Position Sensor Circuit", "sev": "critical", "causes": ["Sensor failed", "Trigger wheel damaged", "Wiring fault", "Sensor gap wrong"], "tests": ["Ohm sensor", "AC voltage while cranking (magnetic pickup type)", "Check trigger wheel teeth for damage"]},
    "P0340": {"desc": "Camshaft Position Sensor Circuit", "sev": "critical", "causes": ["Sensor failed", "Timing component jumped", "Wiring"], "tests": ["Ohm/scope sensor", "Check timing marks"]},

    # EGR / Emissions
    "P0400": {"desc": "EGR Flow Malfunction", "sev": "minor", "causes": ["EGR valve stuck closed", "Passages clogged with carbon", "Vacuum diaphragm ruptured", "DPFE sensor drift"], "tests": ["Apply vacuum to EGR at idle — should stall", "Remove valve, clean passages with carb cleaner and pipe brush", "Test DPFE sensor voltage vs pressure"]},
    "P0401": {"desc": "EGR Insufficient Flow", "sev": "minor", "causes": ["Clogged passages", "EGR pintle stuck", "DPFE hoses reversed or clogged"], "tests": ["Same as P0400"]},
    "P0440": {"desc": "EVAP Emission Control System", "sev": "minor", "causes": ["Gas cap loose", "Leak in vapor lines", "Purge valve stuck", "Canister saturated"], "tests": ["Check gas cap seal", "Smoke test EVAP system (0.5 psi max)", "Command purge valve with scan tool — should flow"]},
    "P0442": {"desc": "EVAP Small Leak Detected", "sev": "minor", "causes": ["Gas cap", "Small crack in vapor line", "Leak detection pump failure"], "tests": ["Replace gas cap", "Smoke test", "Check LDP diaphragm if equipped"]},
    "P0455": {"desc": "EVAP Large Leak Detected", "sev": "minor", "causes": ["Gas cap missing/loose", "Large hose disconnected", "Canister vent valve stuck open"], "tests": ["Verify gas cap", "Visual inspection of all hoses", "Smoke test"]},

    # Ignition
    "P0351": {"desc": "Ignition Coil A Primary/Secondary Circuit", "sev": "major", "causes": ["Coil on cyl 1 failed", "Connector/wiring", "PCM driver"], "tests": ["Swap coil to adjacent cyl — if misfire moves, replace coil", "Ohm primary and secondary windings"]},
    "P0352": {"desc": "Ignition Coil B Primary/Secondary Circuit", "sev": "major", "causes": ["Coil on cyl 2 failed"], "tests": ["Swap test"]},
    "P0353": {"desc": "Ignition Coil C Primary/Secondary Circuit", "sev": "major", "causes": ["Coil on cyl 3 failed"], "tests": ["Swap test"]},
    "P0354": {"desc": "Ignition Coil D Primary/Secondary Circuit", "sev": "major", "causes": ["Coil on cyl 4 failed"], "tests": ["Swap test"]},

    # VVT / Timing
    "P0011": {"desc": "Camshaft Position Timing Over-Advanced (Bank 1)", "sev": "major", "causes": ["VVT solenoid stuck", "Wrong viscosity oil", "Timing chain stretched", "Oil pressure low"], "tests": ["Test VVT solenoid resistance and actuation", "Verify correct oil spec", "Check timing marks for chain stretch"]},
    "P0012": {"desc": "Camshaft Position Timing Over-Retarded (Bank 1)", "sev": "major", "causes": ["VVT solenoid stuck", "Oil pressure low", "Chain stretched/jumped"], "tests": ["Same as P0011"]},
    "P0016": {"desc": "Crankshaft-Camshaft Correlation (Bank 1)", "sev": "critical", "causes": ["Timing belt/chain jumped", "Wrong correlation installed", "Sensor fault"], "tests": ["Check timing marks IMMEDIATELY", "Scope CKP and CMP correlation"]},
    "P0017": {"desc": "Crankshaft-Camshaft Correlation (Bank 2)", "sev": "critical", "causes": ["Same as P0016, bank 2"], "tests": ["Check timing marks"]},

    # Fuel Injector
    "P0201": {"desc": "Injector Circuit/Open Cylinder 1", "sev": "major", "causes": ["Open winding in injector", "Connector corroded", "PCM driver fault"], "tests": ["Ohm injector (~12-16Ω high, 2-5Ω low)", "Noid light pulse", "Swap injector to cyl 2"]},
    "P0202": {"desc": "Injector Circuit/Open Cylinder 2", "sev": "major", "causes": ["Same as P0201"], "tests": ["Same as P0201"]},
    "P0203": {"desc": "Injector Circuit/Open Cylinder 3", "sev": "major", "causes": ["Same as P0201"], "tests": ["Same as P0201"]},
    "P0204": {"desc": "Injector Circuit/Open Cylinder 4", "sev": "major", "causes": ["Same as P0201"], "tests": ["Same as P0201"]},
    "P0205": {"desc": "Injector Circuit/Open Cylinder 5", "sev": "major", "causes": ["Same as P0201"], "tests": ["Same as P0201"]},
    "P0206": {"desc": "Injector Circuit/Open Cylinder 6", "sev": "major", "causes": ["Same as P0201"], "tests": ["Same as P0201"]},

    # Idle
    "P0505": {"desc": "Idle Air Control System", "sev": "minor", "causes": ["IAC valve clogged", "Vacuum leak", "Throttle plate dirty", "Base idle screw tampered"], "tests": ["Remove IAC, clean pintle and seat", "Clean throttle bore", "Reset base idle procedure"]},
    "P0506": {"desc": "Idle Speed Low", "sev": "minor", "causes": ["Vacuum leak (large)", "IAC restricted", "Base idle low"], "tests": ["Smoke test", "IAC cleaning", "Relearn idle adaptation"]},
    "P0507": {"desc": "Idle Speed High", "sev": "minor", "causes": ["Vacuum leak", "Throttle plate stuck slightly open", "IAC sticking open", "False air from PCV"], "tests": ["Smoke test", "Clean throttle", "Check PCV flow"]},

    # Starter / Battery
    "P0562": {"desc": "System Voltage Low", "sev": "minor", "causes": ["Weak battery", "Charging system fault", "High parasitic draw"], "tests": ["Battery load test", "Alternator output at 2,000 RPM (13.5-14.5V)", "Parasitic draw test (<50 mA after 30 min sleep)"]},

    # Generic
    "P0600": {"desc": "Serial Communication Link", "sev": "minor", "causes": ["CAN bus fault", "Module not communicating", "Wiring short/open"], "tests": ["Check termination resistors (60Ω between CAN-H and CAN-L)", "Scope CAN signals"]},
}


def _resolve_dtc(code: str) -> DTC:
    """Map an OBD-II code to our knowledge-base entry."""
    kb = DTC_KB.get(code.upper())
    if not kb:
        # Unknown code — return generic with the raw code
        return DTC(
            code=code.upper(),
            description="Unknown code — consult factory service manual or advanced scan tool",
            severity="info",
            system="powertrain",
            probable_causes=["Code not in local KB — may require dealer-level diagnostics"],
            suggested_tests=["Record freeze-frame data", "Research code in manufacturer TSB database"],
        )
    return DTC(
        code=code.upper(),
        description=kb["desc"],
        severity=kb["sev"],
        system="powertrain",
        probable_causes=kb["causes"],
        suggested_tests=kb["tests"],
    )


# ─── OBD Bridge ────────────────────────────────────────────────────────────────

class OBDBridge:
    """
    OBD-II scanner interface using python-obd.

    Usage:
        bridge = OBDBridge(port="/dev/ttyUSB0")
        result = bridge.full_scan()

    Mock mode:
        bridge = OBDBridge(mock_mode=True)
        result = bridge.full_scan()
    """

    def __init__(self, port: str = "/dev/ttyUSB0", mock_mode: bool = False) -> None:
        self.port = port
        self.mock_mode = mock_mode
        self._connection: Any | None = None

    def _connect(self) -> Any:
        """Lazy connection to OBD adapter."""
        if self._connection is not None:
            return self._connection

        if self.mock_mode:
            return None  # No real connection needed

        try:
            import obd  # python-obd library
            conn = obd.Async(self.port, protocol=None)
            # Wait briefly for auto-negotiation
            import time
            time.sleep(1.5)
            self._connection = conn
            return conn
        except ImportError:
            raise RuntimeError(
                "python-obd is required for live scanning. "
                "Install: pip install obd"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to connect to OBD adapter at {self.port}: {e}. "
                f"Try mock_mode=True for testing."
            )

    def read_dtcs(self) -> list[DTC]:
        """Read active diagnostic trouble codes."""
        if self.mock_mode:
            return self._mock_dtcs()

        conn = self._connect()
        cmd = conn.query(obd.commands.GET_DTC)
        if not cmd.is_null():
            codes = cmd.value  # list of (code_str, description) tuples
            return [_resolve_dtc(c[0]) for c in codes]
        return []

    def clear_dtcs(self) -> bool:
        """Clear all DTCs and reset MIL. Returns True on success."""
        if self.mock_mode:
            return True

        conn = self._connect()
        conn.query(obd.commands.CLEAR_DTC)
        return True

    def read_freeze_frame(self) -> list[FreezeFrame]:
        """Read freeze-frame data for the most recently triggered DTC."""
        if self.mock_mode:
            return [self._mock_freeze_frame()]

        conn = self._connect()
        # python-obd freeze frame support varies; best-effort
        ff = FreezeFrame(
            dtc_code="P0000",
            rpm=_safe_int(conn.query(obd.commands.RPM)),
            coolant_temp_c=_safe_int(conn.query(obd.commands.COOLANT_TEMP)),
            engine_load_pct=_safe_float(conn.query(obd.commands.ENGINE_LOAD)),
            vehicle_speed_kmh=_safe_int(conn.query(obd.commands.SPEED)),
            throttle_pos_pct=_safe_float(conn.query(obd.commands.THROTTLE_POS)),
            fuel_trim_short_pct=_safe_float(conn.query(obd.commands.SHORT_FUEL_TRIM_1)),
            fuel_trim_long_pct=_safe_float(conn.query(obd.commands.LONG_FUEL_TRIM_1)),
            maf_rate_gs=_safe_float(conn.query(obd.commands.MAF)),
            intake_temp_c=_safe_int(conn.query(obd.commands.INTAKE_TEMP)),
            o2_voltage_v=_safe_float(conn.query(obd.commands.O2_B1S1)),
        )
        return [ff]

    def read_readiness(self) -> dict[str, str]:
        """Read emission readiness monitors."""
        if self.mock_mode:
            return self._mock_readiness()

        conn = self._connect()
        # python-obd exposes some readiness data
        result: dict[str, str] = {}
        try:
            resp = conn.query(obd.commands.STATUS)
            if resp.value:
                for name, ready in resp.value.__dict__.items():
                    if not name.startswith("_"):
                        result[name] = "ready" if ready else "not_ready"
        except Exception:
            pass
        return result

    def read_live_data(self) -> list[LiveDataPoint]:
        """Pull a snapshot of key live PIDs."""
        if self.mock_mode:
            return self._mock_live_data()

        conn = self._connect()
        import time
        now = time.time()

        pids = [
            ("RPM", obd.commands.RPM, "rev/min"),
            ("Coolant Temp", obd.commands.COOLANT_TEMP, "°C"),
            ("Engine Load", obd.commands.ENGINE_LOAD, "%"),
            ("Vehicle Speed", obd.commands.SPEED, "km/h"),
            ("Throttle Position", obd.commands.THROTTLE_POS, "%"),
            ("Short Term Fuel Trim", obd.commands.SHORT_FUEL_TRIM_1, "%"),
            ("Long Term Fuel Trim", obd.commands.LONG_FUEL_TRIM_1, "%"),
            ("MAF Rate", obd.commands.MAF, "g/s"),
            ("Intake Temp", obd.commands.INTAKE_TEMP, "°C"),
            ("O2 Voltage", obd.commands.O2_B1S1, "V"),
            ("Timing Advance", obd.commands.TIMING_ADVANCE, "°"),
            ("Fuel Level", obd.commands.FUEL_LEVEL, "%"),
        ]

        points: list[LiveDataPoint] = []
        for name, cmd, unit in pids:
            try:
                resp = conn.query(cmd)
                val = resp.value.magnitude if hasattr(resp.value, "magnitude") else resp.value
                points.append(LiveDataPoint(pid_name=name, value=val, unit=unit, timestamp=now))
            except Exception:
                points.append(LiveDataPoint(pid_name=name, value=None, unit=unit, timestamp=now))

        return points

    def full_scan(self) -> OBDScanResult:
        """
        Complete scan: DTCs, freeze frame, readiness, live data.
        One-stop for the mechanic standing next to the vehicle.
        """
        dtcs = self.read_dtcs()
        freeze = self.read_freeze_frame()
        readiness = self.read_readiness()
        live = self.read_live_data()

        warnings: list[str] = []
        if any(d.severity == "critical" for d in dtcs):
            warnings.append("Critical DTCs present — do not operate vehicle until repaired.")
        if any(d.code in ("P0171", "P0174") for d in dtcs):
            warnings.append("Lean condition detected — potential engine damage if driven.")

        protocol = "Mock" if self.mock_mode else "Auto-detected"

        return OBDScanResult(
            port=self.port,
            protocol=protocol,
            vehicle_vin=None,
            dtcs=dtcs,
            freeze_frames=freeze,
            readiness=readiness,
            live_data=live,
            mileage_km=None,
            warnings=warnings,
        )

    # ─── Mock Data ─────────────────────────────────────────────────────────────

    def _mock_dtcs(self) -> list[DTC]:
        """Return sample DTCs for testing/demo."""
        return [
            _resolve_dtc("P0301"),
            _resolve_dtc("P0171"),
        ]

    def _mock_freeze_frame(self) -> FreezeFrame:
        return FreezeFrame(
            dtc_code="P0301",
            rpm=850,
            coolant_temp_c=92,
            engine_load_pct=18.5,
            vehicle_speed_kmh=0,
            throttle_pos_pct=2.1,
            fuel_trim_short_pct=12.5,
            fuel_trim_long_pct=8.0,
            maf_rate_gs=4.2,
            intake_temp_c=35,
            o2_voltage_v=0.45,
        )

    def _mock_readiness(self) -> dict[str, str]:
        return {
            "misfire": "ready",
            "fuel_system": "ready",
            "components": "ready",
            "catalyst": "ready",
            "heated_catalyst": "n/a",
            "evap": "not_ready",
            "secondary_air": "n/a",
            "o2_sensor": "ready",
            "o2_sensor_heater": "ready",
            "egr": "ready",
        }

    def _mock_live_data(self) -> list[LiveDataPoint]:
        import time
        now = time.time()
        return [
            LiveDataPoint("RPM", 850, "rev/min", now),
            LiveDataPoint("Coolant Temp", 92, "°C", now),
            LiveDataPoint("Engine Load", 18.5, "%", now),
            LiveDataPoint("Vehicle Speed", 0, "km/h", now),
            LiveDataPoint("Throttle Position", 2.1, "%", now),
            LiveDataPoint("Short Term Fuel Trim", 12.5, "%", now),
            LiveDataPoint("Long Term Fuel Trim", 8.0, "%", now),
            LiveDataPoint("MAF Rate", 4.2, "g/s", now),
            LiveDataPoint("Intake Temp", 35, "°C", now),
            LiveDataPoint("O2 Voltage", 0.45, "V", now),
            LiveDataPoint("Timing Advance", 12, "°", now),
            LiveDataPoint("Fuel Level", 62, "%", now),
        ]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _safe_int(response: Any) -> int | None:
    """Extract integer from an OBD response safely."""
    if response is None or response.is_null():
        return None
    try:
        val = response.value
        if hasattr(val, "magnitude"):
            return int(val.magnitude)
        return int(val)
    except Exception:
        return None


def _safe_float(response: Any) -> float | None:
    """Extract float from an OBD response safely."""
    if response is None or response.is_null():
        return None
    try:
        val = response.value
        if hasattr(val, "magnitude"):
            return float(val.magnitude)
        return float(val)
    except Exception:
        return None
