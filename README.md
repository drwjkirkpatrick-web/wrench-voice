# 🔧 Wrench Voice

> Hands-free voice assistant for combustion engine repair.
> Diagnose symptoms. Look up parts. Plan the job. All while your hands are on the wrench.

**Repository:** [github.com/drwjkirkpatrick-web/wrench-voice](https://github.com/drwjkirkpatrick-web/wrench-voice)

---

## What It Does

A mechanic speaks to Wrench Voice (via Hermes Agent with STT/TTS) and gets:

1. **Diagnosis** — Symptom → ranked causes → field tests → repair procedure
2. **Parts lookup** — Prices from multiple suppliers, cached locally
3. **Job planning** — Full bill of materials + timeline + cost estimate
4. **Knowledge base** — Torque specs, fluid capacities, known issues for 8 common engine families

**Hard rule: Combustion engines only.** No EVs, no hybrids, no battery packs.

---

## Quick Start

```bash
# Clone
git clone https://github.com/drwjkirkpatrick-web/wrench-voice.git
cd wrench-voice

# Install (editable, for development)
pip install -e .

# Diagnose a symptom
wrench diagnose overheating --make Toyota --year 1996

# Look up a part
wrench parts thermostat --make Toyota --year 1996

# Search knowledge base
wrench kb "timing chain torque"

# Plan a job from a saved diagnosis
wrench plan ~/jobs/diagnosis-overheating.json
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Voice Input (STT)                         │
│        "Overheating at idle, '96 Camry 2.2L"                │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    ┌──────────────────┐      ┌──────────────────┐
    │  DiagnosticEngine │      │   KnowledgeBase   │
    │   symptom → causes│      │  .md file search │
    │   → tests → fix   │      │  torque/specs     │
    └────────┬──────────┘      └──────────────────┘
             │
             ▼
    ┌──────────────────┐
    │   PartsFinder    │
    │  RockAuto scrape │
    │  Local inventory │
    │  Mock fallback   │
    └────────┬──────────┘
             │
             ▼
    ┌──────────────────┐
    │  PartsPlanner    │
    │  BOM + timeline  │
    │  Cost estimate   │
    └──────────────────┘
             │
             ▼
    ┌──────────────────┐
    │   Voice Output   │
    │  (TTS, speakable) │
    └──────────────────┘
```

---

## Modules

| Module | File | What it does |
|--------|------|-------------|
| `diagnostic_engine` | `src/wrench_voice/diagnostic_engine.py` | Symptom → ranked causes → field tests → repair. Pure local knowledge graph. No API calls. |
| `kb` | `src/wrench_voice/kb.py` | Markdown knowledge base reader + keyword search. Loads lazily. |
| `parts_finder` | `src/wrench_voice/parts_finder.py` | Multi-supplier part lookup with SQLite cache. Mock mode for offline demos. |
| `parts_planner` | `src/wrench_voice/parts_planner.py` | Convert diagnosis into full job plan with BOM, timeline, cost. |
| `cli` | `src/wrench_voice/cli.py` | Click-based command line interface. |

---

## Knowledge Base Engines

Eight combustion engine families with torque tables, fluid capacities, known issues, and common procedures:

| Engine | Era | Vehicles |
|--------|-----|----------|
| Toyota 22RE | 1983–2004 | Pickup, 4Runner |
| Ford 300 I6 | 1965–1996 | F-150, E-150 |
| Honda B-Series | 1988–2001 | Civic, Integra, CR-V |
| Chevy Small Block V8 | 1955–2003 | Trucks, Camaro, Corvette |
| Jeep 4.0 I6 | 1987–2006 | Wrangler, Cherokee |
| Nissan KA24DE | 1997–2004 | Frontier, Xterra |
| Mazda Rotary 13B | 1974–2012 | RX-7, RX-8 |
| BMW M54 | 2000–2006 | E46, E39, X3, Z4 |

---

## Hermes Skill Integration

A companion Hermes skill lives at `~/.hermes/skills/wrench-voice/`:

```bash
# Load in any Hermes session
/skill wrench-voice

# Or preload on startup
hermes --skills wrench-voice
```

The skill auto-triggers on mechanic-related keywords and provides a voice-optimized system prompt.

---

## Tests

```bash
# All tests
pytest tests/ -v

# Just diagnostics
pytest tests/test_diagnostic_engine.py -v
```

13 tests, all passing, zero external dependencies required.

---

## Roadmap

- [x] Core diagnostic engine
- [x] Knowledge base (8 engines)
- [x] Parts finder with caching
- [x] Parts planner with BOM expansion
- [x] CLI
- [x] Hermes skill + references
- [ ] OBD-II bridge (python-obd integration)
- [ ] Voice gateway (local STT/TTS server on shop Pi)
- [ ] Local inventory CSV editor
- [ ] More engine families (LS, 2JZ, M50, etc.)

---

## License

MIT © Walker Kirkpatrick
