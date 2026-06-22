# 🔧 Wrench Voice

> **The hands-free voice assistant and shop management system for independent mechanics.**
>
> Speak to your shop. It answers. Hands stay on wrenches. Eyes stay on the engine.
> Built for combustion engines only — and proud of it.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)
![Tests](https://img.shields.io/badge/tests-118%20passing-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Raspberry%20Pi-orange.svg)
![Status](https://img.shields.io/badge/status-v0.3.0%20Alpha-red.svg)
![Engine Families](https://img.shields.io/badge/engine%20families-54-yellow.svg)

**Repository:** [github.com/drwjkirkpatrick-web/wrench-voice](https://github.com/drwjkirkpatrick-web/wrench-voice)

---

## Picture This

You're under a hood. Hands are greasy. You need a torque spec, a part number, a delivery ETA, and a customer's approval — all at once.

Today, you wipe your hands, walk to a desk, open three browser tabs, call a parts counter, and lose four minutes. Multiply that by forty jobs a week. **That's over two hours every week spent at a desk instead of under a hood** — for every mechanic in the shop.

**Wrench Voice gives those hours back.**

It runs on a $55 Raspberry Pi in the corner of your shop, with a USB microphone. You speak naturally — the way you'd talk to a counterman. It answers in under a second. Your hands never touch a keyboard. Your eyes never leave the engine.

```
You:      "Misfire on cold start, B18C1, what's the top suspect?"
Wrench:  "Ignition coil. Seventy percent confidence. Common on this engine
          after eighty thousand miles. Want the field test, or should I
          pull parts and a repair plan?"
```

That's the whole experience. **You talk. It does the rest.**

---

## Who It's For

- **Independent shop owners** who want a bay scheduler, parts inventory, and SMS billing — without a monthly SaaS bill
- **Master mechanics** who want torque specs and repair workflows spoken aloud, not buried in a PDF
- **Driveway DIYers** who want guided step-by-step procedures with exact fastener sizes and torque values
- **Anyone who works on gas or diesel engines** and is tired of greasy fingers on a touchscreen

> **If it has spark plugs or injectors, Wrench Voice knows it.** If it has a battery pack and a motor, it doesn't — and that's a feature, not a limitation. Every answer is ICE-relevant. No EV confusion. No wasted scroll.

---

## What It Does

### 🗣️ Voice-First Diagnostics — *speak a symptom, get a ranked diagnosis*

Wrench Voice understands natural mechanic language. Symptoms, engine families, conditions, even VIN digit 8 for engine identification. It returns ranked causes with confidence scores and step-by-step field tests — no manual, no keyboard, no waiting.

```
You:      "Rough idle when cold, 1998 Camry 5S-FE"
Wrench:  "Top suspect: idle air control valve. Sixty-five percent.
          Second: coolant temp sensor. Third: vacuum leak at the
          intake manifold gasket. Want the quick test for the IAC,
          or should I plan the full diagnostic path?"
```

- **10 symptoms → 45+ ranked causes** with field tests and repair procedures
- **Confidence rises with vehicle specificity** — year, make, model, and engine family all feed the score
- **Pure local knowledge** — works offline, no cloud, no latency, no subscription
- **Mechanic-grade vocabulary** — "P0301", "freeze frame", "fuel trims", "TTY bolts" — it speaks your language

### 🔌 OBD-II Integration — *plug in an ELM327, scan codes by voice*

- **50+ DTCs** in the local knowledge base, each with probable causes, suggested tests, and severity grading (info → minor → major → critical)
- **Freeze frame data** — the snapshot of what the engine was doing when the code set
- **Readiness monitors** — emissions-test prep status
- **Live sensor data** — RPM, coolant temp, fuel trims, O2 voltage
- **Mock mode** — full simulated scan for training and demos without any hardware
- **Clear-and-verify workflow** — clear codes after repair, then confirm the fix with live data (fuel trims near zero, O2 oscillating, coolant stable)

### 📊 Shop Operations — *the desk work, automated*

| Module | What It Does | What It Saves You |
|--------|-------------|---------------------|
| **Bay Scheduling** | Jobs to bays with tech assignment; parts-checked before confirming | Never double-book a lift; zero idle bay time |
| **Inventory Manager** | Bin tracking, min/max reorder, FIFO cost, barcode lookup | Never hunt for a part again; "bin A3-2, twelve on hand" |
| **Price Tracker** | 90-day price history per supplier; sale detection | Catch fake sales; buy from the cheapest real source |
| **Delivery Predictor** | Learns actual vs. promised ETA per supplier, region, season | Order just-in-time; cut buffer stock |
| **Auto-Order** | Generates POs grouped by supplier for free-ship thresholds | Cut shipping costs; save working capital |
| **Job Cost Analyzer** | Actual vs. estimated costs, margins by job and engine family | Know which jobs make money — and which don't |
| **Part Scorer** | Scores parts on brand reputation, warranty, return rates | Buy quality; reduce comebacks |
| **Vehicle History** | Per-VIN service records, predictive maintenance alerts | Customer retention; upsell at the right mileage |
| **Digital Inspection** | Photo-based inspections with customer approval via SMS | Higher ticket average; liability protection |
| **SMS Billing** | Automated payment reminders, AR aging, payment tracking | Cash flow in, days sales outstanding down |
| **Customer Notifications** | Status updates, approval requests, pickup reminders by text | Fewer phone calls; faster approvals |
| **Warranty Tracker** | Warranty dates, core return deadlines, claim tracking | Stop losing money on unclaimed warranties and core charges |

### 🔧 Repair Workflows — *step-by-step procedures with exact fasteners*

This is the headline feature of v0.3.0. **Every bolt, every torque value, every tool — spoken aloud, step by step, hands-free.**

- **Exact fasteners per step**: description, size, drive type, torque (ft-lb + Nm), torque type (standard / TTY / angle), quantity, location
- **Tool matching by engine family**: "socket set" resolves to "10mm, 12mm, 14mm socket" for a Toyota 5S-FE
- **Prerequisite tracking**: the system knows `coolant_drained=True` before letting you touch the water pump
- **Next-step prediction**: "Coming up: 14mm socket, torque wrench, breaker bar" — before you ask
- **Critical warnings by urgency**: "🚨 In 2 steps: DO NOT rotate crank with belt OFF — interference engine"
- **Common-mistake alerts**: "Common mistake: impact gun on crank bolt — stretches unevenly"
- **Voice commands during a job**: "next step", "what size is the tensioner bolt?", "go to step 5", "what's coming up?", "status"

```
You:      "status"
Wrench:  "Progress thirty-seven percent. Step seven: remove timing belt.
          Sixteen steps total, one hundred twenty minutes remaining.
          [pause] Next tool: fourteen millimeter socket. Next fastener:
          tensioner bolt, thirty two foot-pounds. [pause] Critical in
          two steps: do not rotate crank with belt off — interference
          engine. Ready for step eight?"
```

### 🎙️ Voice Gateway — *hot-resident, sub-second response*

Traditional voice assistants load the speech model on every request. That takes 3–5 seconds. **Wrench Voice loads once at startup and stays resident in RAM.**

- **STT**: faster-whisper `base.en` (int8 quantization, CPU)
- **TTS**: piper-tts `en_US-lessac-medium`
- **Latency after warmup**: ~200ms transcription, ~300ms synthesis
- **Boot load**: ~10 seconds, one time
- **Daemon mode**: background thread, continuously listening
- **Thread-safe**: multiple bays can share one gateway instance

### 🎤 Live Microphone — *hands-free in a noisy shop*

- **ALSA / PyAudio / WAV backends** — lowest latency on Linux
- **RMS-based silence detection** with auto-stop — you speak, it records; you stop, it stops
- **16kHz sample rate** optimized for Whisper
- **Auto-calibration** — set the silence threshold to your shop's ambient noise in 2 seconds

### 🏷️ Barcode Scanner — *scan a part, hear the answer*

- **USB HID** (Linux evdev), **camera** (OpenCV + zxing), **mock**, or **manual** backends
- Scan a part box → instant voice announce: "NGK plug, twelve on hand, bin A3-2, six dollars fifty"
- Inventory DB auto-migrates to add barcode columns on first use

### 🔊 Garage-Tuned Audio — *audible over air compressors*

TTS output is normalized, compressed, gated, and EQ'd per room profile:
- **garage**: boost 2–5kHz speech clarity, cut 200Hz rumble, aggressive compression
- **office**: slight presence boost, moderate compression
- **outdoor**: bass boost for wind-noise immunity
- **headphones**: minimal processing, pure voice

---

## Benefits, By Who You Are

### For the Mechanic
- **Hands-free operation** — speak, don't type. Greasy fingers stay on wrenches.
- **Instant answers** — no flipping through manuals, no waiting for web pages, no greasy touchscreen.
- **Offline capable** — all knowledge is local. Works in shops with no internet.
- **Combustion-only focus** — every answer is ICE-relevant. No EV noise in the results.
- **Live microphone** — USB mic auto-calibrates to shop noise; silence detection stops recording when you stop speaking.
- **Barcode by voice** — scan a part box, hear "twelve on hand, bin A3-2" instantly.
- **Garage-tuned audio** — TTS voice is compressed and EQ'd to punch through air compressors and impact guns.

### For the Shop Owner
- **Reduce idle bay time** — parts pre-checked before job confirmation.
- **Cut rush-shipping costs** — predictive ordering with learned delivery times.
- **Capture missed revenue** — digital inspections increase the average ticket.
- **Improve cash flow** — SMS billing reminders reduce accounts-receivable days.
- **Know your numbers** — job profitability, technician efficiency, margin by engine family.
- **Protect from liability** — photo-documented pre-existing condition on every job.
- **Barcode-driven inventory** — scan parts in, scan parts out. No typing. No mistakes.

### For the Customer
- **Transparency** — they see photos of their worn brake pads. They understand why.
- **Convenience** — approve work via text message. No phone tag.
- **Trust** — predictive maintenance alerts prevent breakdowns before they happen.
- **Speed** — work starts when parts arrive, not when the customer calls back.

### For the Bottom Line
- **Zero subscription cost** — open source. Runs on a $55 Raspberry Pi.
- **Reduced part costs** — price tracking reveals fake sales and the real cheapest supplier.
- **Higher first-visit fix rate** — better diagnosis → fewer comebacks.
- **Shorter cycle time** — scheduled bays + parts on hand = cars out the door faster.

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
wrench obd --mock             # Simulated scan for testing
wrench obd --port /dev/ttyUSB0  # Real ELM327 adapter

# Look up parts
wrench parts thermostat --make Toyota --year 1996

# Search the knowledge base
wrench kb search "timing chain torque specs"

# Step-by-step repair workflow
wrench workflow list                                                # Show all available workflows
wrench workflow run -e toyota_5sfe -s water_pump_timing_belt --step 7
wrench workflow predict -e toyota_5sfe -s water_pump_timing_belt
wrench workflow markdown -e toyota_5sfe -s water_pump_timing_belt   # Export full procedure

# Voice-guided repair session (requires local Ollama)
wrench voice repair -e toyota_5sfe -s water_pump_timing_belt
# Then just speak: "next step", "what size is the tensioner bolt?", "go to step 5"

# Shop operations
wrench schedule board                              # Today's bay assignments
wrench schedule add --customer "Jane" --symptom "brakes" \
  --start "2025-08-01T08:00:00" --duration 180
wrench inventory add --sku "NGK-BKR7E" --part-name "Spark Plug" --qty 12 --price 6.50 --bin "A3-2"
wrench inventory low                               # Low-stock alerts
wrench price record THERMO-22RE RockAuto 12.99 --part-name "Thermostat"
wrench price history THERMO-22RE                   # 90-day trend
wrench vehicle register --vin 1HGCM... --customer "Jane" --year 2005 --make Honda --model Accord
wrench vehicle alerts --vin 1HGCM... --odometer 128000
wrench inspection create --vin 1HGCM... --customer "Jane"
wrench billing create --id INV-001 --customer "Jane" --phone "+15551234567" --amount 487.50
wrench billing aging                               # AR aging report

# Voice — preload the models into RAM
wrench voice warmup --stt faster-whisper --tts piper
```

### As a Hermes Agent Skill

```bash
# Load in any Hermes session
/skill wrench-voice

# Or preload on startup
hermes --skills wrench-voice
```

Auto-triggers on mechanic keywords. Provides voice-optimized responses:
- Short sentences (≤20 words) when `/voice` is on
- Numbers spoken aloud ("one-five millimeters" not "1.5mm")
- `[pause]` tokens for TTS pacing
- No markdown in spoken output

---

## Architecture

```
                    Voice Input (USB Mic)
                  faster-whisper (hot in RAM)
                              |
          +-------------------+-------------------+
          v                                       v
 +------------------+                  +------------------+
 |   Diagnostic     |                  |     OBD-II       |
 |     Engine       |                  |     Bridge      |
 | symptom->causes  |                  | DTC->causes     |
 | ->field tests    |                  | freeze frame    |
 | ->repair plan    |                  | live PIDs       |
 +--------+---------+                  +--------+---------+
          |                                       |
          v                                       |
   +--------------+   +--------------+    |  +--------------+
   | Parts Finder |   |  Inventory   |    |  | Parts Planner|
   | multi-source |   |   Manager    |    |  | BOM+timeline |
   | SQLite cache |   | bin tracking |    |  | cost estimate|
   +------+-------+   +------+-------+    |  +------+-------+
          |                  |            |         |
          +--------+---------+            |         |
                   v                      v         v
           +--------------+        +--------------+
           | Price Tracker|        | Delivery     |
           | 90d history  |        | Predictor    |
           | sale detect  |        | learned ETA  |
           +------+-------+        +------+-------+
                  |                       |
                  v                       v
           +--------------+        +--------------+
           |  Auto-Order  |        | Cost Analyzer|
           | PO + ship    |        | actual vs    |
           | consolidation|        | estimated    |
           +------+-------+        +------+-------+
                  |                       |
          +-------+-------+       +-------+-------+
          | Vehicle       |       | Warranty      |
          | History CRM   |       | Tracker       |
          | + alerts      |       | core returns  |
          +-------+-------+       +-------+-------+
                  |                       |
                  +-----------+-----------+
                              v
                  +--------------+
                  | Digital Insp.|
                  | photos + PDF |
                  +------+-------+
                         v
                  +--------------+
                  | Customer Not.|
                  | SMS billing  |
                  +------+-------+
                         v
                  +--------------+
                  | Voice Output |
                  |  piper-tts   |
                  | (kept hot)   |
                  +--------------+
```

---

## Modules — 30 Python Modules, 11,800 Lines, 118 Tests

| Module | What It Does |
|--------|-------------|
| `diagnostic_engine` | Symptom → ranked causes → field tests → repair procedures |
| `kb` | **54 engine families** — torque specs, fluid capacities, known issues |
| `vehicle_specs_db` | SQLite: **183 vehicles, 127 torque specs, 122 fluids, 115 issues, 298 aliases** |
| `repair_workflow` | Step-by-step procedures with tool matching + fastener tracking |
| `workflow_predictor` | Predict next tool, fastener, warning — before the mechanic asks |
| `ollama_bridge` | Local LLM for voice intent parsing + procedure Q&A |
| `photo_hint_manager` | Photos, diagrams, videos per step with bounding boxes |
| `parts_finder` | Multi-supplier lookup with SQLite cache |
| `parts_planner` | BOM expansion + timeline + cost estimate |
| `obd_bridge` | DTC reader, freeze frame, live data, readiness monitors |
| `job_scheduler` | Bay scheduling, tech assignment, parts-check |
| `inventory_manager` | Bin locations, min/max reorder, FIFO cost, barcode lookup |
| `price_tracker` | 90-day price history, trend detection, sale alerts |
| `delivery_predictor` | Learned ETA per supplier / region / season |
| `auto_order` | Automated POs, free-ship consolidation |
| `vehicle_history` | Per-VIN service records, predictive maintenance alerts |
| `digital_inspection` | Photo-based inspection, customer approval via SMS |
| `customer_notifier` | SMS status updates, approval requests, pickup reminders |
| `sms_billing` | Automated reminders, AR aging, payment tracking |
| `warranty_tracker` | Warranty dates, core return deadlines, claim tracking |
| `cost_analyzer` | Actual vs. estimated costs, margins by engine family |
| `part_scorer` | Brand reputation + return rate + warranty scoring |
| `voice_gateway` | faster-whisper STT + piper-tts, hot-resident in RAM |
| `microphone_input` | Live USB/ALSA mic capture with silence detection |
| `barcode_scanner` | USB HID + camera barcode for parts lookup |
| `audio_effects` | Normalization, EQ, compression, gate for noisy shops |
| `quickbooks_sync` | Invoice push to QuickBooks (stub — ready to wire) |
| `carfax_stub` | Vehicle history lookup (stub — ready to wire) |
| `calendar_stub` | Google/Outlook sync (stub — ready to wire) |
| `cli` | Click-based CLI — every feature reachable from the keyboard too |

**Every module supports `--mock` mode** — you can develop, demo, and test the entire system without any hardware, no OBD adapter, no microphone, no Ollama server.

---

## Knowledge Base — 54 Engine Families

The canonical engine data lives in `data/vehicle_specs.db` (SQLite). It spans Toyota, Honda, Subaru, Ford, Chevy, Jeep, Nissan, Mazda, Mitsubishi, BMW, Mercedes, VW/Audi, Cummins, and Power Stroke.

A few highlights:

| Engine | Era | Vehicles |
|--------|-----|----------|
| Toyota 22RE / 2JZ / 1MZ / 2GR / 5VZ / 2TR / 3S-GTE / 1UZ / 7M / 5S | 1983 → present | Pickup, 4Runner, Supra, Camry, Tacoma, Land Cruiser |
| Honda B / D / F / H / J / K / R Series | 1984 → present | Civic, Accord, Prelude, Odyssey, Pilot, TL, RSX |
| Subaru EJ18 → EJ25 → EJ20 → EZ36 → FA20 → FB25 → CB18 | 1980 → present | Loyale, Outback, WRX, STI, BRZ, Crosstrek |
| Ford Windsor / Cleveland / 300 I6 / Triton / EcoBoost / Power Stroke | 1958 → present | Mustang, F-150, Bronco, E-Series, Super Duty |
| Chevy Small Block V8 / Jeep 4.0 I6 / Cummins 5.9–6.7 | 1955 → present | Trucks, Camaro, Corvette, Wrangler, Ram |
| Nissan KA24 / SR20 / VQ35 · Mazda 13B / BP / MZR · Mitsubishi 4G63 | 1974–2011 | 240SX, RX-7, Miata, Eclipse, Evo, 350Z |
| BMW M54 / N54 / N55 · Mercedes M112 · VW EA888 | 1997 → present | E46, 335i, E320, GTI, A4 |

Each KB entry includes: overview, known weak points, torque-spec tables (ft-lb + Nm), fluid capacities, maintenance schedule, common procedures, special tools, and common mistakes — all queryable by engine code or alias.

---

## Available Repair Workflows

| Workflow | Engine | Steps | Skill Level | Time |
|----------|--------|-------|--------------|------|
| Water pump + timing belt | Toyota 5S-FE | 16 | Intermediate | 225 min |
| Valve cover gasket | Toyota 5S-FE | 7 | Beginner | 70 min |
| Spark plugs | Toyota 5S-FE | 5 | Beginner | 35 min |
| Head gasket | Subaru EJ25 SOHC | 5 | Advanced | 170 min |
| Timing belt | Subaru EJ25 SOHC | 5 | Intermediate | 95 min |
| Disc brake pads + rotors | Generic | 6 | Beginner | 75 min |
| Front wheel bearing | Generic | 5 | Intermediate | 75 min |

**Adding a workflow is a documented process** — see `references/` in the Hermes skill. Each `RepairStep` needs exact tools, `FastenerSpec`s (size, drive, torque, torque type, qty, location), safety warnings, and `produces` flags for prerequisite tracking.

---

## SMS Billing Workflow

```
Day 0:   Job complete → Invoice generated → SMS sent to customer
Day 7:   Gentle reminder: "Invoice due. Reply PAY or call shop."
Day 14:  Firm reminder: "Overdue. Please pay to keep account current."
Day 30:  Final notice: "Immediate attention required. Call shop."
Day 45:  Flagged for collection follow-up
```

Customer replies are parsed:
- **`YES` / `PAY`** → triggers a payment link (Stripe, or records intent)
- **`CALL`** → flagged for callback
- **`APPROVE`** → digital inspection work authorized

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| CLI | Click |
| Data | Pydantic v2 + SQLite |
| Web Scraping | httpx + BeautifulSoup4 |
| STT | faster-whisper (default), openai-whisper |
| TTS | piper-tts (default), coqui-tts, pyttsx3 |
| Local LLM | Ollama (qwen2.5-cpu, llama3.2, etc.) |
| Testing | pytest — 118 tests, zero external API calls |
| Package | setuptools (PEP 621) |
| Voice Latency | ~200ms STT, ~300ms TTS after warmup |

---

## Installation

### Standalone — Shop Computer or Raspberry Pi

```bash
# Basic install
pip install -e .

# With voice models (recommended for shop install)
pip install -e ".[voice]"   # faster-whisper, piper-tts

# With all extras
pip install -e ".[full]"
```

### As a Hermes Agent Skill

```bash
git clone https://github.com/drwjkirkpatrick-web/wrench-voice.git \
  ~/.hermes/skills/wrench-voice

# Activate in any session
/skill wrench-voice
```

---

## Tests

```bash
# All tests — zero external API calls required, zero shop data touched
pytest tests/ -v

# Specific modules
pytest tests/test_diagnostic_engine.py -v
pytest tests/test_obd_bridge.py -v
pytest tests/test_shop_modules.py -v
pytest tests/test_repair_workflow.py -v
```

All 118 tests run in mock mode or with temp databases. No shop data is ever touched. No network is required.

---

## Hardware Recommendations — Total Shop Setup ~$135–$240

| Component | Recommendation | Cost |
|-----------|----------------|------|
| Shop computer | Raspberry Pi 4 (4GB) | $55 |
| Microphone | USB Blue Snowball or similar | $50 |
| Speakers | Cheap USB speaker | $15 |
| OBD-II adapter | USB ELM327 or Bluetooth OBDLink MX+ | $15–$120 |
| Display (optional) | 7" touch LCD for bay tablets | $60 |
| **Total shop setup** | | **~$135–$240** |

**One-time cost. No monthly subscription. No per-bay licensing. No cloud bill.**

---

## Configuration

```bash
# Environment variables (add to ~/.bashrc or a systemd unit)
export WRENCH_CACHE_DIR="$HOME/.cache/wrench-voice"
export WRENCH_STT_BACKEND="faster-whisper"   # or "mock"
export WRENCH_TTS_BACKEND="piper"             # or "mock"
export WRENCH_OLLAMA_MODEL="qwen2.5-cpu:latest" # local LLM (optional)
export OLLAMA_HOST="http://localhost:11434"      # Ollama server (optional)

# SMS (optional — mock-mode works without these)
export TWILIO_SID="your_sid"
export TWILIO_TOKEN="your_token"
export TWILIO_FROM="+15555550100"
export SHOP_PHONE="503-555-0100"
export SHOP_NAME="Wrench Auto"

# OBD adapter
export WRENCH_OBD_PORT="/dev/ttyUSB0"
```

---

## Roadmap

### ✅ Complete — v0.3.0
- [x] Core diagnostic engine (10 symptoms, 45+ ranked causes)
- [x] Knowledge base — **54 engine families** across 14 manufacturers
- [x] Vehicle specs database (183 vehicles, 127 torque specs, 122 fluids, 97 maintenance intervals, 115 issues, 298 aliases)
- [x] Parts finder with SQLite caching + parts planner with BOM expansion
- [x] OBD-II bridge (DTCs, freeze frame, live data, readiness, mock mode)
- [x] Full shop suite — scheduling, inventory, pricing, delivery, auto-order, cost analysis, warranties
- [x] Vehicle history CRM with predictive maintenance alerts
- [x] Digital inspection + customer notifications + SMS billing + AR aging
- [x] Voice gateway — faster-whisper + piper-tts, hot-resident
- [x] Live microphone (ALSA/PyAudio/WAV) + barcode scanner (USB HID + camera)
- [x] Garage-tuned audio effects (EQ, compression, gate per room profile)
- [x] **Step-by-step repair workflows** with exact tool + fastener matching
- [x] **Workflow predictor** — next tool, fastener, warning prediction
- [x] **Ollama bridge** — local LLM for voice intent parsing + procedure Q&A
- [x] **Photo hint manager** — photos, diagrams, videos per step with bounding boxes
- [x] Hermes Agent skill integration

### 🚧 In Progress
- [ ] Bluetooth OBD adapter support
- [ ] QuickBooks Online OAuth2 connection
- [ ] Google Calendar API sync
- [ ] Twilio webhook handler for inbound SMS
- [ ] Web dashboard (Flask/FastAPI for shop tablets)

### 🗺️ Planned
- [ ] More engine families — Chevy LS, Porsche flat-6, diesel common-rail
- [ ] ASE-style labor-time integration
- [ ] Mobile app companion (React Native or PWA)
- [ ] Fleet management module (multi-vehicle corporate accounts)

---

## Community & Contributing

Issues, PRs, and engine-family contributions are all welcome.

**Engine-family contributions are especially valued.** Each `.md` file in `kb/` follows the template in the Hermes skill's `templates/engine-kb-article.md`:
- H1: Engine family name
- H2: Overview, Known Issues, Torque Specs, Fluid Capacities, Maintenance Schedule, Common Procedures
- Tables for torque specs and fluid capacities
- Metric + imperial where relevant

See the **wrench-voice** Hermes skill (`~/.hermes/skills/wrench-voice/`) for the full contributor guide — engine family matrix, SQLite migration patterns, OBD setup, diagnostic decision tree, and the canonical voice prompt template.

---

## License

MIT © 2026 Walker Kirkpatrick

> *Built by a mechanic, for mechanics. Hands stay free. Eyes stay on the engine.*
