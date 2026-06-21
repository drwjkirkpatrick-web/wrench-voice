"""
Tests for shop operations modules: job_scheduler, inventory_manager,
price_tracker, delivery_predictor, auto_order, vehicle_history,
warranty_tracker, cost_analyzer, part_scorer, digital_inspection,
customer_notifier, voice_gateway, sms_billing, and integration stubs.

Uses SQLite in-memory or temp files to avoid pollution.
All lazy imports — module imports are instant.
"""

import pytest
import os
import tempfile
from datetime import datetime

# All tests use mock_mode or temp databases to remain hermetic


class TestJobScheduler:
    def test_add_bay_and_list(self):
        from wrench_voice.job_scheduler import JobScheduler, Bay
        sched = JobScheduler()
        sched.add_bay(Bay("b1", "Bay 1", "2-post_lift"))
        bays = sched.list_bays()
        assert len(bays) >= 1
        assert bays[0].bay_id == "b1"

    def test_schedule_job_and_retrieve(self):
        from wrench_voice.job_scheduler import JobScheduler
        sched = JobScheduler()
        ticket = sched.schedule_job(
            customer="Jane Doe", symptom="overheating",
            scheduled_start="2025-08-01T08:00:00",
            estimated_duration_min=240,
        )
        assert ticket.ticket_id.startswith("JOB-")
        retrieved = sched.get_ticket(ticket.ticket_id)
        assert retrieved is not None
        assert retrieved.customer == "Jane Doe"

    def test_status_flow(self):
        from wrench_voice.job_scheduler import JobScheduler
        sched = JobScheduler()
        t = sched.schedule_job(
            customer="Test", symptom="misfire",
            scheduled_start="2025-08-01T09:00:00", estimated_duration_min=60,
        )
        sched.mark_started(t.ticket_id)
        assert sched.get_ticket(t.ticket_id).status == "active"
        sched.mark_completed(t.ticket_id)
        assert sched.get_ticket(t.ticket_id).status == "completed"

    def test_stats(self):
        from wrench_voice.job_scheduler import JobScheduler
        sched = JobScheduler()
        stats = sched.stats()
        assert "total_jobs" in stats


class TestInventoryManager:
    def test_receive_and_get(self):
        from wrench_voice.inventory_manager import InventoryManager
        import uuid
        inv = InventoryManager()
        sku = f"NGK-{uuid.uuid4().hex[:8]}"
        item = inv.receive(sku, "BKR7E", "Spark Plug", 12, 6.50, "RockAuto", "A3-2", reorder_min=4, reorder_max=24)
        assert item.qty_on_hand == 12
        assert item.needs_reorder() == False

    def test_consume_and_shortage(self):
        from wrench_voice.inventory_manager import InventoryManager
        import uuid
        inv = InventoryManager()
        sku = f"TEST-OIL-{uuid.uuid4().hex[:8]}"
        inv.receive(sku, "5W30", "Oil", 5, 25.0, "Advance", "B1-1")
        inv.consume(sku, 3, "JOB-TEST", "Mike")
        item = inv.get_item(sku)
        assert item.qty_on_hand == 2

    def test_low_stock_alerts(self):
        from wrench_voice.inventory_manager import InventoryManager
        import uuid
        inv = InventoryManager()
        sku = f"LOW-{uuid.uuid4().hex[:8]}"
        inv.receive(sku, "L-001", "Rare Part", 2, 50.0, "RockAuto", "C2-3", reorder_min=5)
        alerts = inv.low_stock_alerts()
        assert any(a.sku == sku for a in alerts)

    def test_search(self):
        from wrench_voice.inventory_manager import InventoryManager
        import uuid
        inv = InventoryManager()
        sku = f"SEARCH-{uuid.uuid4().hex[:8]}"
        inv.receive(sku, "S-001", "Special Bolt", 20, 1.50, "OReilly", "D4-1")
        results = inv.search("Special")
        assert len(results) >= 1


class TestPriceTracker:
    def test_record_and_trend(self):
        from wrench_voice.price_tracker import PriceTracker
        pt = PriceTracker()
        pt.record("THERMO-22RE", "RockAuto", 12.99, "Thermostat")
        pt.record("THERMO-22RE", "RockAuto", 11.99, "Thermostat")
        t = pt.trend("THERMO-22RE", "RockAuto")
        assert t is not None
        assert t.current_price in (11.99, 12.99)

    def test_alert(self):
        from wrench_voice.price_tracker import PriceTracker
        pt = PriceTracker()
        pt.record("WATCH-ITEM", "RockAuto", 100.0, "Water Pump")
        pt.add_alert("WATCH-ITEM", "RockAuto", "below", 85.0)
        triggered = pt.check_alerts()
        # Not triggered yet
        assert len(triggered) == 0


class TestDeliveryPredictor:
    def test_no_data_fallback(self):
        from wrench_voice.delivery_predictor import DeliveryPredictor
        pred = DeliveryPredictor()
        result = pred.predict("NewSupplier", "97201", "brakes", promised=3)
        assert result["estimate_days"] == 4.5  # 3 * 1.5 fallback
        assert result["confidence"] == 0.0

    def test_record_and_predict(self):
        from wrench_voice.delivery_predictor import DeliveryPredictor
        pred = DeliveryPredictor()
        pred.record_actual("RockAuto", "972", "brakes", 3, 4)
        pred.record_actual("RockAuto", "972", "brakes", 3, 5)
        result = pred.predict("RockAuto", "97201", "brakes", promised=3)
        assert result["confidence"] > 0


class TestCostAnalyzer:
    def test_record_and_report(self):
        from wrench_voice.cost_analyzer import CostAnalyzer
        ca = CostAnalyzer()
        ca.record_estimate("JOB-CA-001", engine="22RE", symptom="overheating",
                             parts_cost_est=200, labor_hours_est=3.0, labor_rate=95)
        ca.record_actual("JOB-CA-001", parts_cost_actual=220, labor_hours_actual=3.5, billed_total=550)
        report = ca.job_report("JOB-CA-001")
        assert "flag" in report

    def test_monthly_summary(self):
        from wrench_voice.cost_analyzer import CostAnalyzer
        ca = CostAnalyzer()
        summary = ca.monthly_summary(datetime.now().strftime("%Y-%m"))
        assert "total_jobs" in summary


class TestPartScorer:
    def test_known_brand(self):
        from wrench_voice.part_scorer import PartScorer
        scorer = PartScorer()
        result = scorer.score("WP-22RE", "RockAuto", "AISIN", 45.0, warranty_years=2, part_category="water_pump")
        assert result["score"] > 70
        assert result["tier"] in ("excellent", "good")

    def test_unknown_brand(self):
        from wrench_voice.part_scorer import PartScorer
        scorer = PartScorer()
        result = scorer.score("WP-GENERIC", "eBay", "Unknown Brand", 9.99, warranty_years=0.5, part_category="water_pump")
        assert result["concerns"]  # Should flag unknown brand


class TestVehicleHistory:
    def test_register_and_lookup(self):
        from wrench_voice.vehicle_history import VehicleHistory
        vh = VehicleHistory()
        vh.register_vehicle("1HGCM82633A004352", "Jane Doe", 2005, "Honda", "Accord", "K24")
        vh.add_visit("1HGCM82633A004352", odometer=124500, symptom="overheating",
                      diagnosis="thermostat", parts_used=["thermostat", "coolant"],
                      labor_hours=1.2, cost_parts=45, cost_labor=114)
        visits = vh.lookup("1HGCM82633A004352")
        assert len(visits) >= 1
        assert visits[0]["symptom"] == "overheating"

    def test_predictive_alerts(self):
        from wrench_voice.vehicle_history import VehicleHistory
        import uuid
        vh = VehicleHistory()
        vin = f"1VIN{uuid.uuid4().hex[:12].upper()}"
        vh.register_vehicle(vin, "Jane Doe", 2005, "Honda", "Accord", "K24")
        vh.add_visit(vin, odometer=100000, symptom="brake pads worn",
                      diagnosis="replace brake pads", parts_used=["brake pads front"], labor_hours=1.5,
                      cost_parts=80, cost_labor=142)
        alerts = vh.predictive_alerts(vin, current_odometer=160000)
        brake_alerts = [a for a in alerts if "brake" in a["message"].lower()]
        assert len(brake_alerts) >= 1


class TestWarrantyTracker:
    def test_register_and_expiring(self):
        from wrench_voice.warranty_tracker import WarrantyTracker
        wt = WarrantyTracker()
        wid = wt.register_part("ALT-001", "Alternator", "RockAuto", warranty_months=24, core_charge=35.0)
        assert wid > 0
        exp = wt.expiring(days=9999)
        assert any(e["sku"] == "ALT-001" for e in exp)

    def test_overdue_cores(self):
        from wrench_voice.warranty_tracker import WarrantyTracker
        wt = WarrantyTracker()
        wt.register_part("CORE-001", "Starter", "Advance", core_charge=25.0, core_deadline_days=1)
        # This should appear in overdue cores since deadline is 1 day
        overdue = wt.overdue_cores(days=9999)
        assert any(o["sku"] == "CORE-001" for o in overdue)


class TestDigitalInspection:
    def test_create_and_report(self):
        from wrench_voice.digital_inspection import DigitalInspection
        di = DigitalInspection()
        iid = di.create_inspection("1HGCM82633A004352", "Jane Doe")
        di.add_photo(iid, "brakes", "/tmp/brake.jpg", condition="red",
                     text_note="Pads worn to 2mm")
        di.add_recommendation(iid, "Replace front brake pads", urgency="red", estimated_cost=340, category="brakes")
        r = di.generate_report(iid)
        assert r["vin"] == "1HGCM82633A004352"
        assert len(r["recommendations"]) == 1

    def test_customer_approval(self):
        from wrench_voice.digital_inspection import DigitalInspection
        import uuid
        di = DigitalInspection()
        vin = f"1VIN{uuid.uuid4().hex[:12].upper()}"
        iid = di.create_inspection(vin, "Jane Doe")
        rid = di.add_recommendation(iid, "Change oil", urgency="yellow", estimated_cost=65)
        di.customer_response(iid, approved=[rid], declined=[])
        r = di.generate_report(iid)
        assert r["viewed"] is True
        assert any(rec["status"] == "approved" for rec in r["recommendations"])


class TestCustomerNotifier:
    def test_mock_send(self):
        from wrench_voice.customer_notifier import CustomerNotifier
        notifier = CustomerNotifier(mock_mode=True)
        result = notifier.send("+15551234567", "Test message", "custom", "JOB-001")
        assert result["status"] == "sent"
        assert result["sid"].startswith("MOCK-")

    def test_templates(self):
        from wrench_voice.customer_notifier import CustomerNotifier
        notifier = CustomerNotifier(mock_mode=True)
        msg = notifier._render("job_complete", {"make": "Honda", "model": "Accord", "total": 487})
        assert "Accord" in msg
        assert "487" in msg


class TestVoiceGateway:
    def test_mock_warmup(self):
        from wrench_voice.voice_gateway import VoiceGateway
        gw = VoiceGateway(mock_mode=True)
        r = gw.warmup()
        assert r["stt"]["status"] == "mock"
        assert gw.is_warm()

    def test_mock_transcribe(self):
        from wrench_voice.voice_gateway import VoiceGateway
        gw = VoiceGateway(mock_mode=True)
        gw.warmup()
        result = gw.transcribe_audio("/dev/null")
        assert result.confidence > 0
        assert len(result.text) > 0

    def test_mock_synthesize(self):
        from wrench_voice.voice_gateway import VoiceGateway
        gw = VoiceGateway(mock_mode=True)
        gw.warmup()
        result = gw.synthesize("Hello mechanic")
        assert result.duration_sec > 0

    def test_daemon_mode(self):
        from wrench_voice.voice_gateway import VoiceGateway
        gw = VoiceGateway(mock_mode=True)
        gw.warmup()
        gw.start_daemon()
        assert gw._daemon_running
        gw.stop_daemon()
        assert not gw._daemon_running


class TestSMSBilling:
    def test_create_invoice(self):
        from wrench_voice.sms_billing import SMSBilling
        import uuid
        sb = SMSBilling(mock_mode=True)
        inv_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        inv = sb.create_invoice(inv_id, "Jane Doe", "+155****4567", 487.50, ticket_id="JOB-001")
        assert inv["invoice_id"] == inv_id
        assert inv["total"] == 487.50

    def test_mark_paid(self):
        from wrench_voice.sms_billing import SMSBilling
        import uuid
        sb = SMSBilling(mock_mode=True)
        inv_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        sb.create_invoice(inv_id, "John", "+155****6543", 250.0)
        sb.mark_paid(inv_id, "credit_card")
        report = sb.payment_stats()
        assert report["total_collected"] >= 250.0

    def test_ar_aging(self):
        from wrench_voice.sms_billing import SMSBilling
        import uuid
        sb = SMSBilling(mock_mode=True)
        inv_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        sb.create_invoice(inv_id, "Late", "+155****1111", 100.0, due_days=-30)
        aging = sb.ar_aging()
        assert "total_unpaid" in aging


class TestIntegrationStubs:
    def test_quickbooks_stub(self):
        from wrench_voice.quickbooks_sync import QuickBooksSync
        qb = QuickBooksSync(mock_mode=True)
        inv = qb.create_invoice("JOB-QB-001", "Jane Doe", [
            {"desc": "Water pump", "amount": 89.99},
            {"desc": "Labor 2.5 hrs", "amount": 237.50},
        ])
        assert inv.total == 327.49

    def test_carfax_stub(self):
        from wrench_voice.carfax_stub import CarfaxStub
        cf = CarfaxStub(mock_mode=True)
        r = cf.lookup("1HGCM82633A004352")
        assert r["vin"] == "1HGCM82633A004352"
        assert "owners" in r

    def test_calendar_stub(self):
        from wrench_voice.calendar_stub import CalendarStub
        cal = CalendarStub(mock_mode=True)
        evt = cal.create_event("JOB-CAL-001", "Timing Belt", "Bay 1", "Mike",
                               "2025-08-01T08:00:00", 240, "Jane", "Honda Accord")
        assert evt["bay"] == "Bay 1"
        assert len(cal.list_events("2025-08-01")) == 1


class TestAutoOrder:
    def test_generate_pos(self):
        from wrench_voice.auto_order import AutoOrder
        ao = AutoOrder()
        parts = [
            {"sku": "WP-22RE", "part_number": "WP-001", "part_name": "Water Pump",
             "supplier": "RockAuto", "qty_needed": 1, "unit_price": 45.0, "part_category": "water_pump"},
        ]
        pos = ao.generate_pos(parts, dest_zip="97201")
        assert len(pos) >= 1
        assert pos[0]["supplier"] == "RockAuto"

    def test_export_po(self):
        from wrench_voice.auto_order import AutoOrder
        ao = AutoOrder()
        po = {
            "supplier": "Test", "order_date": "2025-08-01", "need_by": "2025-08-05",
            "items": [{"sku": "X", "part_number": "PN", "part_name": "Name", "qty_needed": 1, "unit_price": 10}],
            "subtotal": 10.0, "shipping_estimate": 0.0,
            "delivery_estimate_days": 3, "confidence": 0.5, "recommendation": "test",
            "shipping_method": "standard", "free_ship_threshold": 49.0, "free_ship_achieved": False,
        }
        path = ao.export_po(po, fmt="json", out_path="/tmp/test_po.json")
        assert os.path.exists(path)
        os.unlink(path)
