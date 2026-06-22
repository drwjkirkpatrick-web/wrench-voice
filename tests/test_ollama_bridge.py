"""
test_ollama_bridge.py
=====================
Tests for the Ollama bridge: intent classification, command parsing, and QA.
Uses mock mode to avoid requiring a running Ollama instance.
"""

import pytest

from wrench_voice.ollama_bridge import (
    OllamaBridge,
    NLUResult,
    WorkflowQAContext,
    quick_intent,
)
from wrench_voice.repair_workflow import RepairWorkflowRegistry, WorkflowTracker


class TestOllamaBridgeMock:
    """Test with mock mode (no Ollama required)."""

    @pytest.fixture
    def bridge(self):
        return OllamaBridge(mock_mode=True)

    def test_mock_chat_returns_text(self, bridge):
        result = bridge.chat("What torque for water pump bolts?")
        assert "water pump bolts" in result.lower()
        assert "10mm" in result or "14" in result

    def test_mock_generate_returns_text(self, bridge):
        result = bridge.generate("Hello")
        assert len(result) > 0

    def test_classify_intent_torque(self, bridge):
        result = bridge.classify_intent("What's the torque on the tensioner bolt?")
        assert result.intent == "what_torque"
        assert result.confidence > 0.8

    def test_classify_intent_goto_step(self, bridge):
        result = bridge.classify_intent("Go to step 5")
        assert result.intent == "goto_step"
        assert result.action == "goto"
        assert result.action_params.get("step") == 5

    def test_classify_intent_advance(self, bridge):
        result = bridge.classify_intent("Next step")
        assert result.intent == "advance"
        assert result.action == "advance"

    def test_parse_command_goto(self, bridge):
        result = bridge.parse_command("Go to step 7")
        assert result.action == "goto"
        assert result.action_params.get("step") == 7

    def test_parse_command_advance(self, bridge):
        result = bridge.parse_command("Next step please")
        assert result.action == "advance"

    def test_summarize_symptoms(self, bridge):
        result = bridge.summarize_symptoms("It's knocking when I accelerate and the oil light flickers")
        assert result.intent == "symptom_summary"
        assert result.confidence > 0.5

    def test_answer_procedure_question(self, bridge):
        ctx = WorkflowQAContext(
            engine_slug="toyota_5sfe",
            symptom="water_pump_timing_belt",
            current_step=7,
            total_steps=16,
            step_title="Remove Timing Belt Tensioner & Belt",
            step_description="Loosen tensioner bolt...",
            fasteners=[{"description": "Tensioner bolt", "drive": "14mm socket", "torque": "32 ft-lb"}],
            tools=["14mm socket", "torque wrench"],
            progress_pct=37.5,
        )
        result = bridge.answer_procedure_question("Do I need to replace the tensioner?", ctx)
        assert len(result.response) > 0
        assert result.confidence > 0.5

    def test_transcribe_to_intent_command(self, bridge):
        reg = RepairWorkflowRegistry()
        wf = reg.get("toyota_5sfe", "water_pump_timing_belt")
        tracker = WorkflowTracker(wf)
        for _ in range(6):
            tracker.advance()
        ctx = WorkflowQAContext(
            engine_slug="toyota_5sfe",
            symptom="water_pump_timing_belt",
            current_step=tracker.current_step.step_number if tracker.current_step else 0,
            total_steps=len(wf.steps),
            step_title=tracker.current_step.title if tracker.current_step else "",
            step_description=tracker.current_step.description if tracker.current_step else "",
            progress_pct=tracker.progress_pct(),
        )
        result = bridge.transcribe_to_intent("Go to step 10", ctx)
        assert result.action == "goto"

    def test_unknown_intent_fallback(self, bridge):
        result = bridge.classify_intent("The weather is nice today")
        assert result.intent == "general_question" or result.intent == "unknown"

    def test_parse_json_from_markdown(self, bridge):
        raw = 'Some text before ```json\n{"intent": "what_tool", "confidence": 0.9}\n``` after'
        result = bridge._parse_nlu_json(raw, "test")
        assert result.intent == "what_tool"
        assert result.confidence == 0.9

    def test_parse_json_plain(self, bridge):
        raw = '{"intent": "goto_step", "confidence": 0.95, "action": "goto", "action_params": {"step": 3}}'
        result = bridge._parse_nlu_json(raw, "test")
        assert result.intent == "goto_step"
        assert result.action_params["step"] == 3

    def test_parse_invalid_json_fallback(self, bridge):
        raw = "This is not json at all"
        result = bridge._parse_nlu_json(raw, "test")
        assert result.intent == "unknown"
        assert result.response == raw


class TestOllamaBridgeConnection:
    """Tests that verify Ollama connection (skipped if not available)."""

    def test_check_available(self):
        bridge = OllamaBridge()
        available = bridge.check_available()
        # This may be True or False depending on environment
        assert isinstance(available, bool)

    @pytest.mark.skipif(
        not OllamaBridge().check_available(),
        reason="Ollama not running"
    )
    def test_real_generate(self):
        bridge = OllamaBridge()
        result = bridge.generate("Say hello in one word.", system="You are helpful.")
        # May succeed or fail depending on model state; just verify it returns something
        assert len(result) > 0
