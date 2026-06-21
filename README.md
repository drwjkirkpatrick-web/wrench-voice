# 🔧 Wrench Voice

> **Hands-free voice assistant + shop management system for independent mechanic shops.**
>
> Diagnose by voice. Track every part. Schedule every bay. Bill by SMS.
> Built for combustion engines. Nothing else.

**Repository:** [github.com/drwjkirkpatrick-web/wrench-voice](https://github.com/drwjkirkpatrick-web/wrench-voice)

---

## Why Mechanics Need This

Running a small shop means juggling three jobs at once:
- **Under the hood:** Diagnosing, repairing, keeping cars moving
- **At the desk:** Ordering parts, chasing deliveries, managing inventory
- **On the phone:** Updating customers, sending estimates, collecting payment

**Wrench Voice automates the desk and the phone so the mechanic stays under the hood.**

It runs on a Raspberry Pi in the shop corner with a USB microphone.
Speak naturally. Get answers instantly. Hands stay free. Eyes stay on the engine.

---

## What It Does

### 🗣️ Voice-First Diagnostics

Speak a symptom. Get a ranked diagnosis with field tests.

> *Speak a symptom. Get a ranked diagnosis with field tests — hands-free, in under 3 seconds.*
>
> Wrench Voice understands natural mechanic language: symptoms, engine families, symptoms under specific conditions. It returns ranked causes, confidence scores, and step-by-step field tests without opening a manual or touching a keyboard.
>
> *Example: "Misfire on cold start, B18C1" → returns ignition coil, injector, compression test order, and parts lookup — all by voice.*

- 10 symptoms → 45+ ranked causes
- 23 engine families with torque specs, known issues, fluid capacities
- Confidence rises with make/model/year/engine specificity
- Pure local knowledge — works offline, no cloud dependency

### 🔌 OBD-II Integration

Plug in an ELM327 adapter. Scan codes instantly.

- 50+ DTCs in local knowledge base with probable causes and field tests
- Freeze frame data, readiness monitors, live sensor readings
- Severity grading: info → minor → major → critical
- Mock mode for training without hardware

### 📊 Shop Operations

| Feature | What It Solves |
|---------|----------------|
| **Bay Scheduling** | Never double-book a lift. Parts-checked before confirming. |
| **Inventory Manager** | Know exactly where every part lives (bin A3-2). Auto-reorder alerts. |
| **Price Tracker** | Detect fake sales. Track 90-day price history per supplier. |
| **Delivery Predictor** | Learn actual vs. promised delivery times. Order just-in-time. |
| **Auto-Order** | Generate purchase orders grouped by supplier for free shipping. |
| **Job Cost Analyzer** | See which jobs made money, which went over budget. |
| **Part Scorer** | Score parts on brand reputation, warranty, return rates. |
| **Vehicle History** | Per-VIN service records. Predictive maintenance alerts. |
| **Digital Inspection** | Photo-based inspections with customer approval via SMS. |
| **SMS Billing** | Automated payment reminders. AR aging reports. |
| **Customer Notifications** | Status updates, approval requests, pickup reminders via text. |
| **Warranty Tracker** | Never miss a warranty claim. Track core charge returns. |
| **Voice Gateway** | faster-whisper + piper-tts kept hot in RAM for sub-second response. |

### 🔗 Business Integrations (Ready to Wire)

- **QuickBooks** — Push invoices automatically
- **Carfax / AutoCheck** — Pull service history, verify odometer
- **Google Calendar / Outlook** — Tech schedules on their phones
- **Twilio** — Real SMS (currently mock-mode for development)

---

## Benefits Summary

### For the Mechanic
- **Hands-free operation** — Speak, don't type. Greasy fingers stay on wrenches.
- **Instant answers** — No flipping through manuals or waiting for web pages.
- **Offline capable** — Works in shops with no internet. All knowledge is local.
- **Combustion-only focus** — No EV confusion. Every answer is ICE-relevant.
- **Live microphone** — USB mic auto-calibrates to shop noise. Silence detection stops recording when you stop speaking.
- **Barcode scan by voice** — Scan a part box, hear instantly: "NGK plug, twelve on hand, bin A3-2."
- **Garage-tuned audio** — TTS voice is compressed, gated, and EQ'd to punch through air compressors and impact guns.

### For the Shop Owner
- **Reduce idle bay time** — Parts pre-checked before job confirmation.
- **Cut rush shipping costs** — Predictive ordering with learned delivery times.
- **Capture missed revenue** — Digital inspections increase average ticket.
- **Improve cash flow** — SMS billing reminders reduce accounts receivable days.
- **Know your numbers** — Job profitability, technician efficiency, margin by engine family.
- **Protect from liability** — Photo-documented pre-existing condition on every job.
- **Barcode-driven inventory** — Scan parts in, scan parts out. No typing. No mistakes.
- **Voice-printed inspection reports** — Customer gets a PDF with your voice annotations embedded.

### For the Customer
- **Transparency** — See photos of their worn brake pads. Understand why.
- **Convenience** — Approve work via text message. No phone tag.
- **Trust** — Predictive maintenance alerts prevent breakdowns.
- **Speed** — Work starts when parts arrive, not when the customer calls back.

### For the Bottom Line
- **Zero subscription cost** — Open source. Runs on a $50 Raspberry Pi.
- **Reduced part costs** — Price tracking reveals fake sales and best suppliers.
- **Higher first-visit fix rate** — Better diagnosis → fewer comebacks.
- **Shorter cycle time** — Scheduled bays + parts on hand = cars out faster.

---

## Quick Start

```bash
# Clone
git clone https://github.com/drwjkirkpatrick-web/wrench-voice.git
cd wrench-voice

# Install (editable, for development)
pip install -e .

# Diagnose by voice (or CLI)
wrench diagnose overheating --make Toyota --year 1996

# Scan OBD-II codes
wrench obd --mock           # Simulated scan for testing
wrench obd --port /dev/ttyUSB0  # Real ELM327 adapter

# Look up parts
wrench parts thermostat --make Toyota --year 1996

# Search knowledge base
timing chain torque specs

# Shop operations
wrench schedule board              # Today's bay assignments
wrench schedule add --customer "Jane Doe" --symptom "brakes" --start "2025-08-01T08:00:00" --duration 180
wrench inventory add --sku "NGK-BKR7E" --part-name "Spark Plug" --qty 12 --price 6.50 --bin "A3-2"
wrench inventory low               # Show low-stock alerts
wrench price record THERMO-22RE RockAuto 12.99 --part-name "Thermostat"
wrench price history THERMO-22RE  # 90-day trend analysis
wrench vehicle register --vin 1HGCM... --customer "Jane Doe" --year 2005 --make Honda --model Accord
wrench vehicle alerts --vin 1HGCM... --odometer 128000  # Predictive maintenance
wrench inspection create --vin 1HGCM... --customer "Jane Doe"
wrench billing create --id INV-001 --customer "Jane Doe" --phone "+155****4567" --amount 487.50
wrench billing aging               # Accounts receivable report
wrench voice warmup --stt mock --tts mock  # Preload voice models
```

### Hermes Agent Skill

```bash
# Load in any Hermes session
/skill wrench-voice

# Or preload on startup
hermes --skills wrench-voice
```

Auto-triggers on mechanic keywords. Provides voice-optimized responses:
- Short sentences (≤20 words)
- Numbers spoken aloud
- `[pause]` tokens for TTS pacing
- No markdown in spoken output

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Voice Input (USB Mic)                     │
│              faster-whisper (kept hot in RAM)               │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Diagnostic  │  │   OBD-II     │  │    Shop      │
│   Engine     │  │   Bridge     │  │  Scheduler   │
│              │  │              │  │              │
│ symptom→     │  │ DTC→causes   │  │ Bay board,   │
│ ranked       │  │ Freeze frame │  │ tech assign, │
│ causes→fix   │  │ Live data    │  │ parts check  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────┬───────┴─────────┐      │
                 ▼                 ▼      │
        ┌──────────────┐  ┌──────────────┐ │
        │ Parts Finder │  │   Inventory  │ │
        │ RockAuto/API │  │   Manager    │ │
        │ Local CSV    │  │ Bin tracking │ │
        │ SQLite cache │  │ Reorder alerts │ │
        └──────┬───────┘  └──────┬───────┘ │
               │                 │         │
               └────────┬────────┘         │
                        ▼                  │
               ┌──────────────┐           │
               │ PartsPlanner │           │
               │ BOM + timeline│           │
               │ Cost estimate│           │
               └──────┬───────┘           │
                      │                  │
       ┌──────────────┼──────────────────┘
       ▼              ▼
┌──────────────┐ ┌──────────────┐
│ Price Tracker│ │ Delivery     │
│ 90d history  │ │ Predictor    │
│ Sale detect  │ │ Learned ETA  │
└──────┬───────┘ └──────┬───────┘
       │                │
       └────────┬───────┘
                ▼
        ┌──────────────┐
        │  Auto-Order   │
        │ PO generation │
        │ Free shipping │
        │ consolidation │
        └──────┬───────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐
│Vehicle│  │Cost  │  │Warr- │
│History│  │Analy-│  │anty  │
│CRM    │  │zer   │  │Track │
└──┬────┘  └──┬───┘  └──┬───┘
   │          │         │
   └──────────┼─────────┘
              ▼
       ┌──────────────┐
       │Digital Insp-  │
       │ection         │
       │Photos + PDF   │
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │Customer Notif-│
       │ier + SMS      │
       │Billing        │
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │ Voice Output │
       │  piper-tts   │
       │ (kept hot)   │
       └──────────────┘
```

---

## Modules

| Module | What It Does | Benefit |
|--------|------------|---------|
| `diagnostic_engine` | Symptom → ranked causes → field tests → repair | Instant diagnosis without manuals |
| `kb` | 23 engine families, torque specs, fluid capacities, known issues | Offline access to shop manual data |
| `parts_finder` | Multi-supplier lookup with SQLite cache | Best price in seconds |
| `parts_planner` | BOM expansion + timeline + cost estimate | Accurate quotes, fewer surprises |
| `obd_bridge` | DTC reader, freeze frame, live data, readiness | Codes explained in plain English |
| `job_scheduler` | Bay scheduling, tech assignment, parts-check | Zero double-booking, idle bays filled |
| `inventory_manager` | Bin locations, min/max reorder, FIFO cost | Never hunt for parts again |
| `price_tracker` | 90-day price history, trend detection, alerts | Catch fake sales, buy low |
| `delivery_predictor` | Learned ETA per supplier/region/season | Just-in-time ordering |
| `auto_order` | Automated POs, free-ship consolidation | Cut shipping costs, save capital |
| `vehicle_history` | Per-VIN service records, predictive alerts | Customer retention, upsell opportunities |
| `digital_inspection` | Photo-based inspection, customer approval | Higher ticket average, liability protection |
| `customer_notifier` | SMS status updates, approval requests | Fewer phone calls, faster approvals |
| `sms_billing` | Automated reminders, AR aging, payment tracking | Improved cash flow |
| `warranty_tracker` | Warranty dates, core return deadlines | Stop losing money on unclaimed warranties |
| `cost_analyzer` | Actual vs. estimated costs, margins | Know which jobs make money |
| `part_scorer` | Brand reputation + return rate + warranty scoring | Buy quality parts, reduce comebacks |
| `voice_gateway` | faster-whisper STT + piper-tts, kept hot in RAM | Sub-second voice response |
| `microphone_input` | Live USB/ALSA mic capture with silence detection | Hands-free in noisy shop |
| `barcode_scanner` | USB HID + camera barcode for parts lookup | Instant inventory, no typing |
| `audio_effects` | Normalization, EQ, compression, gate for TTS | Audible over air compressors |
| `quickbooks_sync` | Invoice push to QuickBooks (stub) | Eliminate double-entry |
| `carfax_stub` | Vehicle history lookup (stub) | Verify odometer, check for frame damage |
| `calendar_stub` | Google/Outlook sync (stub) | Tech schedules on their phones |

---

## Knowledge Base: 23 Engine Families

| Engine | Era | Vehicles |
|--------|-----|----------|
| **Toyota 22RE** | 1983–2004 | Pickup, 4Runner |
| **Toyota 2JZ-GE/GTE** | 1991–2007 | Supra MKIV, GS300, IS300 |
| **Toyota 1MZ-FE** | 1994–2006 | Camry, Avalon, Sienna, ES300 |
| **Toyota 1ZZ-FE / 2ZZ-GE** | 1998–2008 | Corolla, Matrix, Celica, Elise |
| **Toyota 2GR-FE** | 2004–present | Camry, Avalon, Highlander, RX350 |
| **Toyota 5VZ-FE** | 1995–2004 | Tacoma, 4Runner, Tundra, T100 |
| **Toyota 2TR-FE** | 2004–present | Tacoma, 4Runner, Hilux |
| **Toyota 3S-GTE** | 1986–2007 | Celica GT-Four, MR2 Turbo |
| **Toyota 1UZ-FE / 2UZ-FE** | 1989–2009 | LS400, Land Cruiser, Tundra, Sequoia |
| **Toyota 7M-GE/GTE** | 1986–1992 | Supra MK3, Cressida |
| **Honda B-Series** | 1988–2001 | Civic, Integra, CR-V |
| **Honda D-Series** | 1984–2005 | Civic, CR-X, Del Sol |
| **Honda F-Series** | 1989–2002 | Accord, Prelude, Odyssey |
| **Honda H-Series** | 1992–2001 | Prelude, Accord |
| **Honda J-Series** | 1996–present | Accord, Odyssey, Pilot, TL, MDX |
| **Honda K-Series** | 2001–present | Civic, CR-V, Accord, TSX, RSX |
| **Honda R-Series** | 2006–2015 | Civic 1.8 |
| **Ford 300 I6** | 1965–1996 | F-150, E-150 |
| **Chevy Small Block V8** | 1955–2003 | Trucks, Camaro, Corvette |
| **Jeep 4.0 I6** | 1987–2006 | Wrangler, Cherokee |
| **Nissan KA24DE** | 1997–2004 | Frontier, Xterra |
| **Mazda Rotary 13B** | 1974–2012 | RX-7, RX-8 |
| **BMW M54** | 2000–2006 | E46, E39, X3, Z4 |

Each file includes: overview, known issues, torque specs tables, fluid capacities, maintenance schedule, common procedures, special tools, and common mistakes.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| CLI | Click |
| Data | Pydantic v2 + SQLite |
| Web Scraping | httpx + BeautifulSoup4 |
| STT | faster-whisper (default), openai-whisper |
| TTS | piper-tts (default), coqui-tts, pyttsx3 |
| Testing | pytest |
| Package | setuptools (PEP 621) |

---

## Installation

### Standalone (Shop Computer / Raspberry Pi)

```bash
# Basic install
pip install -e .

# With voice models (recommended for shop install)
pip install -e ".[voice]"  # faster-whisper, piper-tts

# With all extras
pip install -e ".[full]"
```

### Hermes Agent Skill

```bash
# Clone to Hermes skills directory
git clone https://github.com/drwjkirkpatrick-web/wrench-voice.git \
  ~/.hermes/skills/wrench-voice

# Activate
/skill wrench-voice
```

---

## Tests

```bash
# All tests — zero external API calls required
pytest tests/ -v

# Specific modules
pytest tests/test_diagnostic_engine.py -v
pytest tests/test_obd_bridge.py -v
pytest tests/test_shop_modules.py -v
```

All tests run in mock mode or with temp databases. No shop data is touched.

---

## Configuration

```bash
# Environment variables (add to ~/.bashrc or systemd unit)
export WRENCH_CACHE_DIR="$HOME/.cache/wrench-voice"
export WRENCH_STT_BACKEND="faster-whisper"  # or "mock"
export WRENCH_TTS_BACKEND="piper"           # or "mock"
export TWILIO_SID="your_sid"
export TWILIO_TOKEN="your_token"
export TWILIO_FROM="+15555555555"
export SHOP_PHONE="503-555-0100"
export SHOP_NAME="Wrench Auto"

# OBD adapter
export WRENCH_OBD_PORT="/dev/ttyUSB0"
```

---

## Voice Gateway: Hot-Resident Architecture

Traditional voice assistants load the STT model on every request. That takes 3–5 seconds.

**Wrench Voice loads once at startup and stays resident:**

```python
from wrench_voice.voice_gateway import VoiceGateway

gw = VoiceGateway(stt_backend="faster-whisper", tts_backend="piper")
gw.warmup()  # ~10 seconds at boot

# Now every interaction is < 500ms
result = gw.transcribe_audio("recording.wav")  # ~200ms
audio = gw.synthesize("Thermostat replacement complete.")  # ~300ms
```

- **Daemon mode:** Background thread continuously listens
- **Queue-based:** Other modules push audio chunks, pop transcriptions
- **Thread-safe:** Multiple bays can use the same gateway instance

---

## SMS Billing Workflow

```
Day 0:  Job complete → Invoice generated → SMS sent to customer
Day 7:  Gentle reminder: "Invoice due. Reply PAY or call shop."
Day 14: Firm reminder: "Overdue. Please pay to keep account current."
Day 30: Final notice: "Immediate attention required. Call shop."
Day 45: Flagged for collection follow-up call
```

Customer replies:
- **"YES" / "PAY"** → Triggers Stripe payment link (or records intent)
- **"CALL"** → Flagged for callback
- **"APPROVE"** → Digital inspection work authorized

---

## Roadmap

### Complete ✅
- [x] Core diagnostic engine (10 symptoms, 45+ causes)
- [x] Knowledge base (23 engine families: 10 Toyota, 6 Honda, 7 other)
- [x] Parts finder with SQLite caching
- [x] Parts planner with BOM expansion
- [x] OBD-II bridge (DTCs, freeze frame, live data, mock mode)
- [x] Bay scheduling with technician assignment
- [x] Inventory manager with bin tracking + barcode support
- [x] Price tracker with 90-day history and sale detection
- [x] Delivery predictor with learned ETAs
- [x] Auto-order generator with free-ship consolidation
- [x] Vehicle history CRM with predictive alerts
- [x] Digital inspection with photo + PDF workflow
- [x] Customer notifier with SMS templates
- [x] SMS billing with AR aging
- [x] Warranty and core return tracking
- [x] Job cost analyzer (estimate vs. actual)
- [x] Part quality scorer (brand + warranty + returns)
- [x] Voice gateway (faster-whisper + piper-tts, hot-resident)
- [x] Microphone input (ALSA/PyAudio/WAV)
- [x] Barcode scanner (USB HID + camera)
- [x] Audio effects (EQ, compression, gate for noisy shops)
- [x] Hermes skill integration

### In Progress
- [ ] Bluetooth OBD adapter support
- [ ] QuickBooks Online OAuth2 connection
- [ ] Google Calendar API sync
- [ ] Twilio webhook handler for inbound SMS
- [ ] Web dashboard (Flask/FastAPI for shop tablets)

### Planned
- [ ] More engine families: Chevy LS, BMW M50/M52, Subaru EJ, Ford Modular, Nissan RB/VQ
- [ ] ASE-style labor time integration
- [ ] Mobile app companion (React Native or PWA)
- [ ] Local LLM integration (Ollama for complex diagnostics)
- [ ] Fleet management module (multi-vehicle corporate accounts)

---

## Hardware Recommendations

| Component | Recommendation | Cost |
|-----------|---------------|------|
| Shop computer | Raspberry Pi 4 (4GB) | $55 |
| Microphone | USB Blue Snowball or similar | $50 |
| Speakers | Cheap USB speaker | $15 |
| OBD-II adapter | USB ELM327 or Bluetooth OBDLink MX+ | $15–$120 |
| Display (optional) | 7" touch LCD for bay tablets | $60 |
| **Total shop setup** | | **~$135–$240** |

---

## Community & Contributing

Issues, PRs, and engine-family contributions welcome.

**Engine family contributions are especially valued.** Each `.md` file in `kb/` needs:
- H1: Engine family name
- H2: Overview, Known Issues, Torque Specs, Fluid Capacities, Maintenance Schedule, Common Procedures
- Tables for torque specs and fluid capacities
- Metric + imperial where relevant

---

## License

MIT © Walker Kirkpatrick

> *Built by a mechanic, for mechanics.*
