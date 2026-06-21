"""
wrench-voice
============
Hands-free voice assistant for combustion engine repair.

Modules
-------
diagnostic_engine   Symptom → ranked causes → tests → repair procedure
parts_finder        Web search + price comparison across suppliers
parts_planner       Predict parts for diagnosed repairs, check inventory
kb                  Markdown knowledge base (engines, specs, procedures)

Usage
-----
    from wrench_voice.diagnostic_engine import DiagnosticEngine
    from wrench_voice.parts_finder import PartsFinder

    diag = DiagnosticEngine()
    results = diag.diagnose("overheating_at_idle", make="Toyota", model="Camry", engine="2.2L")

    finder = PartsFinder()
    parts = finder.lookup("thermostat", make="Toyota", year=1996)
"""

__version__ = "0.1.0"
