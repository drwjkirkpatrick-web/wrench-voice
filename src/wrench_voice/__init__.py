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
obd_bridge          OBD-II DTC reader + live data + freeze frame
job_scheduler       Bay scheduling, technician assignment, job tracking
inventory_manager   Parts inventory with bin locations, reorder alerts
price_tracker       Historical price tracking, trend detection
auto_order          Automated purchase order generation
vehicle_history     Per-VIN service record CRM
warranty_tracker    Part warranty + core return tracking
cost_analyzer       Job profitability: estimated vs. actual
digital_inspection  Photo-based inspection with PDF report
customer_notifier   SMS/email customer notifications
voice_gateway       Hot-resident STT/TTS gateway (faster-whisper, piper)
sms_billing         SMS billing reminders + AR aging

Integration Stubs
-----------------
quickbooks_sync     Invoice push to QuickBooks
quickbooks_sync     Stub for Carfax / AutoCheck
quickbooks_sync     Calendar sync (Google / Outlook)

Usage
-----
    from wrench_voice.diagnostic_engine import DiagnosticEngine
    from wrench_voice.parts_finder import PartsFinder
    from wrench_voice.voice_gateway import VoiceGateway

    diag = DiagnosticEngine()
    results = diag.diagnose("overheating_at_idle", make="Toyota", model="Camry", engine="2.2L")

    finder = PartsFinder()
    parts = finder.lookup("thermostat", make="Toyota", year=1996)

    voice = VoiceGateway(mock_mode=True)
    voice.warmup()
    result = voice.transcribe_audio("recording.wav")
"""

__version__ = "0.2.0"
