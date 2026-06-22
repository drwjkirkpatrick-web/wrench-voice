"""
test_repair_workflow.py
=======================
Test the repair workflow, tool matcher, and predictor modules.
"""

import pytest

from wrench_voice.repair_workflow import (
    RepairWorkflowRegistry,
    WorkflowTracker,
    ToolMatcher,
    FastenerSpec,
    RepairStep,
    RepairWorkflow,
)
from wrench_voice.workflow_predictor import NextStepPredictor, predict_for_job, hud_summary


class TestToolMatcher:
    """Tool resolution by engine family."""

    def test_toyota_5sfe_socket_set(self):
        matcher = ToolMatcher("toyota_5sfe")
        tools = matcher.resolve("socket set")
        assert "10mm socket" in tools
        assert "14mm socket" in tools
        # 19mm is the largest in the set; 22mm is for timing-belt crank bolt
        assert "19mm socket" in tools
        # Verify timing belt category has crank pulley tool
        timing_tools = matcher.resolve("timing belt")
        assert any("crank" in t.lower() for t in timing_tools)

    def test_subaru_ej25_head_gasket_tools(self):
        matcher = ToolMatcher("subaru_ej25_sohc")
        tools = matcher.resolve("head gasket")
        assert any("cam sprocket" in t.lower() for t in tools)
        assert any("RTV" in t for t in tools)

    def test_unknown_family_falls_back(self):
        matcher = ToolMatcher("unknown_engine")
        tools = matcher.resolve("socket set")
        assert len(tools) >= 3  # Generic fallback

    def test_resolve_all_dedupes(self):
        matcher = ToolMatcher("toyota_5sfe")
        combined = matcher.resolve_all(["socket set", "torque critical", "general"])
        # Should have deduped specific tools
        assert len(combined) >= 5


class TestWorkflowTracker:
    """Step-by-step progression through a repair."""

    @pytest.fixture
    def camry_tracker(self):
        reg = RepairWorkflowRegistry()
        wf = reg.get("toyota_5sfe", "water_pump_timing_belt")
        return WorkflowTracker(wf)

    def test_initial_state(self, camry_tracker):
        assert camry_tracker.progress_pct() == 0.0
        assert camry_tracker.has_next()
        step = camry_tracker.current_step
        assert step.step_number == 1
        assert "Safety" in step.title

    def test_advance_sets_flags(self, camry_tracker):
        tracker = camry_tracker
        tracker.advance()  # Step 1: Safety & Prep
        assert "vehicle_lifted" in tracker.state.flags
        assert "battery_disconnected" in tracker.state.flags

    def test_skip_step(self, camry_tracker):
        tracker = camry_tracker
        tracker.skip("Already lifted")
        assert tracker.state.skipped_steps == [1]
        assert tracker.current_step.step_number == 2

    def test_go_back(self, camry_tracker):
        tracker = camry_tracker
        tracker.advance()
        tracker.advance()
        tracker.go_back()
        assert tracker.current_step.step_number == 2

    def test_predict_time_remaining(self, camry_tracker):
        tracker = camry_tracker
        initial = tracker.predict_time_remaining()
        tracker.advance()
        after = tracker.predict_time_remaining()
        assert after < initial

    def test_predict_next_tools(self, camry_tracker):
        tracker = camry_tracker
        tools = tracker.predict_next_tools(2)
        assert len(tools) >= 2
        # Step 1 needs jack stands, Step 2 needs catch pan
        assert any("jack" in t.lower() for t in tools)

    def test_predict_next_fasteners(self, camry_tracker):
        tracker = camry_tracker
        # At Step 1, fastener lookahead should see Steps 1-4
        fasteners = tracker.predict_next_fasteners(4)
        assert len(fasteners) >= 2
        # Should include crank pulley bolt (87 ft-lb) in Step 4
        big_torque = [f for f in fasteners if f.torque_ft_lbs and f.torque_ft_lbs > 50]
        assert len(big_torque) >= 1

    def test_predict_next_warning(self, camry_tracker):
        tracker = camry_tracker
        warning = tracker.predict_next_warning()
        assert warning is not None
        assert "cold" in warning.lower() or "burn" in warning.lower()

    def test_progress_tracking(self, camry_tracker):
        tracker = camry_tracker
        assert tracker.progress_pct() == 0.0
        for _ in range(8):
            if tracker.has_next():
                tracker.advance()
        assert tracker.progress_pct() > 40

    def test_is_prerequisite_met(self, camry_tracker):
        tracker = camry_tracker
        assert not tracker.is_prerequisite_met("coolant_drained")
        tracker.advance()  # Step 1
        tracker.advance()  # Step 2: Drain Coolant
        assert tracker.is_prerequisite_met("coolant_drained")

    def test_status_summary(self, camry_tracker):
        tracker = camry_tracker
        summary = tracker.status_summary()
        assert summary["workflow"].endswith("water_pump_timing_belt")
        assert summary["current_step"] == 1
        assert summary["time_remaining_min"] > 0
        assert "next_tools" in summary
        assert "next_fasteners" in summary


class TestPredictor:
    """Next-step prediction engine."""

    @pytest.fixture
    def camry_predictor(self):
        reg = RepairWorkflowRegistry()
        wf = reg.get("toyota_5sfe", "water_pump_timing_belt")
        tracker = WorkflowTracker(wf)
        return NextStepPredictor(tracker)

    def test_predict_returns_sorted_by_urgency(self, camry_predictor):
        predictions = camry_predictor.predict()
        # Critical warnings should come first
        urgencies = [p.urgency for p in predictions]
        if "critical" in urgencies:
            assert urgencies.index("critical") < urgencies.index("normal")

    def test_predict_next_step_summary(self, camry_predictor):
        summary = camry_predictor.predict_next_step_summary()
        assert summary["status"] == "ACTIVE"
        assert summary["step"] == 1
        assert "tools_now" in summary
        assert "fasteners_now" in summary
        assert "predictions" in summary

    def test_predict_fastener_prefetch(self, camry_predictor):
        predictions = camry_predictor.predict()
        fastener_preds = [p for p in predictions if p.category == "fastener"]
        assert len(fastener_preds) >= 1
        # Should include torque values
        assert any("ft-lb" in p.message for p in fastener_preds)

    def test_predict_warning_lookahead(self, camry_predictor):
        predictions = camry_predictor.predict()
        warning_preds = [p for p in predictions if p.category == "warning"]
        assert len(warning_preds) >= 1
        # Should see the interference engine warning
        assert any("interference" in p.message.lower() for p in warning_preds)

    def test_predict_mistakes(self, camry_predictor):
        predictions = camry_predictor.predict()
        mistake_preds = [p for p in predictions if "mistake" in p.message.lower()]
        assert len(mistake_preds) >= 1
        # Should warn about impact gun on crank bolt
        assert any("impact" in p.message.lower() for p in mistake_preds)

    def test_hud_summary(self, camry_predictor):
        summary = hud_summary(camry_predictor.tracker)
        assert summary["status"] == "ACTIVE"
        assert summary["progress_pct"] == 0.0

    def test_predict_export(self, camry_predictor, tmp_path):
        path = tmp_path / "predictions.json"
        camry_predictor.export_predictions(path)
        import json
        data = json.loads(path.read_text())
        assert "predictions" in data
        assert "summary" in data


class TestRepairWorkflowRegistry:
    """Workflow loading and retrieval."""

    def test_get_existing_workflow(self):
        reg = RepairWorkflowRegistry()
        wf = reg.get("toyota_5sfe", "water_pump_timing_belt")
        assert wf is not None
        assert wf.engine_slug == "toyota_5sfe"
        assert len(wf.steps) >= 10

    def test_get_missing_workflow(self):
        reg = RepairWorkflowRegistry()
        wf = reg.get("nonexistent", "symptom")
        assert wf is None

    def test_list_for_engine(self):
        reg = RepairWorkflowRegistry()
        wfs = reg.list_for_engine("toyota_5sfe")
        assert len(wfs) >= 1

    def test_workflow_to_markdown(self):
        reg = RepairWorkflowRegistry()
        wf = reg.get("toyota_5sfe", "water_pump_timing_belt")
        md = wf.to_markdown()
        assert "# Toyota 5S-FE" in md
        assert "Step 1:" in md
        assert "Fasteners:" in md

    def test_subaru_head_gasket_loaded(self):
        reg = RepairWorkflowRegistry()
        wf = reg.get("subaru_ej25_sohc", "head_gasket")
        assert wf is not None
        assert wf.skill_level == "advanced"
        assert any("MLS" in c for c in wf.cautions)


class TestFastenerSpec:
    """Fastener data model."""

    def test_torque_str_standard(self):
        f = FastenerSpec("Test bolt", "M8", "13mm socket", 25.0, 34.0)
        assert "25.0 ft-lb / 34.0 Nm" in f.torque_str()

    def test_torque_str_hand_tight(self):
        f = FastenerSpec("Clip", "plastic", "fingers")
        assert f.torque_str() == "hand-tight"

    def test_torque_str_tty(self):
        f = FastenerSpec("Head bolt", "M10", "14mm 12-point", 36.0, 49.0, torque_type="TTY")
        assert "36.0 ft-lb" in f.torque_str()

    def test_fastener_quantity(self):
        f = FastenerSpec("Cover bolts", "M6", "10mm socket", 7.0, quantity=6)
        assert f.quantity == 6
