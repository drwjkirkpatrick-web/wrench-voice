"""
workflow_predictor.py
=====================
Predict the next tool, fastener, or procedure the mechanic will need
BEFORE they ask for it.

WHY:
A mechanic spends 5–10 minutes per job walking back and forth:
- "Did I already drain the coolant?"
- "What size was that bolt again?"
- "Do I need the breaker bar or just the ratchet?"
- "What's next after the water pump?"

This module predicts those answers from the workflow tracker state
and delivers them proactively — on a heads-up display, earpiece,
or printed on a work-order sheet.

HOW:
1. Track current step + completed flags
2. Look ahead N steps for upcoming tools/fasteners
3. Predict based on:
   - What step they're on
   - What they've already done (flags)
   - What tools are already out (tool persistence model)
   - Common mistakes for this engine+symptom
4. Surface predictions as:
   - "Next tool: 14mm socket + torque wrench"
   - "Next fastener: Tensioner bolt → 32 ft-lb (do NOT let spring relax)"
   - "WARNING in 2 steps: interference engine — do NOT rotate crank"
   - "You probably need: breaker bar (crank bolt is 87 ft-lb)"

FEATURES:
- Tool persistence: predicts which tools to keep out vs put away
- Fastener pre-fetch: surfaces exact sizes before the step starts
- Warning lookahead: warns N steps ahead, not just current step
- Mistake prediction: "Common error on 5S-FE: forgetting to hold tensioner while torquing"
- Alternative paths: if a prerequisite is missing, suggests backtracking
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .repair_workflow import (
    FastenerSpec,
    RepairWorkflow,
    WorkflowTracker,
    ToolMatcher,
)


@dataclass
class Prediction:
    """One actionable prediction for the mechanic."""
    category: str              # tool | fastener | warning | procedure | time
    message: str               # Human-readable prediction
    urgency: str = "normal"      # low | normal | high | critical
    step_ahead: int = 0        # How many steps away is this relevant
    confidence: float = 1.0    # 0.0–1.0
    action: str = ""           # What to do: "grab_tool", "check_flag", "stop", etc.

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "urgency": self.urgency,
            "step_ahead": self.step_ahead,
            "confidence": self.confidence,
            "action": self.action,
        }


@dataclass
class PredictionContext:
    """Current state + environment for making predictions."""
    tracker: WorkflowTracker
    tools_on_bench: list[str] = field(default_factory=list)
    job_start_time: str = ""   # ISO datetime
    technician_skill: str = "intermediate"  # beginner | intermediate | advanced


class NextStepPredictor:
    """
    Predict what the mechanic needs next based on workflow progress.

    Usage:
        predictor = NextStepPredictor(tracker)
        predictions = predictor.predict()
        for p in predictions:
            print(f"[{p.urgency.upper()}] {p.message}")
    """

    def __init__(self, tracker: WorkflowTracker) -> None:
        self.tracker = tracker
        self.tool_matcher = ToolMatcher(tracker.workflow.engine_slug)
        self._mistakes_db = self._load_mistakes_db()

    # ─── Core Prediction ──────────────────────────────────────────────────────

    def predict(self, lookahead: int = 3) -> list[Prediction]:
        """
        Generate all relevant predictions for the mechanic RIGHT NOW.
        Returns list ordered by urgency (critical first).
        """
        predictions: list[Prediction] = []

        # 1. Immediate next tool prediction
        predictions.extend(self._predict_next_tools(lookahead))

        # 2. Upcoming fastener pre-fetch
        predictions.extend(self._predict_next_fasteners(lookahead))

        # 3. Warning lookahead (not just current step)
        predictions.extend(self._predict_warnings(lookahead))

        # 4. Prerequisite checks (did they forget something?)
        predictions.extend(self._predict_missing_prerequisites())

        # 5. Common mistakes for this engine+procedure
        predictions.extend(self._predict_mistakes())

        # 6. Time pressure
        predictions.extend(self._predict_time_pressure())

        # Sort by urgency
        urgency_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        predictions.sort(key=lambda p: urgency_order.get(p.urgency, 2))

        return predictions

    def predict_next_step_summary(self) -> dict[str, Any]:
        """Single-call summary for heads-up display or voice readout."""
        step = self.tracker.current_step
        if not step:
            return {"status": "DONE", "message": "Job complete. No more steps."}

        tools = self.tool_matcher.resolve_all(step.required_tools)
        warnings = step.safety_warnings
        fasteners = step.fasteners
        remaining = self.tracker.predict_time_remaining()
        progress = self.tracker.progress_pct()

        # Predict what's coming after this step
        next_tools = self.tracker.predict_next_tools(2)
        next_warnings = self._predict_warnings(2)
        critical_warning = next((w for w in next_warnings if w.urgency == "critical"), None)

        return {
            "status": "ACTIVE",
            "step": step.step_number,
            "title": step.title,
            "description": step.description,
            "tools_now": tools,
            "fasteners_now": [
                {"desc": f.description, "drive": f.drive, "torque": f.torque_str()}
                for f in fasteners
            ],
            "warnings_now": warnings,
            "time_remaining_min": remaining,
            "progress_pct": round(progress, 1),
            "next_tools": next_tools,
            "critical_lookahead": critical_warning.message if critical_warning else None,
            "predictions": [p.to_dict() for p in self.predict(lookahead=2)],
        }

    # ─── Internal Predictors ──────────────────────────────────────────────────

    def _predict_next_tools(self, lookahead: int) -> list[Prediction]:
        """Predict tools needed in upcoming steps."""
        tools = self.tracker.predict_next_tools(lookahead)
        if not tools:
            return []

        return [Prediction(
            category="tool",
            message=f"Next {len(tools)} tool(s): {', '.join(tools[:5])}",
            urgency="normal",
            step_ahead=1,
            confidence=0.95,
            action="grab_tools",
        )]

    def _predict_next_fasteners(self, lookahead: int) -> list[Prediction]:
        """Pre-fetch exact fastener specs before the step."""
        fasteners = self.tracker.predict_next_fasteners(lookahead)
        if not fasteners:
            return []

        predictions: list[Prediction] = []
        for i, f in enumerate(fasteners[:3]):  # Limit to avoid overwhelm
            msg = f"{f.description}: {f.drive or f.size} → {f.torque_str()}"
            if f.notes:
                msg += f" | NOTE: {f.notes}"
            predictions.append(Prediction(
                category="fastener",
                message=msg,
                urgency="normal",
                step_ahead=i + 1,
                confidence=0.95,
                action="prep_fastener",
            ))
        return predictions

    def _predict_warnings(self, lookahead: int) -> list[Prediction]:
        """Look ahead for safety warnings, especially critical ones."""
        predictions: list[Prediction] = []
        start = self.tracker.state.current_step_idx

        for offset, step in enumerate(self.tracker.workflow.steps[start: start + lookahead]):
            for warning in step.safety_warnings:
                # Determine urgency from warning text
                urgency = self._classify_warning_urgency(warning)
                predictions.append(Prediction(
                    category="warning",
                    message=f"Step {step.step_number} ({step.title}): {warning}",
                    urgency=urgency,
                    step_ahead=offset,
                    confidence=1.0,
                    action="read_carefully" if urgency in ("critical", "high") else "note",
                ))
        return predictions

    def _predict_missing_prerequisites(self) -> list[Prediction]:
        """Detect if mechanic forgot a prerequisite step."""
        predictions: list[Prediction] = []
        step = self.tracker.current_step
        if not step:
            return predictions

        for prereq in step.depends_on:
            if prereq not in self.tracker.state.completed_steps and prereq not in self.tracker.state.skipped_steps:
                predictions.append(Prediction(
                    category="procedure",
                    message=f"Step {step.step_number} depends on Step {prereq} which is not complete. Go back?",
                    urgency="high",
                    step_ahead=0,
                    confidence=0.90,
                    action="go_back",
                ))

        # Check prerequisite flags
        for check in self.tracker.workflow.prerequisite_checks:
            flag = check.lower().replace(" ", "_").replace("—", "_")
            if not self.tracker.is_prerequisite_met(flag):
                predictions.append(Prediction(
                    category="procedure",
                    message=f"Prerequisite not confirmed: {check}",
                    urgency="high",
                    step_ahead=0,
                    confidence=0.85,
                    action="verify_prerequisite",
                ))

        return predictions

    def _predict_mistakes(self) -> list[Prediction]:
        """Surface common mistakes for this engine + procedure."""
        key = f"{self.tracker.workflow.engine_slug}__{self.tracker.workflow.symptom}"
        mistakes = self._mistakes_db.get(key, [])
        return [
            Prediction(
                category="warning",
                message=f"Common mistake: {m}",
                urgency="normal",
                step_ahead=0,
                confidence=0.70,
                action="remember",
            )
            for m in mistakes
        ]

    def _predict_time_pressure(self) -> list[Prediction]:
        """Warn if job is running long."""
        # In a real system, compare actual elapsed vs estimated
        # For now, just predict based on remaining steps
        remaining_time = self.tracker.predict_time_remaining()
        if remaining_time > 120:  # > 2 hours left
            return [Prediction(
                category="time",
                message=f"{remaining_time} minutes remaining. Consider breaking for lunch before reassembly.",
                urgency="low",
                step_ahead=0,
                confidence=0.60,
                action="plan_break",
            )]
        return []

    # ─── Helpers ───────────────────────────────────────────────────────────────

    def _classify_warning_urgency(self, warning_text: str) -> str:
        """Classify warning urgency from text content."""
        text = warning_text.lower()
        critical_signals = ["interference", "do not rotate", "must replace", "must be", "do not reuse", "critical"]
        high_signals = ["do not", "never", "always", "danger", "burn", "hot", "toxic"]

        if any(s in text for s in critical_signals):
            return "critical"
        if any(s in text for s in high_signals):
            return "high"
        return "normal"

    def _load_mistakes_db(self) -> dict[str, list[str]]:
        """Common mistakes database. In production, load from JSON."""
        return {
            "toyota_5sfe__water_pump_timing_belt": [
                "Forgetting to hold tensioner while tightening bolt — spring relaxes, belt goes slack",
                "Using impact gun to tighten crank bolt — stretches unevenly, may snap",
                "Installing belt without verifying both timing marks — interference engine, valves will hit",
                "Overtightening water pump bolts in aluminum block — strips threads",
                "Forgetting to bleed coolant properly — air pocket causes overheating on test drive",
            ],
            "subaru_ej25_sohc__head_gasket": [
                "Reusing TTY head bolts — clamping force drops, gasket leaks again",
                "Using composite head gasket instead of MLS — guaranteed repeat failure",
                "Not cleaning deck surface thoroughly — oil residue causes immediate leak",
                "Forgetting angle gauge — ft-lb alone insufficient for TTY bolts",
                "Not replacing valve cover gaskets while heads are off — leaks in 6 months",
            ],
            "subaru_ej25_sohc__timing_belt": [
                "Rotating crank or cam with belt off — interference engine, bent valves",
                "Not marking belt direction — reversed belt wears differently",
                "Forgetting to tension spring on tensioner — belt slips, jumps timing",
            ],
        }

    def export_predictions(self, path: str | Path) -> None:
        """Export current predictions to JSON for external display."""
        data = {
            "workflow": self.tracker.workflow.slug,
            "step": self.tracker.state.current_step_idx,
            "predictions": [p.to_dict() for p in self.predict()],
            "summary": self.predict_next_step_summary(),
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─── Convenience Functions ─────────────────────────────────────────────────────

def predict_for_job(tracker: WorkflowTracker) -> list[Prediction]:
    """One-shot prediction for a tracker."""
    predictor = NextStepPredictor(tracker)
    return predictor.predict()


def hud_summary(tracker: WorkflowTracker) -> dict[str, Any]:
    """Heads-up display summary — one dict for display on tablet/phone."""
    predictor = NextStepPredictor(tracker)
    return predictor.predict_next_step_summary()
