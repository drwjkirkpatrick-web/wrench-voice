"""
repair_workflow.py
==================
Step-by-step repair guidance with tool matching, fastener tracking,
and real-time progress prediction for the mechanic.

WHY:
A mechanic on a lift needs:
1. What tool NOW — not a wall-of-text manual
2. What fastener size NOW — not "remove bolts"
3. What safety warning BEFORE they do it
4. Where they ARE in the job — did they already drained coolant?
5. What's NEXT — before they waste 5 minutes staring at the engine

HOW:
- RepairWorkflow = a complete procedure (e.g. "Water pump + timing belt on 5S-FE")
- RepairStep = one atomic action with exact tools, fasteners, torque, warnings
- WorkflowTracker = state machine tracking current step, completed steps, predictions
- ToolMatcher = resolves generic tool names into exact sizes for a specific vehicle
- FastenerSpec = bolt/nut/screw with size, drive type, thread pitch, torque, quantity

EXAMPLE — 1998 Camry water pump + timing belt:
    tracker = WorkflowTracker.for_procedure("toyota_5sfe", "water_pump_timing_belt")
    while tracker.has_next():
        step = tracker.current_step()
        print(step.tools_needed)      # ["10mm socket", "ratchet", "torque wrench"]
        print(step.fasteners)         # [FastenerSpec("M6×1.0", "10mm hex", 14ft-lb, qty=6)]
        tracker.advance()             # marks complete, predicts next
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class FastenerSpec:
    """One bolt, nut, screw, or clip with exact sizing."""
    description: str           # e.g. "Water pump bolt (upper)"
    size: str                  # e.g. "M6×1.0" or "3/8-16" or "10mm socket"
    drive: str                 # e.g. "10mm hex", "12mm socket", "Phillips #2"
    torque_ft_lbs: float | None = None
    torque_nm: float | None = None
    torque_type: str = "standard"  # standard | TTY | angle | hand-tight
    quantity: int = 1
    location: str = ""         # e.g. "front of pump, 12 o'clock"
    notes: str = ""            # e.g. "Thread-locker pre-applied", "Replace — TTY"

    def torque_str(self) -> str:
        if self.torque_ft_lbs is None:
            return "hand-tight"
        if self.torque_nm:
            return f"{self.torque_ft_lbs} ft-lb / {self.torque_nm} Nm"
        return f"{self.torque_ft_lbs} ft-lb"


@dataclass
class RepairStep:
    """One atomic action in a repair workflow."""
    step_number: int
    title: str
    description: str
    required_tools: list[str] = field(default_factory=list)
    fasteners: list[FastenerSpec] = field(default_factory=list)
    estimated_time_min: int = 5
    safety_warnings: list[str] = field(default_factory=list)
    substeps: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)  # step_numbers that must precede
    produces: list[str] = field(default_factory=list)   # what this step yields ("coolant drained", "belt off")
    inspection_notes: list[str] = field(default_factory=list)
    image_hints: list[str] = field(default_factory=list)  # descriptions of what to look for

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fasteners"] = [asdict(f) for f in self.fasteners]
        return d


@dataclass
class RepairWorkflow:
    """A complete repair procedure for one symptom on one engine family."""
    slug: str                  # e.g. "toyota_5sfe__water_pump_timing_belt"
    engine_slug: str
    symptom: str
    title: str
    description: str
    skill_level: str           # beginner | intermediate | advanced
    estimated_total_time_min: int
    steps: list[RepairStep]
    required_tools_summary: list[str] = field(default_factory=list)
    consumables: list[str] = field(default_factory=list)
    prerequisite_checks: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    related_procedures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "engine_slug": self.engine_slug,
            "symptom": self.symptom,
            "title": self.title,
            "description": self.description,
            "skill_level": self.skill_level,
            "estimated_total_time_min": self.estimated_total_time_min,
            "steps": [s.to_dict() for s in self.steps],
            "required_tools_summary": self.required_tools_summary,
            "consumables": self.consumables,
            "prerequisite_checks": self.prerequisite_checks,
            "cautions": self.cautions,
            "related_procedures": self.related_procedures,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            f"**Engine:** {self.engine_slug}  |  **Symptom:** {self.symptom}",
            f"**Skill:** {self.skill_level}  |  **Est. time:** {self.estimated_total_time_min} min",
            "",
        ]
        if self.cautions:
            lines.append("## ⚠️ Cautions")
            for c in self.cautions:
                lines.append(f"- {c}")
            lines.append("")
        if self.prerequisite_checks:
            lines.append("## Pre-Flight Checks")
            for p in self.prerequisite_checks:
                lines.append(f"- [ ] {p}")
            lines.append("")
        lines.append("## Tools Required")
        for t in self.required_tools_summary:
            lines.append(f"- {t}")
        lines.append("")
        lines.append("## Consumables")
        for c in self.consumables:
            lines.append(f"- {c}")
        lines.append("")
        for step in self.steps:
            lines.append(f"### Step {step.step_number}: {step.title}")
            lines.append(step.description)
            if step.safety_warnings:
                lines.append("")
                for w in step.safety_warnings:
                    lines.append(f"⚠️ {w}")
            if step.required_tools:
                lines.append(f"**Tools:** {', '.join(step.required_tools)}")
            if step.fasteners:
                lines.append("")
                lines.append("**Fasteners:**")
                for f in step.fasteners:
                    lines.append(f"  - {f.description}: {f.drive} → {f.torque_str()} ({f.quantity}×)")
            if step.substeps:
                lines.append("")
                for ss in step.substeps:
                    lines.append(f"  1. {ss}")
            if step.inspection_notes:
                lines.append("")
                for i in step.inspection_notes:
                    lines.append(f"🔍 {i}")
            lines.append("")
        return "\n".join(lines)


# ─── Tool Matcher ─────────────────────────────────────────────────────────────

class ToolMatcher:
    """
    Resolve generic tool requirements into exact sizes for a vehicle.

    Example:
        matcher = ToolMatcher("toyota_5sfe")
        matcher.resolve("socket set") -> ["10mm socket", "12mm socket", "14mm socket", "17mm socket"]
    """

    # Engine-family-specific tool size mappings
    _FAMILY_TOOLS: dict[str, dict[str, list[str]]] = {
        "toyota_5sfe": {
            "socket set": ["10mm socket", "12mm socket", "14mm socket", "17mm socket", "19mm socket"],
            "wrench set": ["10mm wrench", "12mm wrench", "14mm wrench", "17mm wrench"],
            "torque critical": ["3/8 torque wrench (10–100 ft-lb)", "angle gauge (for TTY bolts)"],
            "timing belt": ["crank pulley holder tool"],
            "coolant system": ["catch pan (≥3 gal)", "funnel", "hose clamp pliers"],
            "general": ["ratchet (3/8)", "extensions (3, 6, 10 in)", "universal joint", "magnetic pickup"],
        },
        "subaru_ej25_sohc": {
            "socket set": ["10mm socket", "12mm socket", "14mm socket", "17mm socket", "19mm socket", "22mm socket"],
            "wrench set": ["10mm wrench", "12mm wrench", "14mm wrench"],
            "torque critical": ["1/2 torque wrench (20–150 ft-lb)", "angle gauge"],
            "head gasket": ["Subaru cam sprocket holder", "Subaru crank holder", "RTV gun"],
            "timing belt": ["Subaru belt tensioner tool (or 3/8 ratchet + stubby)"],
            "coolant system": ["catch pan (≥4 gal)", "spill-free funnel"],
            "general": ["ratchet (3/8, 1/2)", "extensions", "magnetic pickup", "brake clean"],
        },
        "honda_j_series": {
            "socket set": ["10mm socket", "12mm socket", "14mm socket", "17mm socket", "19mm socket"],
            "wrench set": ["10mm wrench", "12mm wrench", "14mm wrench"],
            "torque critical": ["3/8 torque wrench", "angle gauge"],
            "timing belt": ["Honda crank pulley holder", "cam holder (B18 tool or equivalent)"],
            "coolant system": ["catch pan (≥3 gal)", "funnel"],
            "general": ["ratchet (3/8)", "extensions", "magnetic pickup"],
        },
        "ford_73_powerstroke": {
            "socket set": ["8mm socket", "10mm socket", "13mm socket", "15mm socket", "18mm socket"],
            "wrench set": ["8mm wrench", "10mm wrench", "13mm wrench", "15mm wrench"],
            "torque critical": ["1/2 torque wrench (50–250 ft-lb)", "1 torque wrench (50–250 ft-lb)"],
            "diesel": ["compression tester (diesel adapter)", "fuel pressure gauge"],
            "general": ["ratchet (3/8, 1/2)", "breaker bar", "extensions"],
        },
    }

    _GENERIC_TOOLS: dict[str, list[str]] = {
        "socket set": ["10mm socket", "12mm socket", "14mm socket", "17mm socket"],
        "wrench set": ["10mm wrench", "12mm wrench", "14mm wrench"],
        "torque critical": ["3/8 torque wrench"],
        "general": ["ratchet (3/8)", "extensions", "magnetic pickup"],
    }

    def __init__(self, engine_slug: str) -> None:
        self.engine_slug = engine_slug
        self.family_tools = self._FAMILY_TOOLS.get(engine_slug, self._GENERIC_TOOLS)

    def resolve(self, generic_tool: str) -> list[str]:
        """Resolve a generic tool category into specific tools."""
        generic = generic_tool.lower().strip()
        if generic in self.family_tools:
            return list(self.family_tools[generic])
        # Try substring match
        for key, tools in self.family_tools.items():
            if generic in key or key in generic:
                return list(tools)
        return [generic_tool]  # Passthrough if unknown

    def resolve_all(self, generics: list[str]) -> list[str]:
        """Resolve a list of generic tools into specific ones, deduped."""
        seen: set[str] = set()
        out: list[str] = []
        for g in generics:
            for t in self.resolve(g):
                if t not in seen:
                    seen.add(t)
                    out.append(t)
        return out


# ─── Workflow Tracker ───────────────────────────────────────────────────────────

@dataclass
class TrackerState:
    """Serializable state of a repair in progress."""
    workflow_slug: str
    current_step_idx: int = 0
    completed_steps: list[int] = field(default_factory=list)
    skipped_steps: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)  # e.g. {"coolant_drained": True}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkflowTracker:
    """
    Tracks a mechanic's progress through a RepairWorkflow.
    Predicts next tools, next fasteners, and upcoming warnings.
    """

    def __init__(self, workflow: RepairWorkflow) -> None:
        self.workflow = workflow
        self.state = TrackerState(workflow_slug=workflow.slug)
        self.tool_matcher = ToolMatcher(workflow.engine_slug)

    @classmethod
    def for_procedure(cls, engine_slug: str, symptom: str,
                      registry: RepairWorkflowRegistry | None = None) -> WorkflowTracker:
        """Factory: load a workflow from registry by engine + symptom."""
        reg = registry or RepairWorkflowRegistry()
        wf = reg.get(engine_slug, symptom)
        if wf is None:
            raise ValueError(f"No workflow registered for {engine_slug} + {symptom}")
        return cls(wf)

    # ─── Navigation ──────────────────────────────────────────────────────────────

    @property
    def current_step(self) -> RepairStep | None:
        if 0 <= self.state.current_step_idx < len(self.workflow.steps):
            return self.workflow.steps[self.state.current_step_idx]
        return None

    def has_next(self) -> bool:
        return self.state.current_step_idx < len(self.workflow.steps)

    def advance(self) -> RepairStep | None:
        """Mark current step complete and move to next."""
        if self.current_step:
            self.state.completed_steps.append(self.current_step.step_number)
            # Set flags from step produces
            for p in self.current_step.produces:
                self.state.flags[p] = True
        self.state.current_step_idx += 1
        return self.current_step

    def go_back(self) -> RepairStep | None:
        """Move to previous step (for re-do)."""
        if self.state.current_step_idx > 0:
            self.state.current_step_idx -= 1
            # Un-complete if we went back to it
            if self.current_step and self.current_step.step_number in self.state.completed_steps:
                self.state.completed_steps.remove(self.current_step.step_number)
        return self.current_step

    def skip(self, reason: str = "") -> RepairStep | None:
        """Skip current step (e.g. already done)."""
        if self.current_step:
            self.state.skipped_steps.append(self.current_step.step_number)
            if reason:
                self.state.notes.append(f"Skipped step {self.current_step.step_number}: {reason}")
        self.state.current_step_idx += 1
        return self.current_step

    # ─── Predictions ─────────────────────────────────────────────────────────────

    def predict_next_tools(self, lookahead: int = 3) -> list[str]:
        """What tools will be needed in the next N steps?"""
        tools: set[str] = set()
        start = self.state.current_step_idx
        for step in self.workflow.steps[start: start + lookahead]:
            tools.update(step.required_tools)
        return self.tool_matcher.resolve_all(sorted(tools))

    def predict_next_fasteners(self, lookahead: int = 3) -> list[FastenerSpec]:
        """What fasteners are coming up in the next N steps?"""
        out: list[FastenerSpec] = []
        start = self.state.current_step_idx
        for step in self.workflow.steps[start: start + lookahead]:
            out.extend(step.fasteners)
        return out

    def predict_next_warning(self) -> str | None:
        """The most urgent safety warning in upcoming steps."""
        start = self.state.current_step_idx
        for step in self.workflow.steps[start:]:
            if step.safety_warnings:
                return step.safety_warnings[0]
        return None

    def predict_time_remaining(self) -> int:
        """Sum estimated time for all remaining steps."""
        start = self.state.current_step_idx
        return sum(s.estimated_time_min for s in self.workflow.steps[start:])

    def is_prerequisite_met(self, check: str) -> bool:
        """Has a prerequisite flag been set?"""
        return self.state.flags.get(check, False)

    def progress_pct(self) -> float:
        total = len(self.workflow.steps)
        done = len(self.state.completed_steps) + len(self.state.skipped_steps)
        return (done / total * 100) if total else 0.0

    def status_summary(self) -> dict[str, Any]:
        step = self.current_step
        return {
            "workflow": self.workflow.slug,
            "progress_pct": round(self.progress_pct(), 1),
            "current_step": step.step_number if step else None,
            "current_title": step.title if step else "DONE",
            "time_remaining_min": self.predict_time_remaining(),
            "next_tools": self.predict_next_tools(2),
            "next_fasteners": [
                {"desc": f.description, "drive": f.drive, "torque": f.torque_str()}
                for f in self.predict_next_fasteners(2)
            ],
            "next_warning": self.predict_next_warning(),
            "prerequisites_met": dict(self.state.flags),
        }


# ─── Workflow Registry ──────────────────────────────────────────────────────────

class RepairWorkflowRegistry:
    """
    In-memory store of RepairWorkflow instances.
    In production, load from JSON/YAML files in workflows/*.json
    """

    def __init__(self) -> None:
        self._workflows: dict[str, RepairWorkflow] = {}
        self._build_default_workflows()

    def register(self, workflow: RepairWorkflow) -> None:
        self._workflows[workflow.slug] = workflow

    def get(self, engine_slug: str, symptom: str) -> RepairWorkflow | None:
        key = f"{engine_slug}__{symptom}"
        return self._workflows.get(key)

    def list_for_engine(self, engine_slug: str) -> list[RepairWorkflow]:
        return [wf for wf in self._workflows.values() if wf.engine_slug == engine_slug]

    def export_json(self, path: str | Path) -> None:
        data = {k: v.to_dict() for k, v in self._workflows.items()}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ─── Default Built-In Workflows ─────────────────────────────────────────────

    def _build_default_workflows(self) -> None:
        """Populate with example workflows. More loaded from disk in real use."""
        self._build_toyota_5sfe_water_pump()
        self._build_toyota_5sfe_valve_cover_gasket()
        self._build_toyota_5sfe_spark_plugs()
        self._build_generic_brake_job()
        self._build_subaru_ej25_timing_belt()
        self._build_subaru_ej25_head_gasket()
        self._build_generic_wheel_bearing()

    def _build_toyota_5sfe_water_pump(self) -> None:
        """
        1998 Camry 5S-FE: Water pump + timing belt replacement.
        This is the user's explicit example — full detail.
        """
        steps = [
            RepairStep(
                step_number=1,
                title="Safety & Prep",
                description="Engine cold. Disconnect negative battery terminal. Raise front of vehicle on jack stands or lift.",
                required_tools=["jack stands", "floor jack", "10mm wrench"],
                fasteners=[
                    FastenerSpec("Battery negative cable clamp", "10mm hex", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=1, notes="Loosen only, do not remove stud"),
                ],
                estimated_time_min=10,
                safety_warnings=[
                    "Engine must be cold — hot coolant under pressure causes burns",
                    "Use wheel chocks if on ground",
                ],
                produces=["vehicle_lifted", "battery_disconnected"],
            ),
            RepairStep(
                step_number=2,
                title="Drain Coolant",
                description="Place catch pan under radiator petcock. Open petcock and remove radiator cap to vent. Drain fully.",
                required_tools=["catch pan", "gloves", "rag"],
                estimated_time_min=10,
                safety_warnings=["Coolant is toxic to pets — clean up spills immediately"],
                inspection_notes=["Coolant color: should be pink/red. Brown = overdue change or oil contamination (check for HG leak)."],
                produces=["coolant_drained"],
            ),
            RepairStep(
                step_number=3,
                title="Remove RH Undercover & Accessories",
                description="Remove plastic splash shield under right side. Remove alternator belt and A/C belt if equipped. Remove PS pump and bracket if in the way — do not disconnect hoses, just swing aside.",
                required_tools=["10mm socket", "12mm socket", "14mm socket", "ratchet"],
                fasteners=[
                    FastenerSpec("Splash shield bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=4, location="Under RH side"),
                    FastenerSpec("Alternator adjustment bolt", "12mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, quantity=1, location="Top of alternator bracket"),
                    FastenerSpec("Alternator pivot bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1, location="Bottom of alternator"),
                    FastenerSpec("PS pump bracket bolts", "12mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, quantity=2, location="PS pump to block"),
                ],
                estimated_time_min=15,
                produces=["belts_removed", "access_clear"],
            ),
            RepairStep(
                step_number=4,
                title="Remove Crankshaft Pulley",
                description="Hold crankshaft pulley with holder tool or wedge flywheel through inspection port. Remove 22mm crank bolt. Remove pulley with puller if stuck.",
                required_tools=["22mm socket", "crank pulley holder", "puller (optional)", "impact gun (optional)"],
                fasteners=[
                    FastenerSpec("Crankshaft pulley bolt", "22mm socket", drive="", torque_ft_lbs=87.0, torque_nm=118.0, torque_type="standard", quantity=1, notes="VERY tight — use breaker bar or impact. Do NOT use impact on reassembly."),
                ],
                estimated_time_min=15,
                safety_warnings=[
                    "Do NOT use impact gun to tighten crank bolt on reassembly — stretches bolt unevenly",
                    "Pulley is aluminum — be careful with puller jaws",
                ],
                inspection_notes=["Check front seal for seepage behind pulley. Replace now if wet."],
                produces=["crank_pulley_off"],
            ),
            RepairStep(
                step_number=5,
                title="Remove Timing Belt Covers",
                description="Remove upper and lower timing belt covers. Upper is 3–4 10mm bolts. Lower may require 12mm bolts on brackets.",
                required_tools=["10mm socket", "12mm socket"],
                fasteners=[
                    FastenerSpec("Upper cover bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=4, location="Perimeter of upper cover"),
                    FastenerSpec("Lower cover bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=3, location="Lower cover to block"),
                ],
                estimated_time_min=10,
                produces=["covers_off"],
            ),
            RepairStep(
                step_number=6,
                title="Set Engine to TDC / Confirm Timing Marks",
                description="Rotate crankshaft clockwise until timing mark on crank sprocket aligns with pointer on oil pump housing. Check camshaft sprocket punch marks align with backing plate marks at 12 o'clock.",
                required_tools=["19mm socket", "ratchet", "breaker bar"],
                estimated_time_min=10,
                safety_warnings=[
                    "Rotate ONLY clockwise — reverse rotation can skip belt teeth and bend valves",
                    "Verify BOTH marks before proceeding. If only one aligns, rotate another full revolution",
                ],
                inspection_notes=[
                    "Cam sprocket marks: small punch holes should align with notches on backing plate at 12 o'clock",
                    "Crank mark: notch on sprocket aligns with pointer on oil pump at ~11 o'clock position",
                ],
                produces=["at_tdc", "timing_confirmed"],
            ),
            RepairStep(
                step_number=7,
                title="Remove Timing Belt Tensioner & Belt",
                description="Loosen tensioner bolt (14mm). Spring will push tensioner to relieve belt tension. Slide belt off crank sprocket, then off cam sprocket. Remove tensioner and idler pulley.",
                required_tools=["14mm socket", "12mm socket", "torque critical"],
                fasteners=[
                    FastenerSpec("Tensioner bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1, location="Center of tensioner arm"),
                    FastenerSpec("Idler pulley bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1, location="Center of idler pulley"),
                ],
                estimated_time_min=15,
                safety_warnings=[
                    "DO NOT rotate crank or cam with belt OFF — this is an interference engine. Valves hit pistons.",
                    "Keep tensioner spring — re-use if not damaged",
                ],
                inspection_notes=[
                    "Check belt teeth for cracking, glazing, or missing chunks. If any damage, inspect sprockets for burrs.",
                    "Spin idler and tensioner pulleys — should be silent and smooth. Replace if gritty.",
                ],
                produces=["belt_off", "tensioner_removed"],
            ),
            RepairStep(
                step_number=8,
                title="Remove Water Pump",
                description="Remove water pump bolts. Pump is behind timing belt tensioner area. Scrape old gasket material from block and pump mating surfaces. Clean with brake clean.",
                required_tools=["10mm socket", "scraper", "brake clean", "rag"],
                fasteners=[
FastenerSpec("Water pump bolts (upper)", "10mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, quantity=3, location="Upper pump flange"),
FastenerSpec("Water pump bolts (lower)", "10mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, quantity=3, location="Lower pump flange"),
                ],
                estimated_time_min=15,
                safety_warnings=["Scrape carefully — aluminum block gouges easily. Do NOT use rotary wire brush."],
                inspection_notes=[
                    "Check impeller for corrosion or erosion pits. Replace pump if impeller is worn.",
                    "Check weep hole — if wet, pump was already failing. Confirm with customer.",
                ],
                produces=["pump_removed"],
            ),
            RepairStep(
                step_number=9,
                title="Install New Water Pump",
                description="Apply thin film of RTV to both sides of new gasket. Install pump with gasket. Torque bolts in star pattern.",
                required_tools=["10mm socket", "torque critical", "RTV"],
                fasteners=[
FastenerSpec("Water pump bolts (all)", "10mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, torque_type="standard", quantity=6, notes="Torque in cross pattern. Do not overtighten — aluminum threads strip."),
                ],
                estimated_time_min=15,
                safety_warnings=["Too much RTV squeezes into coolant passages. Thin film only."],
                inspection_notes=["Pump should seat flush without forcing. If it rocks, check for old gasket residue."],
                produces=["pump_installed"],
            ),
            RepairStep(
                step_number=10,
                title="Install New Tensioner & Idler",
                description="Install new tensioner and idler pulley. Tensioner spring hooks to stud and arm. Verify spring is seated in both hooks.",
                required_tools=["14mm socket", "torque critical"],
                fasteners=[
                    FastenerSpec("Tensioner bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1, notes="Tensioner must pivot freely after torquing"),
                    FastenerSpec("Idler pulley bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1, notes="Spin pulley after — should be silent"),
                ],
                estimated_time_min=10,
                inspection_notes=["Push tensioner arm — should spring back smoothly. No binding."],
                produces=["tensioner_installed"],
            ),
            RepairStep(
                step_number=11,
                title="Install New Timing Belt",
                description="Start belt on crank sprocket (ensure mark still aligned). Route counterclockwise up to cam sprocket. Belt should be snug on tensioner side, loose on slack side. Verify cam and crank marks still align.",
                required_tools=["fingers", "patience"],
                estimated_time_min=15,
                safety_warnings=[
                    "CRITICAL: Verify both timing marks AFTER belt is on. If misaligned, remove and re-align.",
                    "Do NOT rotate crank to 'adjust' — remove belt and set marks properly.",
                ],
                substeps=[
                    "Route belt over crank sprocket first",
                    "Up around tensioner pulley",
                    "Over water pump (if pump has sprocket — 5S-FE does not)",
                    "Over cam sprocket",
                    "Push tensioner with 14mm socket to take up slack",
                    "Verify cam punch marks at 12 o'clock",
                    "Verify crank mark aligned with pointer",
                ],
                inspection_notes=["Belt teeth must sit fully in sprocket valleys. No half-seated teeth."],
                produces=["belt_installed", "timing_verified"],
            ),
            RepairStep(
                step_number=12,
                title="Set Belt Tension",
                description="Use tensioner tool or 14mm socket to push tensioner against spring. Tighten tensioner bolt to spec while holding tension. Rotate crank TWO full revolutions clockwise. Recheck timing marks.",
                required_tools=["14mm socket", "torque critical", "19mm socket"],
                fasteners=[
FastenerSpec("Tensioner bolt (final)", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1, notes="Hold tension while tightening — do NOT let spring relax"),
                ],
                estimated_time_min=15,
                safety_warnings=[
                    "After tensioning, rotate crank 2 full revolutions and RE-CHECK timing marks.",
                    "If marks are off by even one tooth, remove belt and re-align.",
                ],
                substeps=[
                    "Push tensioner fully toward water pump",
                    "Tighten tensioner bolt to 32 ft-lb while holding tension",
                    "Rotate crank 2 full revolutions clockwise (720°)",
                    "Re-check cam mark at TDC",
                    "Re-check crank mark at TDC",
                    "If both align, tension is correct",
                ],
                produces=["belt_tensioned"],
            ),
            RepairStep(
                step_number=13,
                title="Reinstall Timing Covers & Crank Pulley",
                description="Install lower cover, then upper cover. Install crank pulley. Torque crank bolt to spec using holder tool (NOT impact).",
                required_tools=["10mm socket", "22mm socket", "crank pulley holder", "torque critical"],
                fasteners=[
                    FastenerSpec("Timing cover bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=7, notes="Snug only — plastic threads strip"),
                    FastenerSpec("Crankshaft pulley bolt", "22mm socket", drive="", torque_ft_lbs=87.0, torque_nm=118.0, torque_type="standard", quantity=1, notes="Use holder tool + torque wrench. Do NOT use impact."),
                ],
                estimated_time_min=15,
                safety_warnings=["Overtightening crank bolt can fracture pulley hub or stretch bolt."],
                produces=["covers_on", "pulley_on"],
            ),
            RepairStep(
                step_number=14,
                title="Reinstall Belts & Accessories",
                description="Reinstall alternator belt, A/C belt, PS belt. Adjust tension via adjustment bolts. Verify all belts deflect ~10mm at midpoint.",
                required_tools=["12mm socket", "14mm socket", "wrench set"],
                fasteners=[
                    FastenerSpec("Alternator adjustment bolt", "12mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, quantity=1),
                    FastenerSpec("Alternator pivot bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1),
                    FastenerSpec("PS pump bolts", "12mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, quantity=2),
                ],
                estimated_time_min=15,
                inspection_notes=["Belt should not squeal on startup. If it does, re-tension."],
                produces=["belts_on"],
            ),
            RepairStep(
                step_number=15,
                title="Refill Coolant & Bleed",
                description="Close radiator petcock. Fill with Toyota Pink SLLC coolant 50/50 with distilled water. Fill slowly to avoid air pockets. Start engine with heater on MAX and cap OFF. Add coolant as level drops. When thermostat opens, level will drop — top off. Install cap when full and no bubbles.",
                required_tools=["funnel", "spill-free funnel (optional)", "Toyota Pink coolant"],
                estimated_time_min=20,
                safety_warnings=[
                    "Do NOT install radiator cap on hot engine — pressure builds immediately",
                    "Keep heater on MAX during bleed — forces flow through heater core",
                ],
                substeps=[
                    "Fill radiator to neck",
                    "Fill overflow tank to FULL line",
                    "Start engine, heater on MAX HOT, fan on HIGH",
                    "Let idle 10–15 minutes",
                    "Watch for bubbles in radiator neck",
                    "When thermostat opens, level drops — add coolant",
                    "Install cap when full and stable",
                    "Recheck level after test drive",
                ],
                inspection_notes=["Upper radiator hose should be hot after thermostat opens. If cold, stuck thermostat or air pocket."],
                produces=["coolant_filled", "system_bled"],
            ),
            RepairStep(
                step_number=16,
                title="Final Checks & Test Drive",
                description="Reconnect battery. Verify no leaks under vehicle. Start engine — listen for belt squeal or knocking. Check temperature gauge reaches normal and stays there. Test drive 5–10 minutes with A/C on. Recheck coolant level cold.",
                required_tools=["10mm wrench"],
                fasteners=[
                    FastenerSpec("Battery negative clamp", "10mm hex", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=1),
                ],
                estimated_time_min=20,
                safety_warnings=["Check under vehicle BEFORE lowering from lift — coolant puddle = leak."],
                inspection_notes=[
                    "No coolant dripping from weep hole or pump gasket",
                    "No timing cover leaking coolant",
                    "Temperature stable at middle of gauge",
                    "No CEL after test drive",
                ],
                produces=["job_complete"],
            ),
        ]

        wf = RepairWorkflow(
            slug="toyota_5sfe__water_pump_timing_belt",
            engine_slug="toyota_5sfe",
            symptom="water_pump_timing_belt",
            title="Toyota 5S-FE: Water Pump & Timing Belt Replacement",
            description="Complete water pump and timing belt replacement for Toyota 5S-FE (1990–2001 Camry, Celica, MR2). Includes timing belt routing, tensioning, and coolant bleed procedure.",
            skill_level="intermediate",
            estimated_total_time_min=sum(s.estimated_time_min for s in steps),
            steps=steps,
            required_tools_summary=[
                "Metric socket set (10, 12, 14, 17, 19, 22mm)",
                "3/8 ratchet + extensions (3, 6, 10 in)",
                "Torque wrench (3/8, 10–100 ft-lb)",
                "Crank pulley holder tool",
                "Breaker bar",
                "Jack + stands or lift",
                "Catch pan (≥3 gal)",
                "Coolant funnel / spill-free funnel",
                "Scraper + brake clean",
                "RTV sealant (Toyota FIPG or Permatex Ultra Gray)",
            ],
            consumables=[
                "Toyota Pink SLLC coolant (2 gal)",
                "Distilled water (2 gal)",
                "RTV sealant",
                "Shop towels",
                "Brake cleaner",
                "New timing belt",
                "New water pump + gasket",
                "New tensioner + idler pulley",
                "New crankshaft seal (optional but recommended)",
            ],
            prerequisite_checks=[
                "Engine cold — no hot coolant under pressure",
                "Vehicle safely supported on stands or lift",
                "Battery negative terminal disconnected",
                "New parts on bench: belt, pump, tensioner, idler, coolant",
                "Torque wrench calibrated and in range",
            ],
            cautions=[
                "INTERFERENCE ENGINE: If timing belt breaks or is misinstalled, valves WILL hit pistons.",
                "Do NOT rotate crank or cam with belt removed.",
                "Do NOT use impact gun on crank bolt reassembly — use torque wrench + holder.",
                "Use ONLY Toyota Pink SLLC or equivalent — green coolant causes corrosion in Toyota aluminum.",
            ],
            related_procedures=[
                "toyota_5sfe__valve_cover_gasket",
                "toyota_5sfe__timing_belt_only",
            ],
        )
        self.register(wf)

    def _build_subaru_ej25_head_gasket(self) -> None:
        """
        Subaru EJ25 SOHC: Head gasket replacement.
        Simplified but realistic — full version loaded from disk in production.
        """
        steps = [
            RepairStep(
                step_number=1,
                title="Drain Fluids & Disconnect Battery",
                description="Drain coolant and oil. Remove battery and tray for RH access.",
                required_tools=["catch pan", "10mm wrench", "12mm socket"],
                fasteners=[
                    FastenerSpec("Battery clamp", "10mm hex", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=1),
                    FastenerSpec("Battery tray bolts", "12mm socket", drive="", torque_ft_lbs=14.0, torque_nm=19.0, quantity=3),
                ],
                estimated_time_min=15,
                safety_warnings=["Coolant toxic to pets"],
                produces=["fluids_drained", "battery_out"],
            ),
            RepairStep(
                step_number=2,
                title="Remove Timing Belt & Covers",
                description="Remove covers, set to TDC, remove tensioner, remove belt. DO NOT rotate crank/cam.",
                required_tools=["10mm socket", "14mm socket", "Subaru crank holder", "torque critical"],
                fasteners=[
                    FastenerSpec("Timing cover bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=8),
                    FastenerSpec("Tensioner bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1),
                    FastenerSpec("Idler pulley bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1),
                ],
                estimated_time_min=20,
                safety_warnings=[
                    "INTERFERENCE ENGINE — do not rotate with belt off",
                    "Mark belt direction with paint pen before removal",
                ],
                produces=["belt_off", "covers_off"],
            ),
            RepairStep(
                step_number=3,
                title="Remove Cylinder Heads",
                description="Remove intake manifold, exhaust manifolds, valve covers. Remove head bolts in reverse torque sequence. Lift heads straight up.",
                required_tools=["10mm socket", "12mm socket", "14mm socket", "1/2 torque wrench", "angle gauge"],
                fasteners=[
FastenerSpec("Head bolts (TTY — MUST REPLACE)", "14mm 12-point", drive="", torque_ft_lbs=36.0, torque_nm=49.0, torque_type="TTY", quantity=10, notes="Replace with new. Torque 36 ft-lb, then 90° angle. Do NOT reuse.", location="5 per head, outer row"),
                ],
                estimated_time_min=45,
                safety_warnings=[
                    "Head bolts are TTY — MUST replace. Reusing stretches bolts = clamping force loss = repeat HG failure.",
                    "Lift heads straight up — sliding gouges deck surface.",
                ],
                inspection_notes=[
                    "Check deck surface for warp with straightedge + feeler gauge (spec: 0.002 in max).",
                    "Look for corrosion pitting around coolant passages — this is why Subaru HG fails.",
                ],
                produces=["heads_removed"],
            ),
            RepairStep(
                step_number=4,
                title="Install MLS Head Gaskets & Reassemble",
                description="Clean deck surfaces with Scotch-Brite and brake clean. Install MLS gaskets (composite gaskets WILL fail again). Torque head bolts in sequence: 22 ft-lb, then 36 ft-lb, then 90° angle.",
                required_tools=["1/2 torque wrench", "angle gauge", "brake clean", "Scotch-Brite"],
                fasteners=[
FastenerSpec("Head bolts (NEW TTY)", "14mm 12-point", drive="", torque_ft_lbs=36.0, torque_nm=49.0, torque_type="TTY", quantity=10, notes="Stage 1: 22 ft-lb. Stage 2: 36 ft-lb. Stage 3: +90° angle. Use angle gauge.", location="Follow factory sequence: center → ends, alternating sides"),
                ],
                estimated_time_min=60,
                safety_warnings=[
                    "USE MLS GASKETS ONLY — Fel-Pro or OEM Subaru. Composite gaskets fail again.",
                    "Deck MUST be clean — any oil residue causes immediate leak.",
                    "Angle gauge is mandatory — ft-lb alone is insufficient for TTY bolts.",
                ],
                inspection_notes=["Gasket should sit flush without sliding. Blue loc-tite on upper bolt threads (some kits include)."],
                produces=["heads_installed"],
            ),
            RepairStep(
                step_number=5,
                title="Reinstall Timing Belt & Covers",
                description="Reinstall belt with marks aligned. Tension per Subaru spec. Reinstall covers, battery, fluids.",
                required_tools=["14mm socket", "torque critical"],
                fasteners=[
                    FastenerSpec("Tensioner bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1),
                    FastenerSpec("Idler pulley bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1),
                ],
                estimated_time_min=30,
                safety_warnings=["Rotate crank 2 revolutions and re-check marks."],
                produces=["belt_on", "job_complete"],
            ),
        ]

        wf = RepairWorkflow(
            slug="subaru_ej25_sohc__head_gasket",
            engine_slug="subaru_ej25_sohc",
            symptom="head_gasket",
            title="Subaru EJ25 SOHC: Head Gasket Replacement",
            description="Head gasket replacement for Subaru EJ25 SOHC. Emphasizes MLS gasket requirement, TTY bolt replacement, and deck surface inspection.",
            skill_level="advanced",
            estimated_total_time_min=sum(s.estimated_time_min for s in steps),
            steps=steps,
            required_tools_summary=[
                "Metric socket set (10, 12, 14mm)",
                "1/2 torque wrench (20–150 ft-lb)",
                "Angle gauge (for TTY bolts)",
                "Subaru crank holder + cam holder",
                "Straightedge + feeler gauge (0.002 in)",
                "Scotch-Brite pads",
                "Brake cleaner",
            ],
            consumables=[
                "MLS head gasket set (Fel-Pro or OEM)",
                "Head bolts (NEW — TTY, do NOT reuse)",
                "Valve cover gaskets",
                "Intake manifold gasket",
                "Exhaust manifold gasket",
                "Coolant (Subaru Super Coolant — BLUE)",
                "Motor oil + filter",
                "RTV sealant",
            ],
            prerequisite_checks=[
                "Confirm external coolant leak (not combustion leak) with combustion tester",
                "Verify deck warp is within 0.002 in before ordering parts",
                "Order MLS gaskets — confirm part number, not composite",
            ],
            cautions=[
                "MLS gaskets ONLY. Composite gaskets fail again.",
                "TTY head bolts MUST be replaced. Do NOT reuse.",
                "Angle gauge is mandatory for final torque.",
                "Subaru coolant is BLUE — do NOT mix green or orange.",
            ],
            related_procedures=[
                "subaru_ej25_sohc__timing_belt",
                "subaru_ej25_sohc__valve_cover_gasket",
            ],
        )
        self.register(wf)

    # ─── NEW WORKFLOWS ADDED IN THIS SESSION ─────────────────────────────────────

    def _build_toyota_5sfe_valve_cover_gasket(self) -> None:
        """Toyota 5S-FE: Valve cover gasket replacement — common oil leak fix."""
        steps = [
            RepairStep(
                step_number=1,
                title="Safety & Prep",
                description="Engine cold. Disconnect negative battery terminal. Remove engine cover if equipped.",
                required_tools=["10mm wrench", "rag"],
                fasteners=[
                    FastenerSpec("Battery negative clamp", "10mm hex", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=1),
                ],
                estimated_time_min=5,
                safety_warnings=["Engine must be cold — hot valve cover burns skin"],
                produces=["battery_disconnected"],
            ),
            RepairStep(
                step_number=2,
                title="Remove Ignition Coils & Wiring",
                description="Label and disconnect ignition coil connectors. Remove coil packs (10mm bolts). Set aside.",
                required_tools=["10mm socket"],
                fasteners=[
                    FastenerSpec("Coil pack bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=4, notes="Do not overtighten on reassembly — strip easily"),
                ],
                estimated_time_min=10,
                produces=["coils_removed"],
            ),
            RepairStep(
                step_number=3,
                title="Remove PCV Hose & Breather",
                description="Disconnect PCV hose from valve cover. Remove breather hose. Move hoses aside.",
                required_tools=["pliers", "rag"],
                estimated_time_min=5,
                produces=["hoses_disconnected"],
            ),
            RepairStep(
                step_number=4,
                title="Remove Valve Cover Bolts",
                description="Remove valve cover bolts in reverse of torque sequence (spiral outward). Cover may be stuck — tap gently with rubber mallet, do NOT pry with screwdriver.",
                required_tools=["10mm socket", "ratchet", "rubber mallet"],
                fasteners=[
                    FastenerSpec("Valve cover bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=8, notes="Some have rubber grommets — do not lose"),
                ],
                estimated_time_min=10,
                safety_warnings=["Do NOT pry with screwdriver — gouges head surface = new leak"],
                produces=["cover_loose"],
            ),
            RepairStep(
                step_number=5,
                title="Remove Old Gasket & Clean Surfaces",
                description="Peel old gasket from cover and head. Scrape residue with plastic scraper. Clean with brake clean. Apply FIPG (Toyota gray RTV) to front cam cap seam and rear half-moons.",
                required_tools=["plastic scraper", "brake clean", "rag", "RTV"],
                estimated_time_min=15,
                safety_warnings=["Do NOT use metal scraper on aluminum head — scratches cause leaks"],
                inspection_notes=["Half-moon seals at front and rear of head are common leak points. Replace if hard/cracked."],
                produces=["surfaces_clean"],
            ),
            RepairStep(
                step_number=6,
                title="Install New Gasket & Reassemble",
                description="Install new gasket in cover groove. RTV on half-moons and front/rear cap junctions. Set cover straight down. Torque bolts in spiral pattern from center outward: 7 ft-lb.",
                required_tools=["10mm socket", "torque critical"],
                fasteners=[
                    FastenerSpec("Valve cover bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, torque_type="standard", quantity=8, notes="Torque in spiral sequence. Snug, then 7 ft-lb final."),
                ],
                estimated_time_min=15,
                safety_warnings=["Too much RTV squeezes into head — thin bead only"],
                produces=["cover_installed"],
            ),
            RepairStep(
                step_number=7,
                title="Reinstall Coils, Hoses, Battery",
                description="Reinstall coil packs (7 ft-lb). Reconnect PCV and breather hoses. Reconnect battery.",
                required_tools=["10mm socket"],
                fasteners=[
                    FastenerSpec("Coil pack bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=4),
                    FastenerSpec("Battery clamp", "10mm hex", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=1),
                ],
                estimated_time_min=10,
                inspection_notes=["Start engine and check for oil seepage at cover edges after 5 minutes."],
                produces=["job_complete"],
            ),
        ]
        wf = RepairWorkflow(
            slug="toyota_5sfe__valve_cover_gasket",
            engine_slug="toyota_5sfe",
            symptom="valve_cover_gasket",
            title="Toyota 5S-FE: Valve Cover Gasket Replacement",
            description="Replace leaking valve cover gasket on Toyota 5S-FE. Common at 100k+ miles. Emphasizes half-moon RTV and no-pry removal.",
            skill_level="beginner",
            estimated_total_time_min=sum(s.estimated_time_min for s in steps),
            steps=steps,
            required_tools_summary=["10mm socket", "ratchet", "torque wrench", "plastic scraper", "brake clean", "RTV", "rubber mallet"],
            consumables=["Valve cover gasket set", "Toyota FIPG / Permatex Ultra Gray", "Brake cleaner", "Shop towels"],
            prerequisite_checks=["Engine cold", "New gasket and RTV on hand"],
            cautions=["Do NOT pry with screwdriver — gouges aluminum head surface", "Use plastic scraper only"],
            related_procedures=["toyota_5sfe__water_pump_timing_belt", "toyota_5sfe__spark_plugs"],
        )
        self.register(wf)

    def _build_toyota_5sfe_spark_plugs(self) -> None:
        """Toyota 5S-FE: Spark plug replacement."""
        steps = [
            RepairStep(
                step_number=1,
                title="Safety & Access",
                description="Engine cold. Remove engine cover. Disconnect coil connectors.",
                required_tools=["10mm socket"],
                fasteners=[
                    FastenerSpec("Coil pack bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=4),
                ],
                estimated_time_min=5,
                produces=["coils_accessible"],
            ),
            RepairStep(
                step_number=2,
                title="Remove Coil Packs & Inspect Tubes",
                description="Pull coil packs straight up. Inspect spark plug tubes for oil — oil in tube = valve cover gasket leak.",
                required_tools=["hands"],
                estimated_time_min=5,
                inspection_notes=["Oil in plug tube = replace valve cover gasket and tube seals."],
                produces=["coils_removed"],
            ),
            RepairStep(
                step_number=3,
                title="Remove Old Plugs",
                description="Remove spark plugs with 5/8 socket + extension + universal joint. Inspect electrodes.",
                required_tools=["5/8 spark plug socket", "3/8 ratchet", "extension (6in)", "universal joint"],
                estimated_time_min=10,
                inspection_notes=[
                    "White = lean. Black/sooty = rich. Wet = coolant or oil. Brown/tan = normal.",
                    "Gap should be 0.044 in.",
                ],
                produces=["plugs_removed"],
            ),
            RepairStep(
                step_number=4,
                title="Install New Plugs",
                description="Apply anti-seize to threads. Gap new plugs to 0.044 in. Thread by hand first. Torque to 13 ft-lb.",
                required_tools=["5/8 spark plug socket", "torque critical", "gap tool", "anti-seize"],
                fasteners=[
                    FastenerSpec("Spark plugs", "5/8 hex", drive="", torque_ft_lbs=13.0, torque_nm=18.0, torque_type="standard", quantity=4, notes="Hand-thread first — cross-threading destroys head"),
                ],
                estimated_time_min=10,
                safety_warnings=["Hand-thread first — NEVER use impact or power tools on spark plugs in aluminum head"],
                produces=["plugs_installed"],
            ),
            RepairStep(
                step_number=5,
                title="Reinstall Coil Packs & Test",
                description="Reinstall coil packs. Torque bolts to 7 ft-lb. Start engine — verify smooth idle, no misfire.",
                required_tools=["10mm socket"],
                fasteners=[
                    FastenerSpec("Coil pack bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=4),
                ],
                estimated_time_min=5,
                produces=["job_complete"],
            ),
        ]
        wf = RepairWorkflow(
            slug="toyota_5sfe__spark_plugs",
            engine_slug="toyota_5sfe",
            symptom="spark_plugs",
            title="Toyota 5S-FE: Spark Plug Replacement",
            description="Replace spark plugs on Toyota 5S-FE. NGK BKR5E-11 or Denso K16TR11. Interval: 30k miles (platinum).",
            skill_level="beginner",
            estimated_total_time_min=sum(s.estimated_time_min for s in steps),
            steps=steps,
            required_tools_summary=["5/8 spark plug socket", "3/8 ratchet", "extension", "gap tool", "torque wrench", "anti-seize"],
            consumables=["NGK BKR5E-11 or Denso K16TR11 (4)", "Anti-seize compound", "Dielectric grease"],
            prerequisite_checks=["Engine cold", "Correct spark plug part number"],
            cautions=["Hand-thread spark plugs — never power-drive into aluminum head", "Check plug tubes for oil"],
            related_procedures=["toyota_5sfe__valve_cover_gasket"],
        )
        self.register(wf)

    def _build_generic_brake_job(self) -> None:
        """Generic disc brake pad & rotor replacement."""
        steps = [
            RepairStep(
                step_number=1,
                title="Safety & Lift",
                description="Loosen lug nuts. Raise vehicle on jack stands. Remove wheel.",
                required_tools=["lug wrench", "floor jack", "jack stands"],
                fasteners=[
                    FastenerSpec("Lug nuts", "19mm or 21mm socket", drive="", torque_ft_lbs=80.0, torque_nm=108.0, torque_type="standard", quantity=4, notes="Loosen before lifting"),
                ],
                estimated_time_min=10,
                safety_warnings=["Never work under vehicle supported only by jack — use stands"],
                produces=["wheel_off"],
            ),
            RepairStep(
                step_number=2,
                title="Remove Caliper & Bracket",
                description="Remove caliper bolts (slide pins) — 14mm. Swing caliper up and hang with bungee (do NOT let hang by hose). Remove caliper bracket bolts — 17mm.",
                required_tools=["14mm socket", "17mm socket", "ratchet", "bungee cord"],
                fasteners=[
                    FastenerSpec("Caliper slide bolts", "14mm socket", drive="", torque_ft_lbs=25.0, torque_nm=34.0, quantity=2, location="Top and bottom of caliper"),
                    FastenerSpec("Caliper bracket bolts", "17mm socket", drive="", torque_ft_lbs=80.0, torque_nm=108.0, quantity=2, location="Back of knuckle"),
                ],
                estimated_time_min=15,
                safety_warnings=["Do NOT let caliper hang by brake hose — stretches/kinks hose"],
                produces=["caliper_off"],
            ),
            RepairStep(
                step_number=3,
                title="Remove Old Pads & Rotor",
                description="Remove pads. Remove rotor set screw (if equipped) — often Phillips or T-30. Tap rotor off hub with mallet if rusted.",
                required_tools=["hammer", "screwdriver", "impact driver (optional)"],
                fasteners=[
                    FastenerSpec("Rotor set screw", "Phillips #2 or T-30", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=1, notes="Often seized — impact driver recommended"),
                ],
                estimated_time_min=10,
                safety_warnings=["Rotor may be heavy — catch before it falls"],
                produces=["rotor_off"],
            ),
            RepairStep(
                step_number=4,
                title="Clean & Inspect",
                description="Clean caliper bracket with wire brush. Lubricate slide pins with silicone brake grease. Inspect caliper piston boot for tears.",
                required_tools=["wire brush", "brake clean", "silicone brake grease"],
                estimated_time_min=10,
                inspection_notes=["Slide pins must move freely. If stuck, replace pin kit. Boot torn = replace caliper."],
                produces=["cleaned"],
            ),
            RepairStep(
                step_number=5,
                title="Install New Rotor & Pads",
                description="Install new rotor (clean with brake clean first). Install pad hardware clips. Install new pads with anti-rattle clips. Compress caliper piston with C-clamp or tool.",
                required_tools=["C-clamp or brake piston tool", "brake clean"],
                fasteners=[],
                estimated_time_min=15,
                safety_warnings=["Compress piston SLOWLY — brake fluid may overflow reservoir"],
                produces=["pads_installed"],
            ),
            RepairStep(
                step_number=6,
                title="Reinstall Caliper & Torque",
                description="Reinstall caliper bracket (80 ft-lb). Reinstall caliper slide bolts (25 ft-lb). Reinstall wheel. Lower vehicle. Torque lug nuts in star pattern to spec (usually 80 ft-lb).",
                required_tools=["14mm socket", "17mm socket", "torque critical", "lug wrench"],
                fasteners=[
                    FastenerSpec("Caliper bracket bolts", "17mm socket", drive="", torque_ft_lbs=80.0, torque_nm=108.0, torque_type="standard", quantity=2),
                    FastenerSpec("Caliper slide bolts", "14mm socket", drive="", torque_ft_lbs=25.0, torque_nm=34.0, torque_type="standard", quantity=2),
                    FastenerSpec("Lug nuts", "19mm or 21mm", drive="", torque_ft_lbs=80.0, torque_nm=108.0, torque_type="standard", quantity=4, notes="Star pattern"),
                ],
                estimated_time_min=15,
                safety_warnings=["Torque lug nuts in star pattern — uneven torque warps rotor"],
                produces=["job_complete"],
            ),
        ]
        wf = RepairWorkflow(
            slug="generic__brake_job",
            engine_slug="generic",
            symptom="brake_pads_rotors",
            title="Generic Disc Brake: Pad & Rotor Replacement",
            description="Standard disc brake pad and rotor replacement procedure. Applies to most FWD/RWD vehicles with floating calipers.",
            skill_level="beginner",
            estimated_total_time_min=sum(s.estimated_time_min for s in steps),
            steps=steps,
            required_tools_summary=["Lug wrench", "14mm socket", "17mm socket", "torque wrench", "C-clamp", "wire brush", "brake clean", "silicone brake grease"],
            consumables=["Brake pads (front pair)", "Rotors (front pair)", "Brake clean", "Silicone brake grease", "Anti-rattle clips"],
            prerequisite_checks=["Verify pad thickness < 3mm", "Rotor thickness above minimum (stamped on edge)"],
            cautions=["Never hang caliper by brake hose", "Compress piston slowly to avoid overflow", "Torque lug nuts in star pattern"],
            related_procedures=[],
        )
        self.register(wf)

    def _build_subaru_ej25_timing_belt(self) -> None:
        """Subaru EJ25 SOHC: Timing belt replacement (belt only, not water pump)."""
        steps = [
            RepairStep(
                step_number=1,
                title="Safety & Prep",
                description="Engine cold. Disconnect battery. Remove radiator if necessary for clearance.",
                required_tools=["10mm wrench"],
                fasteners=[FastenerSpec("Battery clamp", "10mm hex", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=1)],
                estimated_time_min=10,
                safety_warnings=["Engine cold — hot coolant under pressure causes burns"],
                produces=["battery_disconnected"],
            ),
            RepairStep(
                step_number=2,
                title="Remove Belts & Covers",
                description="Remove accessory belts. Remove timing belt covers (10mm bolts).",
                required_tools=["10mm socket", "12mm socket"],
                fasteners=[
                    FastenerSpec("Timing cover bolts", "10mm socket", drive="", torque_ft_lbs=7.0, torque_nm=10.0, quantity=8),
                ],
                estimated_time_min=15,
                produces=["covers_off"],
            ),
            RepairStep(
                step_number=3,
                title="Set to TDC & Remove Crank Pulley",
                description="Set crank and cam to TDC marks. Hold crank pulley with Subaru holder. Remove 22mm crank bolt. Remove pulley.",
                required_tools=["22mm socket", "Subaru crank holder", "breaker bar"],
                fasteners=[
                    FastenerSpec("Crank pulley bolt", "22mm socket", drive="", torque_ft_lbs=132.0, torque_nm=179.0, torque_type="standard", quantity=1, notes="Very tight — breaker bar or impact OK for removal only"),
                ],
                estimated_time_min=20,
                safety_warnings=["Do NOT use impact to tighten crank bolt on reassembly"],
                produces=["pulley_off", "at_tdc"],
            ),
            RepairStep(
                step_number=4,
                title="Replace Belt & Components",
                description="Loosen tensioner. Remove old belt. Replace idler and tensioner pulleys. Install new belt with marks aligned. Tension per spec.",
                required_tools=["14mm socket", "torque critical"],
                fasteners=[
                    FastenerSpec("Tensioner bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1),
                    FastenerSpec("Idler pulley bolt", "14mm socket", drive="", torque_ft_lbs=32.0, torque_nm=43.0, quantity=1),
                ],
                estimated_time_min=30,
                safety_warnings=[
                    "INTERFERENCE ENGINE — do not rotate crank or cam with belt off",
                    "Rotate crank 2 revolutions and re-check marks before buttoning up",
                ],
                produces=["belt_installed"],
            ),
            RepairStep(
                step_number=5,
                title="Reassemble & Verify",
                description="Reinstall pulley (132 ft-lb with holder). Reinstall covers and belts. Start engine and verify smooth idle.",
                required_tools=["22mm socket", "Subaru crank holder", "torque critical"],
                fasteners=[
                    FastenerSpec("Crank pulley bolt", "22mm socket", drive="", torque_ft_lbs=132.0, torque_nm=179.0, torque_type="standard", quantity=1, notes="Use holder + torque wrench. Do NOT use impact."),
                ],
                estimated_time_min=20,
                produces=["job_complete"],
            ),
        ]
        wf = RepairWorkflow(
            slug="subaru_ej25_sohc__timing_belt",
            engine_slug="subaru_ej25_sohc",
            symptom="timing_belt",
            title="Subaru EJ25 SOHC: Timing Belt Replacement",
            description="Timing belt replacement for Subaru EJ25 SOHC. Interference engine — critical timing mark verification required.",
            skill_level="intermediate",
            estimated_total_time_min=sum(s.estimated_time_min for s in steps),
            steps=steps,
            required_tools_summary=["10mm socket", "12mm socket", "14mm socket", "22mm socket", "Subaru crank holder", "torque wrench", "breaker bar"],
            consumables=["Timing belt", "Tensioner pulley", "Idler pulley", "Coolant (if drained)"],
            prerequisite_checks=["Engine cold", "New belt kit on bench", "Subaru crank holder tool available"],
            cautions=["INTERFERENCE ENGINE — belt misalignment = bent valves", "Do NOT rotate crank/cam with belt off", "Do NOT use impact on crank bolt reassembly"],
            related_procedures=["subaru_ej25_sohc__head_gasket", "subaru_ej25_sohc__water_pump"],
        )
        self.register(wf)

    def _build_generic_wheel_bearing(self) -> None:
        """Generic front wheel bearing / hub assembly replacement."""
        steps = [
            RepairStep(
                step_number=1,
                title="Safety & Wheel Removal",
                description="Loosen axle nut (if applicable) and lug nuts. Raise vehicle. Remove wheel.",
                required_tools=["lug wrench", "32mm socket (axle nut)", "floor jack", "jack stands"],
                fasteners=[
                    FastenerSpec("Axle nut", "32mm or 36mm socket", drive="", torque_ft_lbs=134.0, torque_nm=182.0, torque_type="standard", quantity=1, notes="Stake or cotter pin type — inspect"),
                    FastenerSpec("Lug nuts", "19mm or 21mm", drive="", torque_ft_lbs=80.0, torque_nm=108.0, quantity=4),
                ],
                estimated_time_min=10,
                safety_warnings=["Axle nut is VERY tight — use breaker bar or impact"],
                produces=["wheel_off"],
            ),
            RepairStep(
                step_number=2,
                title="Remove Brake Caliper & Rotor",
                description="Remove caliper and hang with bungee. Remove rotor.",
                required_tools=["14mm socket", "17mm socket"],
                fasteners=[
                    FastenerSpec("Caliper slide bolts", "14mm socket", drive="", torque_ft_lbs=25.0, torque_nm=34.0, quantity=2),
                ],
                estimated_time_min=10,
                produces=["brake_off"],
            ),
            RepairStep(
                step_number=3,
                title="Remove Hub Assembly",
                description="Disconnect ABS sensor if equipped. Remove hub bolts from back of knuckle (often 17mm or 19mm). Tap hub out with hammer.",
                required_tools=["17mm socket", "19mm socket", "hammer", "penetrating oil"],
                fasteners=[
                    FastenerSpec("Hub bolts", "17mm or 19mm socket", drive="", torque_ft_lbs=60.0, torque_nm=81.0, quantity=3, notes="May be seized — penetrating oil + heat"),
                ],
                estimated_time_min=20,
                safety_warnings=["Hub may be seized in knuckle — do NOT hammer on ABS ring"],
                produces=["hub_removed"],
            ),
            RepairStep(
                step_number=4,
                title="Install New Hub & Torque",
                description="Clean knuckle bore. Apply anti-seize. Install new hub. Torque hub bolts to spec. Install axle nut to spec (usually 134 ft-lb + stake).",
                required_tools=["torque critical", "32mm socket", "cotter pin / stake tool"],
                fasteners=[
                    FastenerSpec("Hub bolts", "17mm or 19mm socket", drive="", torque_ft_lbs=60.0, torque_nm=81.0, torque_type="standard", quantity=3),
                    FastenerSpec("Axle nut", "32mm or 36mm socket", drive="", torque_ft_lbs=134.0, torque_nm=182.0, torque_type="standard", quantity=1, notes="Stake or cotter pin after torquing"),
                ],
                estimated_time_min=20,
                safety_warnings=["Axle nut MUST be staked or cotter-pinned after torque — loosening causes catastrophic failure"],
                produces=["hub_installed"],
            ),
            RepairStep(
                step_number=5,
                title="Reinstall Brakes & Wheel",
                description="Reinstall rotor and caliper. Reinstall wheel. Lower vehicle. Final torque axle nut and lug nuts.",
                required_tools=["14mm socket", "17mm socket", "torque critical"],
                fasteners=[
                    FastenerSpec("Caliper slide bolts", "14mm socket", drive="", torque_ft_lbs=25.0, torque_nm=34.0, quantity=2),
                    FastenerSpec("Lug nuts", "19mm or 21mm", drive="", torque_ft_lbs=80.0, torque_nm=108.0, quantity=4, notes="Star pattern"),
                ],
                estimated_time_min=15,
                produces=["job_complete"],
            ),
        ]
        wf = RepairWorkflow(
            slug="generic__wheel_bearing",
            engine_slug="generic",
            symptom="wheel_bearing",
            title="Generic: Front Wheel Bearing / Hub Assembly Replacement",
            description="Replace a noisy or loose front wheel bearing/hub assembly. Common on high-mileage FWD vehicles.",
            skill_level="intermediate",
            estimated_total_time_min=sum(s.estimated_time_min for s in steps),
            steps=steps,
            required_tools_summary=["Lug wrench", "14mm socket", "17mm socket", "19mm socket", "32mm socket", "torque wrench", "hammer", "bungee cord"],
            consumables=["Wheel hub assembly", "Axle nut (replace)", "Cotter pin or stake", "Anti-seize", "Brake clean"],
            prerequisite_checks=["Confirm bearing noise (growl that changes with steering load)", "Verify hub is in stock"],
            cautions=["Axle nut must be staked or cotter-pinned after torque", "Do NOT hammer on ABS tone ring"],
            related_procedures=["generic__brake_job"],
        )
        self.register(wf)


# ─── Convenience Functions ───────────────────────────────────────────────────────

def load_workflow_from_json(path: str | Path) -> RepairWorkflow:
    """Load a single workflow from JSON (exported by registry.export_json)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # Simplified — in real code, recursively parse dataclasses
    # For now, return raw dict; caller uses registry.register(RepairWorkflow(**data))
    raise NotImplementedError("Use RepairWorkflowRegistry + manual construction for now")


# When imported directly, the default registry is available
DEFAULT_REGISTRY = RepairWorkflowRegistry()
