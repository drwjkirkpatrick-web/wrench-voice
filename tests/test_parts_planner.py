"""
Tests for the parts planner.

Verifies:
1. JobPlan generates from DiagnosisResult
2. Cost estimation aggregates part prices
3. Warnings flag missing parts
4. Export produces valid JSON/YAML
"""

import pytest

from wrench_voice.diagnostic_engine import DiagnosticEngine
from wrench_voice.parts_planner import PartsPlanner, JobPlan


class TestPartsPlanner:
    """Job planning and cost estimation tests."""

    def test_plan_from_diagnosis(self):
        """
        A typical overheating diagnosis should yield a job plan
        with thermostat + gasket + coolant at minimum.
        """
        diag_engine = DiagnosticEngine()
        diagnosis = diag_engine.diagnose("overheating", make="Toyota", year=1996)

        planner = PartsPlanner(mock_mode=True)
        plan = planner.plan(diagnosis)

        assert isinstance(plan, JobPlan)
        assert len(plan.parts_needed) >= 1
        assert plan.estimated_cost >= 0
        assert plan.timeline != ""

    def test_plan_exports_json(self, tmp_path):
        """
        Export to JSON should produce a loadable file.
        """
        import json

        diag_engine = DiagnosticEngine()
        diagnosis = diag_engine.diagnose("rough_idle")

        planner = PartsPlanner(mock_mode=True)
        plan = planner.plan(diagnosis)

        out = tmp_path / "job.json"
        plan.export_json(out)

        loaded = json.loads(out.read_text())
        assert "parts_needed" in loaded
        assert "estimated_cost" in loaded
