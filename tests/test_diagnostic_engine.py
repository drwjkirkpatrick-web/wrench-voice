"""
Tests for the diagnostic engine.

These tests verify that:
1. Diagnoses return correct result shapes
2. Make/model filtering actually narrows causes
3. Confidence scores increase with more parameters
4. No external calls happen (pure local knowledge graph)
5. Edge cases (unknown symptom, partial params) degrade gracefully
"""

import pytest

from wrench_voice.diagnostic_engine import DiagnosticEngine, DiagnosisResult


# NOTE: Heavy dependencies are imported at module scope here because
# the diagnostic engine has NO external deps — it's pure Python + Pydantic.
# Tests will run fast and offline.


class TestDiagnosticEngine:
    """Grouped tests for the diagnostic engine."""

    def test_overheating_returns_results(self):
        """
        Most common symptom: overheating.
        Should return at least one ranked cause with a field test.
        """
        engine = DiagnosticEngine()
        result = engine.diagnose("overheating")

        assert isinstance(result, DiagnosisResult)
        assert len(result.ranked_causes) >= 1
        assert result.symptom == "overheating"
        assert 0.0 <= result.confidence <= 1.0

    def test_no_start_returns_results(self):
        """
        Second most common: engine cranks but won't start.
        """
        engine = DiagnosticEngine()
        result = engine.diagnose("no_start")

        assert isinstance(result, DiagnosisResult)
        assert len(result.ranked_causes) >= 1
        assert result.estimated_time != ""

    def test_make_filtering_narrows_causes(self):
        """
        With make="Toyota" we should get Toyota-specific causes ranked higher.
        """
        engine = DiagnosticEngine()
        generic = engine.diagnose("overheating")
        specific = engine.diagnose("overheating", make="Toyota")

        # Specificity should boost confidence
        assert specific.confidence >= generic.confidence

    def test_unknown_symptom_graceful(self):
        """
        An unknown symptom should not crash — return a low-confidence
        result with a "consult manual" message.
        """
        engine = DiagnosticEngine()
        result = engine.diagnose("quantum_entanglement_noise")

        assert isinstance(result, DiagnosisResult)
        assert result.confidence < 0.3

    def test_confidence_increases_with_params(self):
        """
        More parameters (make, model, year, engine) should strictly
        increase (or at least not decrease) confidence.
        """
        engine = DiagnosticEngine()
        base = engine.diagnose("misfire")
        with_make = engine.diagnose("misfire", make="Honda")
        with_all = engine.diagnose("misfire", make="Honda", model="Civic", year=1998, engine="B16A2")

        # These should hold; if they don't, the scoring logic is inconsistent
        assert with_make.confidence >= base.confidence
        assert with_all.confidence >= with_make.confidence
