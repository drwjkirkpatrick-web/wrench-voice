#!/usr/bin/env python3
"""
wrench-voice CLI
================
Command-line interface for the wrench-voice mechanic assistant.

Commands
--------
diagnose    Run a diagnostic query interactively or from args
parts       Look up part availability and pricing
plan        Plan parts for a pending job
kb          Search the knowledge base
serve       Start a lightweight local voice gateway (future)
"""

import sys
from pathlib import Path

# Ensure src/ is on path for local development
sys.path.insert(0, str(Path(__file__).parent.parent))

import click


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Wrench Voice — combustion engine repair assistant."""
    pass


@main.command()
@click.argument("symptom")
@click.option("--make", "-m", help="Vehicle make (e.g. Toyota)")
@click.option("--model", "-M", help="Vehicle model (e.g. Camry)")
@click.option("--engine", "-e", help="Engine code or displacement (e.g. 2.2L)")
@click.option("--year", "-y", type=int, help="Model year")
def diagnose(symptom: str, make: str | None, model: str | None, engine: str | None, year: int | None) -> None:
    """Diagnose a symptom."""
    from wrench_voice.diagnostic_engine import DiagnosticEngine

    diag = DiagnosticEngine()
    results = diag.diagnose(
        symptom_slug=symptom,
        make=make,
        model=model,
        engine=engine,
        year=year,
    )
    click.echo(results.to_markdown())


@main.command()
@click.argument("part_name")
@click.option("--make", "-m", help="Vehicle make")
@click.option("--year", "-y", type=int, help="Model year")
@click.option("--engine", "-e", help="Engine code")
def parts(part_name: str, make: str | None, year: int | None, engine: str | None) -> None:
    """Look up part availability and pricing."""
    from wrench_voice.parts_finder import PartsFinder

    finder = PartsFinder()
    results = finder.lookup(part_name, make=make, year=year, engine=engine)
    for r in results:
        click.echo(f"{r.supplier}: {r.part_number} — ${r.price:.2f}  ({r.availability})")


@main.command()
@click.argument("job_file", type=click.Path(exists=True, path_type=Path))
def plan(job_file: Path) -> None:
    """Plan parts for a pending job described in a YAML or JSON file."""
    from wrench_voice.parts_planner import PartsPlanner

    planner = PartsPlanner()
    plan_result = planner.plan_from_file(job_file)
    click.echo(plan_result.to_markdown())


@main.command()
@click.argument("query")
def kb(query: str) -> None:
    """Search the knowledge base for procedures, specs, or torque values."""
    from wrench_voice.kb import KnowledgeBase

    kbase = KnowledgeBase()
    results = kbase.search(query)
    for r in results[:10]:
        click.echo(f"{r.score:.2f}  {r.title}\n    {r.snippet}\n")


@main.command()
@click.option("--port", "-p", default="/dev/ttyUSB0", help="OBD adapter serial port")
@click.option("--mock", is_flag=True, help="Simulate OBD data (no adapter needed)")
def obd(port: str, mock: bool) -> None:
    """Perform an OBD-II scan: read codes, freeze frame, readiness, live data."""
    from wrench_voice.obd_bridge import OBDBridge

    finder = OBDBridge(port=port, mock_mode=mock)
    result = finder.full_scan()
    click.echo(result.to_markdown())


@main.group()
def schedule():
    """Shop scheduling and bay management."""
    pass

@schedule.command("board")
@click.option("--date", "-d", help="Show schedule for date (YYYY-MM-DD)")
def schedule_board(date: str | None) -> None:
    """Show bay board for today or a specific date."""
    from wrench_voice.job_scheduler import JobScheduler
    sched = JobScheduler()
    board = sched.bay_board(date)
    for bay_id, jobs in board.items():
        click.echo(f"\n{'='*40}")
        click.echo(f"Bay: {bay_id}")
        for j in jobs:
            click.echo(f"  {j.scheduled_start} | {j.customer} | {j.symptom} | {j.status}")
    click.echo(f"\nShop Stats: {sched.stats()}")

@schedule.command("add")
@click.option("--customer", "-c", required=True)
@click.option("--vin")
@click.option("--year", type=int)
@click.option("--make", "-m")
@click.option("--model", "-M")
@click.option("--engine", "-e")
@click.option("--symptom", "-s", required=True)
@click.option("--bay", "-b")
@click.option("--tech", "-t")
@click.option("--start", required=True, help="ISO datetime (e.g. 2025-08-01T08:00:00)")
@click.option("--duration", type=int, required=True, help="Minutes")
@click.option("--priority", type=int, default=2)
def schedule_add(customer: str, vin: str, year: int, make: str, model: str, engine: str,
                   symptom: str, bay: str, tech: str, start: str, duration: int, priority: int) -> None:
    from wrench_voice.job_scheduler import JobScheduler
    sched = JobScheduler()
    ticket = sched.schedule_job(
        customer=customer, vin=vin, year=year, make=make, model=model, engine=engine,
        symptom=symptom, bay_id=bay, technician=tech,
        scheduled_start=start, estimated_duration_min=duration, priority=priority,
    )
    click.echo(f"Scheduled: {ticket.ticket_id}")

@main.group()
def inventory():
    """Parts inventory management."""
    pass

@inventory.command("add")
@click.option("--sku", required=True)
@click.option("--part-number", required=True)
@click.option("--part-name", required=True)
@click.option("--qty", type=int, required=True)
@click.option("--price", type=float, required=True)
@click.option("--supplier", default="unknown")
@click.option("--bin", required=True)
@click.option("--min", type=int, default=0)
@click.option("--max", type=int, default=0)
def inv_add(sku: str, part_number: str, part_name: str, qty: int, price: float,
            supplier: str, bin: str, min: int, max: int) -> None:
    from wrench_voice.inventory_manager import InventoryManager
    inv = InventoryManager()
    item = inv.receive(sku, part_number, part_name, qty, price, supplier, bin, min, max)
    click.echo(f"Received: {item.sku} — {item.part_name} x{item.qty_on_hand} @ ${item.unit_cost:.2f}")

@inventory.command("search")
@click.argument("query")
def inv_search(query: str) -> None:
    from wrench_voice.inventory_manager import InventoryManager
    inv = InventoryManager()
    results = inv.search(query)
    for r in results:
        click.echo(f"{r.sku}: {r.part_name} | Qty: {r.qty_on_hand} | Bin: {r.bin_location} | ${r.unit_cost:.2f}")

@inventory.command("low")
def inv_low() -> None:
    from wrench_voice.inventory_manager import InventoryManager
    inv = InventoryManager()
    alerts = inv.low_stock_alerts()
    click.echo(f"Low stock alerts: {len(alerts)}")
    for a in alerts:
        click.echo(f"  {a.sku}: {a.part_name} — {a.qty_on_hand} left (reorder at {a.reorder_min})")

@main.group()
def price():
    """Price tracking and comparison."""
    pass

@price.command("history")
@click.argument("sku")
@click.option("--supplier", "-s")
def price_history(sku: str, supplier: str | None) -> None:
    from wrench_voice.price_tracker import PriceTracker
    pt = PriceTracker()
    t = pt.trend(sku, supplier)
    if t:
        click.echo(f"Current: ${t.current_price:.2f} | 30d avg: ${t.avg_30d:.2f} | Trend: {t.trend} | Sale: {t.sale_detected}")
    else:
        click.echo("No price data. Use `wrench price record` to add observations.")

@price.command("record")
@click.argument("sku")
@click.argument("supplier")
@click.argument("price", type=float)
@click.option("--part-name", default="")
def price_record(sku: str, supplier: str, price: float, part_name: str) -> None:
    from wrench_voice.price_tracker import PriceTracker
    pt = PriceTracker()
    pt.record(sku, supplier, price, part_name)
    click.echo(f"Recorded: {sku} @ ${price:.2f} from {supplier}")

@main.group()
def vehicle():
    """Vehicle history and predictive maintenance."""
    pass

@vehicle.command("register")
@click.option("--vin", required=True)
@click.option("--customer", "-c", required=True)
@click.option("--year", type=int)
@click.option("--make", "-m")
@click.option("--model", "-M")
@click.option("--engine", "-e")
def veh_register(vin: str, customer: str, year: int, make: str, model: str, engine: str) -> None:
    from wrench_voice.vehicle_history import VehicleHistory
    vh = VehicleHistory()
    vh.register_vehicle(vin, customer, year, make, model, engine)
    click.echo(f"Registered: {vin} for {customer}")

@vehicle.command("visits")
@click.option("--vin", required=True)
def veh_visits(vin: str) -> None:
    from wrench_voice.vehicle_history import VehicleHistory
    vh = VehicleHistory()
    visits = vh.lookup(vin)
    for v in visits[:5]:
        click.echo(f"{v['date']}: {v['symptom']} — {v['diagnosis']} (${v['cost_parts']:.0f})")

@vehicle.command("alerts")
@click.option("--vin", required=True)
@click.option("--odometer", type=int, required=True)
def veh_alerts(vin: str, odometer: int) -> None:
    from wrench_voice.vehicle_history import VehicleHistory
    vh = VehicleHistory()
    alerts = vh.predictive_alerts(vin, odometer)
    for a in alerts:
        click.echo(f"[{a['urgency'].upper()}] {a['message']}")

@main.group()
def inspection():
    """Digital vehicle inspection."""
    pass

@inspection.command("create")
@click.option("--vin", required=True)
@click.option("--customer", "-c", required=True)
def insp_create(vin: str, customer: str) -> None:
    from wrench_voice.digital_inspection import DigitalInspection
    di = DigitalInspection()
    id = di.create_inspection(vin, customer)
    click.echo(f"Inspection created: {id}")

@inspection.command("report")
@click.option("--id", required=True)
def insp_report(id: str) -> None:
    from wrench_voice.digital_inspection import DigitalInspection
    di = DigitalInspection()
    r = di.generate_report(id)
    click.echo(f"Report for {r.get('vin', 'unknown')}: {len(r.get('recommendations', []))} recommendations")
    click.echo(f"Approved: ${r.get('total_approved', 0):.2f} | Pending: ${r.get('total_pending', 0):.2f}")

@main.group()
def voice():
    """Voice gateway: STT/TTS management."""
    pass

@voice.command("warmup")
@click.option("--stt", default="mock", help="STT backend")
@click.option("--tts", default="mock", help="TTS backend")
def voice_warmup(stt: str, tts: str) -> None:
    from wrench_voice.voice_gateway import VoiceGateway
    gw = VoiceGateway(stt_backend=stt, tts_backend=tts, mock_mode=(stt == "mock"))
    r = gw.warmup()
    click.echo(f"STT: {r['stt']} | TTS: {r['tts']}")

@voice.command("status")
def voice_status() -> None:
    from wrench_voice.voice_gateway import VoiceGateway
    gw = VoiceGateway(mock_mode=True)
    click.echo(gw.status())

@main.group()
def billing():
    """SMS billing reminders and accounts receivable."""
    pass

@billing.command("create")
@click.option("--id", required=True)
@click.option("--customer", "-c", required=True)
@click.option("--phone", required=True)
@click.option("--amount", type=float, required=True)
@click.option("--due-days", type=int, default=14)
def bill_create(id: str, customer: str, phone: str, amount: float, due_days: int) -> None:
    from wrench_voice.sms_billing import SMSBilling
    sb = SMSBilling(mock_mode=True)
    inv = sb.create_invoice(id, customer, phone, amount, due_days=due_days)
    click.echo(f"Invoice {id}: ${inv['total']:.2f} due {inv['due']}")

@billing.command("aging")
def bill_aging() -> None:
    from wrench_voice.sms_billing import SMSBilling
    sb = SMSBilling(mock_mode=True)
    report = sb.ar_aging()
    click.echo(f"Total unpaid: ${report['total_unpaid']:.2f} across {report['invoice_count']} invoices")
    for bucket, amt in report['buckets'].items():
        click.echo(f"  {bucket}: ${amt:.2f}")

@billing.command("overdue")
@click.option("--days", type=int, default=14)
def bill_overdue(days: int) -> None:
    from wrench_voice.sms_billing import SMSBilling
    sb = SMSBilling(mock_mode=True)
    for inv in sb.overdue_invoices(days):
        click.echo(f"{inv['invoice_id']}: {inv['customer']} — ${inv['total']:.2f} (issued {inv['issued']})")


@main.group()
def mic():
    """Live microphone capture and calibration."""
    pass

@mic.command("calibrate")
@click.option("--backend", default="mock", help="ALSA, pyaudio, or mock")
@click.option("--duration", type=float, default=2.0)
def mic_calibrate(backend: str, duration: float) -> None:
    from wrench_voice.microphone_input import MicrophoneInput
    m = MicrophoneInput(backend=backend)
    threshold = m.calibrate(duration_sec=duration)
    click.echo(f"Silence threshold set to {threshold:.1f} RMS")

@mic.command("record")
@click.option("--duration", type=float, default=5.0)
@click.option("--output", "-o", default="/tmp/wrench_recording.wav")
@click.option("--backend", default="mock")
def mic_record(duration: float, output: str, backend: str) -> None:
    from wrench_voice.microphone_input import MicrophoneInput
    m = MicrophoneInput(backend=backend)
    result = m.record_to_file(duration_sec=duration, out_path=output)
    click.echo(f"Saved {result.file_path}: {result.duration_sec:.2f}s, peak RMS={result.peak_rms:.1f}")
    m.close()


@main.group()
def scan():
    """Barcode scanner for parts intake and lookup."""
    pass

@scan.command("listen")
@click.option("--backend", default="mock", help="hid, camera, mock, or manual")
@click.option("--device")
def scan_listen(backend: str, device: str | None) -> None:
    from wrench_voice.barcode_scanner import BarcodeScanner
    scanner = BarcodeScanner(backend=backend, device=device)
    click.echo("Listening for barcodes... (Ctrl+C to stop)")
    try:
        scanner.start()
        while True:
            bc, ts = scanner.get_scan(timeout=2.0) or (None, None)
            if bc:
                click.echo(f"Scanned: {bc}")
                result = scanner.lookup_inventory(bc)
                if result.found:
                    click.echo(f"  In stock: {result.part_name} x{result.qty_on_hand} @ {result.bin_location}")
                else:
                    parts = scanner.lookup_parts(bc)
                    if parts:
                        click.echo(f"  Best price: {parts[0].get('supplier', 'N/A')} @ ${parts[0].get('price', 0):.2f}")
                    else:
                        click.echo("  Not in inventory or catalog")
    except KeyboardInterrupt:
        pass
    finally:
        scanner.close()


@main.group()
def audio():
    """TTS audio effects: normalization, EQ, compression, gate."""
    pass

@audio.command("process")
@click.argument("input_wav")
@click.argument("output_wav")
@click.option("--profile", default="garage", help="garage, office, outdoor, headphones, flat")
@click.option("--target-lufs", type=float, default=-16.0)
@click.option("--speed", type=float, default=1.0)
def audio_process(input_wav: str, output_wav: str, profile: str, target_lufs: float, speed: float) -> None:
    from wrench_voice.audio_effects import AudioEffects, AudioEffectsConfig
    import pathlib
    cfg = AudioEffectsConfig(profile=profile, target_lufs=target_lufs, speed=speed)
    fx = AudioEffects(cfg)
    raw = pathlib.Path(input_wav).read_bytes()
    processed = fx.process(raw)
    pathlib.Path(output_wav).write_bytes(processed)
    before = fx.measure_loudness(raw)
    after = fx.measure_loudness(processed)
    click.echo(f"Processed: {output_wav}")
    click.echo(f"  Loudness: {before:.1f} → {after:.1f} LUFS")
    click.echo(f"  Profile: {profile} | Speed: {speed}x")

@audio.command("measure")
@click.argument("input_wav")
def audio_measure(input_wav: str) -> None:
    from wrench_voice.audio_effects import AudioEffects
    import pathlib
    fx = AudioEffects()
    raw = pathlib.Path(input_wav).read_bytes()
    lufs = fx.measure_loudness(raw)
    click.echo(f"Integrated loudness: {lufs:.1f} LUFS")


if __name__ == "__main__":
    main()
