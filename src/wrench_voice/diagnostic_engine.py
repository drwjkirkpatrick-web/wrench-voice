"""
diagnostic_engine.py
====================
Symptom → ranked causes → tests → repair procedure.

WHY this module exists:
Mechanics need fast, offline diagnostic help while their hands are dirty.
No internet, no subscription, no API key — just a local knowledge graph
that knows how combustion engines break.

HOW it works:
1. Take a symptom slug (e.g. "overheating_at_idle")
2. Look up the symptom in SYMPTOM_CAUSES — a hard-coded graph of
   symptom → list of (Cause, prevalence_score)
3. If make/model/year/engine are given, filter causes by engine-family
   knowledge (e.g. Toyota 22RE is prone to cracked exhaust manifolds)
4. Sort by score descending, build a DiagnosisResult with field tests
5. Confidence rises with specificity — more params = narrower causes

WHAT is a "field test":
A quick check the mechanic can do with basic tools (ratchet, multimeter,
coolant tester). Ordered by speed — fastest checks first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class Cause:
    """One possible root cause for a symptom."""
    name: str                # e.g. "Stuck closed thermostat"
    prevalence: float        # 0.0–1.0  how common this cause is
    engine_families: list[str]  # Which engines are prone to this (empty = all)
    field_tests: list[str]   # Ordered checks from fastest to slowest
    repair_procedure: list[str]  # Step-by-step fix
    parts_needed: list[str]    # Rough parts list for the planner
    severity: str = "normal"     # normal | urgent | critical


@dataclass
class DiagnosisResult:
    """What the mechanic hears / reads back."""
    symptom: str
    ranked_causes: list[dict[str, Any]]
    tests: list[str]
    repair_procedure: str
    confidence: float
    estimated_time: str
    warnings: list[str] = field(default_factory=list)
    vehicle_info: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Readable format for CLI or logged output."""
        lines = [
            f"# Diagnosis: {self.symptom.replace('_', ' ').title()}",
            f"",
            f"Confidence: {self.confidence:.0%}",
            f"Estimated time: {self.estimated_time}",
            f"",
        ]
        if self.warnings:
            lines.append("⚠️ Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
            lines.append("")
        lines.append("## Ranked Causes")
        for i, c in enumerate(self.ranked_causes, 1):
            lines.append(f"{i}. {c['name']} ({c['severity']}, score {c['score']:.2f})")
        lines.append("")
        lines.append("## Field Tests (fastest first)")
        for t in self.tests:
            lines.append(f"- {t}")
        lines.append("")
        lines.append("## Repair Procedure")
        lines.append(self.repair_procedure)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """For JSON export / web API."""
        return {
            "symptom": self.symptom,
            "confidence": self.confidence,
            "estimated_time": self.estimated_time,
            "warnings": self.warnings,
            "vehicle_info": self.vehicle_info,
            "ranked_causes": self.ranked_causes,
            "tests": self.tests,
            "repair_procedure": self.repair_procedure,
        }


# ─── Knowledge Graph ───────────────────────────────────────────────────────────

SYMPTOM_CAUSES: dict[str, list[Cause]] = {
    # ── Overheating ────────────────────────────────────────────────────────────
    "overheating": [
        Cause(
            name="Low coolant level",
            prevalence=0.35,
            engine_families=[],
            field_tests=[
                "Check radiator overflow tank level (cold engine)",
                "Inspect for wet spots / dried coolant trails under vehicle",
                "Pressure-test cooling system with pump (15 psi, 10 min)",
            ],
            repair_procedure=(
                "1. Locate leak source with UV dye + blacklight\n"
                "2. Replace leaking hose / clamp / water pump seal\n"
                "3. Refill with manufacturer-spec coolant (50/50)\n"
                "4. Bleed air pockets: run engine with cap off, heater on full\n"
                "5. Verify fans cycle on/off and temp gauge stabilizes"
            ),
            parts_needed=["coolant", "hose", "clamp", "water pump gasket"],
            severity="normal",
        ),
        Cause(
            name="Stuck closed thermostat",
            prevalence=0.25,
            engine_families=[],
            field_tests=[
                "Feel upper radiator hose — cold hose at operating temp = stuck closed",
                "IR thermometer: therm housing vs radiator inlet (big delta = closed)",
                "Remove thermostat, boil water test (should open at stamped temp)",
            ],
            repair_procedure=(
                "1. Drain coolant below thermostat level\n"
                "2. Remove thermostat housing (note bolt length variations)\n"
                "3. Clean mating surfaces, install new gasket + thermostat (orientation matters)\n"
                "4. Torque housing bolts to spec (usually 8–12 ft-lbs)\n"
                "5. Refill, bleed, test drive, recheck"
            ),
            parts_needed=["thermostat", "thermostat gasket", "coolant"],
            severity="urgent",
        ),
        Cause(
            name="Failed water pump",
            prevalence=0.15,
            engine_families=[],
            field_tests=[
                "Grab pump pulley — any wobble or bearing noise?",
                "Peek at weep hole — coolant stain or drip?",
                "Remove belt, spin impeller by hand — gritty or loose?",
            ],
            repair_procedure=(
                "1. Remove accessory belts / serpentine\n"
                "2. Drain coolant\n"
                "3. Remove pump (timing cover interference varies by engine)\n"
                "4. Scrape old gasket, apply RTV if surface is pitted\n"
                "5. Install new pump, torque to spec\n"
                "6. Refill, start, verify no drip at weep hole"
            ),
            parts_needed=["water pump", "water pump gasket", "coolant", "belts"],
            severity="urgent",
        ),
        Cause(
            name="Radiator fan not spinning",
            prevalence=0.10,
            engine_families=[],
            field_tests=[
                "Turn AC on max — fan should engage immediately",
                "Jump 12V directly to fan motor — if it spins, relay/controller fault",
                "Check fuse and relay with test light or multimeter",
            ],
            repair_procedure=(
                "1. Verify fuse continuity\n"
                "2. Swap relay with known-good identical relay\n"
                "3. If motor still dead: remove shroud, replace fan assembly\n"
                "4. If motor runs on 12V jump: replace temp sender / controller"
            ),
            parts_needed=["radiator fan", "relay", "fuse", "temp sender"],
            severity="normal",
        ),
        Cause(
            name="Cracked head or blown head gasket",
            prevalence=0.08,
            engine_families=["toyota_22re", "honda_b_series", "jeep_4_0", "bmw_m54"],
            field_tests=[
                "Coolant in oil (milky dipstick, brown froth under cap)",
                "Exhaust bubbles in radiator (combustion gas test)",
                "Coolant smell from tailpipe / white smoke",
                "Cylinder leak-down test — adjacent cylinders bleed into each other",
            ],
            repair_procedure=(
                "WARNING: This is a major repair.\n"
                "1. Verify with combustion gas tester (blue fluid turns yellow = positive)\n"
                "2. Pull spark plugs — cleanest plug = leaking cylinder\n"
                "3. Remove cylinder head, send to machine shop for flatness check\n"
                "4. Measure block deck for warp\n"
                "5. Install new head gasket with proper torque sequence\n"
                "6. Reassemble timing components, refill all fluids, rebreak in for 500 miles"
            ),
            parts_needed=["head gasket set", "head bolts", "coolant", "oil", "filter", "RTV"],
            severity="critical",
        ),
    ],

    # ── No Start ───────────────────────────────────────────────────────────────
    "no_start": [
        Cause(
            name="Dead battery or corroded terminals",
            prevalence=0.30,
            engine_families=[],
            field_tests=[
                "Turn key — dashboard dim or clicks?",
                "Battery voltage: 12.6V good, below 12.0V weak, below 10.0V dead",
                "Load test: headlamps on, crank — if lights go out = bad battery or terminal",
            ],
            repair_procedure=(
                "1. Clean terminals with baking soda + wire brush\n"
                "2. Check tightness — should not rotate by hand\n"
                "3. Load-test battery at auto parts store (free)\n"
                "4. If fails: replace battery, register on BMW/VW/MB if applicable"
            ),
            parts_needed=["battery", "terminal cleaner", "dielectric grease"],
            severity="normal",
        ),
        Cause(
            name="Bad fuel pump or clogged filter",
            prevalence=0.20,
            engine_families=[],
            field_tests=[
                "Listen for pump prime at key-on (2–3 second hum from rear)",
                "Fuel rail pressure gauge — should hold spec for 5 min after shutoff",
                "Spray starter fluid into intake — if it fires, fuel delivery issue",
            ],
            repair_procedure=(
                "1. Replace fuel filter first (cheap, easy elimination)\n"
                "2. If still no prime: check fuel pump fuse + relay\n"
                "3. Access pump via trunk floor panel or drop tank\n"
                "4. Replace pump + strainer + locking ring\n"
                "5. Prime system: key-on/off 3x before cranking"
            ),
            parts_needed=["fuel pump", "fuel filter", "strainer", "locking ring"],
            severity="urgent",
        ),
        Cause(
            name="No spark — bad coil / distributor / crank sensor",
            prevalence=0.20,
            engine_families=[],
            field_tests=[
                "Pull a spark plug, ground to block, crank — blue spark = ignition OK",
                "Check coil primary resistance (0.5–2.0 Ω typical)",
                "Check distributor cap for carbon tracks or moisture",
                "Oscilloscope or scan tool: crank sensor signal present while cranking?",
            ],
            repair_procedure=(
                "1. Replace spark plugs first (elimination)\n"
                "2. Test coil — if coil-on-plug, swap with adjacent cylinder\n"
                "3. If misfire moves with coil: replace coil\n"
                "4. Distributor engines: replace cap + rotor, check shaft play\n"
                "5. Still no spark: scope crank sensor, replace if no signal"
            ),
            parts_needed=["spark plugs", "ignition coil", "cap", "rotor", "crank sensor"],
            severity="urgent",
        ),
        Cause(
            name="Timing belt / chain jumped or broken",
            prevalence=0.15,
            engine_families=["honda_b_series", "mazda_13b", "ford_300"],
            field_tests=[
                "Crank engine — does it spin unusually fast (no compression)?",
                "Remove cam-cover sight hole or valve cover — cam stationary while cranking?",
                "Compression test: near-zero on all cylinders = timing failure",
            ],
            repair_procedure=(
                "WARNING: Interference engine? Valves may be bent.\n"
                "1. Do NOT crank further\n"
                "2. Inspect belt/chain tensioner and guides\n"
                "3. Align timing marks per factory procedure (cams + crank)\n"
                "4. Turn crank by hand (socket + breaker bar) — any valve contact click?\n"
                "5. If interference engine and jumped: likely needs cylinder head rebuild"
            ),
            parts_needed=["timing belt kit", "tensioner", "idler", "water pump", "valve job maybe"],
            severity="critical",
        ),
        Cause(
            name="Immobilizer / security lockout",
            prevalence=0.08,
            engine_families=["bmw_m54", "vw_ea888"],
            field_tests=[
                "Security light flashing while cranking?",
                "Try spare key — transponder chip may be damaged",
                "Scan for immobilizer codes (Bxxxx series)",
            ],
            repair_procedure=(
                "1. Try spare key\n"
                "2. Disconnect battery 30 min (soft reset)\n"
                "3. Dealer or locksmith: re-program keys or replace EWS/immobilizer module"
            ),
            parts_needed=["transponder key", "immobilizer module maybe"],
            severity="normal",
        ),
    ],

    # ── Rough Idle ──────────────────────────────────────────────────────────────
    "rough_idle": [
        Cause(
            name="Vacuum leak",
            prevalence=0.30,
            engine_families=[],
            field_tests=[
                "Spray carb cleaner around intake manifold seams — RPM surge = leak",
                "Smoke machine test (if available)",
                "Listen for hissing near PCV, brake booster, EGR lines",
            ],
            repair_procedure=(
                "1. Trace leak to source with propane enrichment or smoke\n"
                "2. Replace hose / fitting / gasket\n"
                "3. Clear adaptive fuel trim, run for 2 drive cycles"
            ),
            parts_needed=["vacuum hose", "intake gasket", "PCV valve"],
            severity="normal",
        ),
        Cause(
            name="Dirty throttle body / IAC valve",
            prevalence=0.20,
            engine_families=[],
            field_tests=[
                "Open throttle plate — carbon buildup visible?",
                "Tap IAC valve lightly — idle changes?",
            ],
            repair_procedure=(
                "1. Remove air intake hose\n"
                "2. Spray throttle cleaner on cloth, wipe bore and plate\n"
                "3. Remove IAC, clean pintle and seat\n"
                "4. Reset idle relearn (varies by make: unplug battery or scan tool)",
            ),
            parts_needed=["throttle cleaner", "IAC gasket"],
            severity="normal",
        ),
        Cause(
            name="Bad motor mount transmitting vibration",
            prevalence=0.10,
            engine_families=[],
            field_tests=[
                "Torque brake in Drive / Reverse — does engine rock excessively?",
                "Visual inspect mount rubber for cracks or fluid leaks",
            ],
            repair_procedure=(
                "1. Support engine with jack + wood block under pan\n"
                "2. Remove failed mount bolts\n"
                "3. Install new mount, torque in stages, lower engine gently"
            ),
            parts_needed=["motor mount", "torque wrench"],
            severity="normal",
        ),
        Cause(
            name="Fouled spark plugs",
            prevalence=0.20,
            engine_families=[],
            field_tests=[
                "Pull plugs — black and sooty = rich, white and blistered = lean/heat",
                "Gap check: should match spec (usually 0.035–0.045 in)",
            ],
            repair_procedure=(
                "1. Replace all plugs with OEM-spec\n"
                "2. If repeatedly fouling: fix underlying rich condition first"
            ),
            parts_needed=["spark plugs"],
            severity="normal",
        ),
        Cause(
            name="Low compression on one cylinder",
            prevalence=0.08,
            engine_families=["jeep_4_0", "chevy_350", "toyota_22re"],
            field_tests=[
                "Compression test: one cylinder notably lower",
                "Leak-down test: listen at throttle (intake valve), dipstick (rings), radiator (head gasket)",
            ],
            repair_procedure=(
                "1. Determine source from leak-down location\n"
                "2. Intake valve: replace valve + seat\n"
                "3. Rings: hone + oversize pistons\n"
                "4. Head gasket: see overheating > blown head gasket"
            ),
            parts_needed=["valve", "piston rings", "head gasket"],
            severity="critical",
        ),
    ],

    # ── Misfire ────────────────────────────────────────────────────────────────
    "misfire": [
        Cause(
            name="Ignition coil failure (coil-on-plug)",
            prevalence=0.30,
            engine_families=["bmw_m54", "toyota_2gr", "vw_ea888"],
            field_tests=[
                "Swap coil to adjacent cylinder — if misfire moves, coil is bad",
                "Oscilloscope: spark line duration shortened = weak coil",
            ],
            repair_procedure="Replace failed coil. If one is dead at 80k+, replace all for reliability.",
            parts_needed=["ignition coil"],
            severity="normal",
        ),
        Cause(
            name="Injector clog or electrical fault",
            prevalence=0.20,
            engine_families=[],
            field_tests=[
                "Ohm injector — should be 12–16 Ω (high impedance) or 2–5 Ω (low)",
                "Noid light on connector — pulse present?",
                "Swap injector to adjacent cyl — if misfire moves, injector fault",
            ],
            repair_procedure=(
                "1. Try fuel-system cleaner in tank first (cheap shot)\n"
                "2. Ultrasonic clean injectors if accessible\n"
                "3. Replace injector if electrical fault confirmed"
            ),
            parts_needed=["fuel injector", "O-rings", "fuel cleaner"],
            severity="normal",
        ),
        Cause(
            name="Lean condition from vacuum leak or MAF fault",
            prevalence=0.20,
            engine_families=[],
            field_tests=[
                "Long-term fuel trim &gt; +15% = lean",
                "Clean MAF with CRC spray, retest",
                "Smoke test intake tract",
            ],
            repair_procedure=(
                "1. Clean or replace MAF\n"
                "2. Seal vacuum leaks\n"
                "3. Retest trims — should return to +/- 5%"
            ),
            parts_needed=["MAF sensor", "vacuum hose"],
            severity="normal",
        ),
        Cause(
            name="Valve lash out of spec (solid lifter engines)",
            prevalence=0.15,
            engine_families=["honda_b_series", "toyota_22re", "ford_300"],
            field_tests=[
                "Feeler gauge on cold engine: intake and exhaust clearance",
                "Audible ticking that disappears as engine warms = too loose",
            ],
            repair_procedure=(
                "1. Cold engine, cylinder at TDC compression\n"
                "2. Measure lash with feeler gauge\n"
                "3. Adjust shim or screw to spec\n"
                "4. Re-torque cam cap / rocker arm bolts"
            ),
            parts_needed=["shims", "valve cover gasket"],
            severity="normal",
        ),
    ],

    # ── Knocking / Ticking ─────────────────────────────────────────────────────
    "knocking": [
        Cause(
            name="Rod knock — spun bearing",
            prevalence=0.25,
            engine_families=[],
            field_tests=[
                "Knock increases with RPM and load",
                "Knock present even when warm (doesn't go away like piston slap)",
                "Oil pressure low at hot idle",
            ],
            repair_procedure=(
                "WARNING: Catastrophic failure imminent. Do not drive.\n"
                "1. Confirm with stethoscope — loudest at oil pan/block seam\n"
                "2. Drop pan, inspect bearings with plastigage\n"
                "3. Usually requires engine rebuild or replacement"
            ),
            parts_needed=["rod bearings", "main bearings", "pistons maybe", "engine rebuild kit"],
            severity="critical",
        ),
        Cause(
            name="Piston slap (cold only, OK when warm)",
            prevalence=0.15,
            engine_families=["chevy_350", "ford_300"],
            field_tests=[
                "Knock disappears after 5–10 min warm-up",
                "Louder at cold start, gone at operating temp",
            ],
            repair_procedure=(
                "Often cosmetic on high-mileage engines. If acceptable:\n"
                "1. Use thicker oil (10W-40) if climate allows\n"
                "2. Monitor oil consumption\n"
                "3. Full repair = piston + bore overhaul"
            ),
            parts_needed=["pistons", "rings", "hone job"],
            severity="normal",
        ),
        Cause(
            name="Lifter tick — collapsed hydraulic lifter",
            prevalence=0.25,
            engine_families=["chevy_350", "ford_triton"],
            field_tests=[
                "Tick at one valve cover, rhythmic with RPM",
                "Seafoam or Marvel Mystery Oil in crankcase — tick quiets temporarily?",
            ],
            repair_procedure=(
                "1. Change oil + filter with high-detergent oil\n"
                "2. Add lifter additive (last resort before mechanical fix)\n"
                "3. If persistent: replace lifters, inspect cam lobe wear"
            ),
            parts_needed=["hydraulic lifters", "camshaft maybe", "oil", "filter"],
            severity="normal",
        ),
        Cause(
            name="Exhaust leak tick (manifold crack / gasket)",
            prevalence=0.20,
            engine_families=["toyota_22re", "jeep_4_0", "ford_300"],
            field_tests=[
                "Tick audible near manifold, pitch changes with exhaust flow",
                "Soapy water spray while idling — bubbles at crack",
                "IR thermometer: hot spot at crack location",
            ],
            repair_procedure=(
                "1. Inspect manifold for hairline cracks\n"
                "2. If cracked: replace manifold + gasket + studs\n"
                "3. If gasket only: scrape surfaces, install new gasket"
            ),
            parts_needed=["exhaust manifold", "manifold gasket", "studs", "nuts"],
            severity="normal",
        ),
    ],

    # ── Smoke (Color) ──────────────────────────────────────────────────────────
    "white_smoke": [
        Cause(
            name="Coolant burning in combustion chamber (head gasket / cracked head)",
            prevalence=0.60,
            engine_families=[],
            field_tests=[
                "Sweet coolant smell from exhaust",
                "Combustion gas tester on radiator (positive)",
                "Oil looks milky or frothy",
            ],
            repair_procedure=(
                "See overheating > blown head gasket procedure.\n"
                "DO NOT continue driving — coolant in oil destroys bearings."
            ),
            parts_needed=["head gasket set", "head bolts", "coolant", "oil", "filter"],
            severity="critical",
        ),
        Cause(
            name="Cold condensation (harmless, 30 sec after start)",
            prevalence=0.30,
            engine_families=[],
            field_tests=["Does it disappear within 30–60 seconds? Then condensation."],
            repair_procedure="No repair needed. Normal in cold weather.",
            parts_needed=[],
            severity="normal",
        ),
    ],
    "blue_smoke": [
        Cause(
            name="Burning oil — worn rings or valve seals",
            prevalence=0.50,
            engine_families=[],
            field_tests=[
                "Compression test — low on multiple cylinders = rings",
                "Leak-down at TDC intake stroke — hiss at dipstick = rings, at throttle = valve seals",
                "Wet vs dry compression (add teaspoon oil to cyl, retest — big jump = rings)",
            ],
            repair_procedure=(
                "1. If valve seals only: replace with compressor hose + rope trick (head stays on)\n"
                "2. If rings: hone + oversize pistons or full rebuild\n"
                "3. Temporary fix: thicker oil, additives (band-aid)"
            ),
            parts_needed=["valve seals", "piston rings", "honing tool"],
            severity="normal",
        ),
        Cause(
            name="Turbocharger seal leak",
            prevalence=0.30,
            engine_families=["vw_ea888", "bmw_n54"],
            field_tests=[
                "Oil in intercooler or charge pipes",
                "Shaft play in turbo (grab turbine, check radial movement)",
            ],
            repair_procedure=(
                "1. Remove turbo, inspect shaft bearings\n"
                "2. Rebuild kit or reman turbo\n"
                "3. Replace oil feed line (clogged = starvation = seal failure)"
            ),
            parts_needed=["turbo rebuild kit", "oil feed line", "gaskets"],
            severity="normal",
        ),
    ],
    "black_smoke": [
        Cause(
            name="Rich fuel mixture",
            prevalence=0.50,
            engine_families=[],
            field_tests=[
                "Short-term fuel trim &lt; -10% = rich",
                "Black, sooty spark plugs",
                "MAF reading higher than expected at idle",
            ],
            repair_procedure=(
                "1. Clean or replace MAF\n"
                "2. Check coolant temp sensor — cold reading when hot = extra fuel\n"
                "3. Inspect O2 sensor — stuck high voltage = rich signal\n"
                "4. Check fuel pressure regulator — leaking diaphragm dumps fuel into intake"
            ),
            parts_needed=["MAF", "coolant temp sensor", "O2 sensor", "fuel pressure regulator"],
            severity="normal",
        ),
        Cause(
            name="Clogged air filter",
            prevalence=0.30,
            engine_families=[],
            field_tests=["Hold filter up to sun — can you see light?"],
            repair_procedure="Replace air filter. Check intake snorkel for rodent nests.",
            parts_needed=["air filter"],
            severity="normal",
        ),
    ],

    # ── Poor Fuel Economy ──────────────────────────────────────────────────────
    "poor_mileage": [
        Cause(
            name="O2 sensor degraded (slow response)",
            prevalence=0.25,
            engine_families=[],
            field_tests=[
                "Scan tool live data: O2 voltage oscillates slowly (&gt; 1 sec per cycle)",
                "Compare short-term vs long-term trims — wide spread = sensor lying",
            ],
            repair_procedure="Replace upstream O2 sensor (before catalytic converter). Downstream monitors cat health.",
            parts_needed=["upstream O2 sensor"],
            severity="normal",
        ),
        Cause(
            name="Dragging brake caliper",
            prevalence=0.15,
            engine_families=[],
            field_tests=[
                "Wheel hot after 10 min drive?",
                "Jack up, spin wheel — should rotate 2+ revolutions freely",
                "Caliper slide pins seized?",
            ],
            repair_procedure=(
                "1. Grease or replace slide pins\n"
                "2. If piston seized: rebuild or replace caliper\n"
                "3. Bed pads after repair"
            ),
            parts_needed=["brake pads", "slide pins", "caliper rebuild kit"],
            severity="normal",
        ),
        Cause(
            name="Tires underinflated or misaligned",
            prevalence=0.20,
            engine_families=[],
            field_tests=[
                "Tire pressure all 4 corners",
                "Tread wear pattern — feathered edges = alignment",
            ],
            repair_procedure="Inflate to door sticker spec. Align if wear is uneven.",
            parts_needed=["tire pressure", "alignment"],
            severity="normal",
        ),
    ],

    # ── Subaru-Specific ──────────────────────────────────────────────────────────
    # These are folded into the main symptoms above via engine_family filtering,
    # but we also keep standalone symptom slugs for direct Subaru queries.
    "subaru_head_gasket": [
        Cause(
            name="External head gasket leak (Subaru EJ25 SOHC)",
            prevalence=0.85,
            engine_families=["subaru_ej25_sohc", "subaru_ej25_dohc", "subaru_ej20"],
            field_tests=[
                "Look for coolant weep at head-to-block seam on cylinder 2 or 4 bank",
                "UV dye in coolant — blacklight inspection of block valley",
                "Combustion gas tester — may be negative (external leak, not into combustion)",
                "Pressure-test cooling system: pressure drops without visible external leak = head gasket",
            ],
            repair_procedure=[
                "WARNING: MLS (Multi-Layer Steel) gasket required. Do NOT use composite.",
                "1. Remove intake manifold, exhaust manifolds, timing belt, camshafts",
                "2. Remove cylinder heads. Inspect block deck and head for flatness (< 0.002\" warp)",
                "3. Machine shop: resurface if needed. Do NOT remove more than 0.004\"",
                "4. Clean block threads — chase with tap. Subaru threads are fine and strip easily.",
                "5. Install new MLS head gaskets (marked UP). Use Subaru OEM or Six-Star.",
                "6. Torque in stages per factory sequence. Phase 1 (1998–1999): 10mm bolts. Phase 2+: 11mm + 14mm.",
                "7. Reassemble timing belt with new tensioner and water pump.",
                "8. Refill with Subaru blue coolant. Burp thoroughly — heater on max, front end raised.",
            ],
            parts_needed=["MLS head gasket set", "head bolts", "timing belt kit", "water pump", "Subaru coolant"],
            severity="urgent",
        ),
    ],
    "subaru_timing_belt": [
        Cause(
            name="Timing belt failure (all EJ engines)",
            prevalence=0.70,
            engine_families=["subaru_ej18", "subaru_ej22", "subaru_ej25_sohc", "subaru_ej25_dohc", "subaru_ej20", "subaru_ea82"],
            field_tests=[
                "Remove timing cover — inspect belt for cracks, glazing, missing teeth",
                "Check tensioner plunger extension — should be within spec marks",
                "Crank engine by hand — any valve contact feel?",
            ],
            repair_procedure=[
                "WARNING: ALL Subaru EJ engines are INTERFERENCE. Belt failure = bent valves.",
                "1. Replace belt, tensioner, idler pulleys, and water pump as a kit.",
                "2. Align crank mark to timing cover arrow.",
                "3. Align cam sprocket dots to notches on backing plate.",
                "4. Ensure belt is tight on non-tensioned side before releasing tensioner.",
                "5. Rotate engine by hand two full revolutions. Recheck alignment.",
                "6. If belt broke while running: leak-down test all cylinders before reassembly.",
            ],
            parts_needed=["timing belt kit", "tensioner", "idler", "water pump", "seals"],
            severity="critical",
        ),
    ],
    "subaru_knock": [
        Cause(
            name="Rod knock from oil starvation (Subaru boxer)",
            prevalence=0.45,
            engine_families=["subaru_ej25_sohc", "subaru_ej25_dohc", "subaru_ej20", "subaru_ez36"],
            field_tests=[
                "Knock increases with RPM and load",
                "Knock present even when warm",
                "Oil pressure at hot idle < 14 psi = concern",
                "Inspect oil pickup tube — clogged with RTV or debris?",
            ],
            repair_procedure=[
                "WARNING: Catastrophic failure imminent. Do not drive.",
                "1. Confirm with stethoscope — loudest at oil pan / block seam on cyl 2 or 4",
                "2. Drop oil pan. Inspect pickup tube and baffle. Clean or replace.",
                "3. Remove affected rod cap. Inspect bearing with plastigage.",
                "4. If crank is scored: engine rebuild or short block replacement.",
                "5. On turbo models: add oil pan baffle to prevent starvation in corners.",
            ],
            parts_needed=["rod bearings", "oil pickup tube", "oil pan baffle", "short block maybe"],
            severity="critical",
        ),
        Cause(
            name="Piston slap (Subaru FB/FA cold start)",
            prevalence=0.25,
            engine_families=["subaru_fb25", "subaru_fb20", "subaru_fa20", "subaru_fa24"],
            field_tests=[
                "Knock disappears after 5–10 min warm-up",
                "Louder at cold start, gone at operating temp",
            ],
            repair_procedure=[
                "Often cosmetic on high-mileage FB/FA engines.",
                "1. Use correct viscosity oil (0W-20 for FB/FA)",
                "2. Monitor oil consumption",
                "3. Full repair = piston + bore overhaul",
            ],
            parts_needed=["pistons", "rings", "hone job"],
            severity="normal",
        ),
    ],
}


# ─── Engine Family Database ────────────────────────────────────────────────────

ENGINE_FAMILY_ALIASES: dict[str, list[str]] = {
    "toyota_22re":    ["22re", "22r", "toyota 2.4", "toyota pickup", "toyota 4runner 1985-2004"],
    "toyota_2jz":     ["2jz", "2jz-ge", "2jz-gte", "supra", "aristo", "lexus gs300", "is300", "3.0 i6 toyota"],
    "toyota_1mz":     ["1mz", "1mz-fe", "avalon", "camry v6 1994", "sienna", "solara", "es300", "highlander v6", "3.0 v6 toyota"],
    "toyota_1zz":     ["1zz", "1zz-fe", "corolla", "matrix", "pontiac vibe", "celica gt", "1.8 toyota"],
    "toyota_2zz":     ["2zz", "2zz-ge", "celica gts", "lotus elise", "lotus exige", "corolla xrs", "matrix xrs", "vvtl-i"],
    "toyota_2gr":     ["2gr", "2gr-fe", "camry v6 2007", "avalon v6 2005", "highlander v6 2008", "rav4 v6", "sienna v6", "lexus es350", "rx350", "gs350", "venza v6", "3.5 v6 toyota"],
    "toyota_5vz":     ["5vz", "5vz-fe", "tacoma v6 1995", "4runner v6", "tundra v6", "t100 v6", "3.4 v6 toyota"],
    "toyota_2tr":     ["2tr", "2tr-fe", "tacoma 2.7", "4runner 2.7", "hilux 2.7", "fortuner 2.7"],
    "toyota_3sgte":   ["3sgte", "3s-gte", "celica gt-four", "mr2 turbo", "caldina gt-t", "ct26", "ct20b"],
    "toyota_1uz":     ["1uz", "1uz-fe", "ls400", "sc400", "lexus v8 4.0", "cressida v8"],
    "toyota_2uz":     ["2uz", "2uz-fe", "land cruiser", "tundra v8", "sequoia", "lx470", "lexus v8 4.7"],
    "toyota_7m":      ["7m", "7m-ge", "7m-gte", "supra mk3", "cressida turbo", "3.0 i6 turbo toyota"],
    "ford_300":       ["300", "4.9l", "ford inline 6", "ford f-150 1965-1996", "ford e-150"],
    "honda_b_series": ["b16", "b18", "b20", "integra", "civic si", "cr-v b20"],
    "honda_d_series": ["d15", "d16", "d17", "civic dx", "civic lx", "del sol", "cr-x", "1.5 honda", "1.6 honda", "1.7 honda"],
    "honda_f_series": ["f20", "f22", "f23", "accord 2.2", "prelude 2.2", "prelude 2.3", "accord 2.3", "odyssey 2.2", "odyssey 2.3"],
    "honda_h_series": ["h22", "h23", "prelude vtec", "prelude type sh", "prelude 2.2", "prelude 2.3"],
    "honda_j_series": ["j30", "j35", "j37", "accord v6", "odyssey v6", "pilot v6", "ridgeline v6", "tl v6", "mdx v6", "3.0 honda v6", "3.5 honda v6", "3.7 honda v6"],
    "honda_k_series": ["k20", "k24", "civic si 2006", "rsx", "tsx", "cr-v 2.4", "element 2.4", "accord 2.4", "ilx 2.0"],
    "honda_r_series": ["r18", "civic 1.8", "civic 2006", "civic 2012"],
    "chevy_350":      ["350", "5.7", "small block", "chevrolet 350", "gm 350"],
    "jeep_4_0":       ["4.0", "4.0l i6", "jeep cherokee", "jeep wrangler", "grand cherokee"],
    "bmw_m54":        ["m54", "bmw 3.0", "bmw 2.5", "e46", "e39", "x3"],
    "vw_ea888":       ["ea888", "2.0t", "tsi", "golf gti", "audi a4 2.0t"],
    "nissan_ka24de":  ["ka24", "ka24de", "nissan frontier", "nissan xterra", "2.4 dohc"],
    "mazda_13b":      ["13b", "13b-rew", "rx-7", "rx-8", "rotary"],
    # ── Subaru ───────────────────────────────────────────────────────────────
    "subaru_ej22":    ["ej22", "2.2 subaru", "legacy 2.2"],
    "subaru_ej25_sohc": ["ej25 sohc", "ej25", "2.5 sohc subaru", "forester 2.5", "outback 2.5 2000"],
    "subaru_ej25_dohc": ["ej25 dohc", "ej257", "wrx sti 2.5", "sti engine"],
    "subaru_ej20":    ["ej20", "ej205", "wrx 2.0", "wrx engine"],
    "subaru_ea82":    ["ea82", "loyale", "gl"],
    "subaru_ez36":    ["ez36", "h6 subaru", "3.6r", "outback 3.6"],
    "subaru_fa20":    ["fa20", "brz engine", "86 engine", "fr-s engine"],
    "subaru_fa24":    ["fa24", "wrx 2022", "brz 2022"],
    "subaru_fb25":    ["fb25", "forester 2011", "outback 2013"],
    "subaru_fb20":    ["fb20", "impreza 2.0", "crosstrek 2.0"],
    "subaru_cb18":    ["cb18", "ascent engine", "outback turbo"],
    "subaru_ej18":    ["ej18", "1.8 subaru"],
    # ── Early American ─────────────────────────────────────────────────────
    "ford_model_t":   ["model t", "tin lizzie"],
    "ford_model_a":   ["model a", "a-bone"],
    "ford_flathead_v8": ["flathead", "flatty", "ford v8 1932", "mercury flathead"],
    "ford_y_block":   ["y-block", "ford 292", "ford 312", "thunderbird 1955"],
    "ford_fe":        ["fe", "ford 390", "ford 427", "ford 428", "side oiler", "galaxie 390"],
    "ford_windsor":   ["windsor", "302", "351w", "289", "5.0", "mustang 5.0"],
    "ford_cleveland": ["351c", "351m", "400 ford", "cleveland"],
    "ford_triton":    ["triton", "4.6", "5.4", "expedition 5.4", "f-150 5.4", "f-150 4.6", "crown vic 4.6", "modular ford"],
    "ford_ecoboost":  ["ecoboost", "2.0 ecoboost", "2.3 ecoboost", "3.5 ecoboost", "2.7 ecoboost", "f-150 ecoboost", "focus st", "mustang ecoboost"],
    "chevy_stovebolt_6": ["stovebolt", "chevy 216", "chevy 235", "chevy 261", "inline 6 chevy old"],
    # ── Japanese ───────────────────────────────────────────────────────────
    "nissan_sr20":    ["sr20", "sr20det", "sr20de", "silvia", "sentra se-r"],
    "nissan_vg":      ["vg30", "vg33", "300zx", "pathfinder 3.3", "frontier 3.3"],
    "nissan_vq35":    ["vq35", "vq35de", "350z engine", "altima 3.5", "maxima 3.5"],
    "mazda_bp":       ["bp", "b6", "miata 1.8", "mx-5 engine", "protege 1.8"],
    "mazda_mzr":      ["mzr", "l3", "duratec 2.3", "mazda 3 2.3", "mazda 6 2.3"],
    "mitsubishi_4g63": ["4g63", "evo engine", "eclipse turbo", "4g63t"],
    # ── European ───────────────────────────────────────────────────────────
    "bmw_n54":        ["n54", "335i engine", "135i engine", "535i engine"],
    "bmw_n55":        ["n55", "335i 2011", "x5 35i"],
    "mercedes_m112":  ["m112", "m113", "e320 engine", "ml320 engine", "c320 engine"],
    # ── Diesel ─────────────────────────────────────────────────────────────
    "cummins_59":     ["cummins", "5.9 cummins", "6.7 cummins", "12 valve", "24 valve", "ram 2500", "ram diesel"],
    "ford_73_powerstroke": ["7.3", "7.3 powerstroke", "powerstroke", "f-250 7.3"],
    "ford_60_powerstroke": ["6.0 powerstroke", "6.0", "bulletproof"],
}


def _detect_engine_family(make: str | None, model: str | None, engine: str | None) -> str | None:
    """
    Try to map user input to a known engine family slug.
    
    Returns the slug or None if we can't determine it.
    This is fuzzy matching — we're forgiving about spacing and case.
    """
    text = " ".join(filter(None, [make, model, engine])).lower()
    for slug, aliases in ENGINE_FAMILY_ALIASES.items():
        for alias in aliases:
            if alias in text:
                return slug
    return None


# ─── Diagnostic Engine ─────────────────────────────────────────────────────────

class DiagnosticEngine:
    """
    Offline diagnostic knowledge graph for combustion engines.

    No API calls. No database. Just a big Python dict of accumulated
    mechanic wisdom, encoded as a decision tree.
    """

    def diagnose(
        self,
        symptom_slug: str,
        make: str | None = None,
        model: str | None = None,
        engine: str | None = None,
        year: int | None = None,
    ) -> DiagnosisResult:
        """
        Diagnose a symptom. All parameters are optional — more info = better result.
        """
        # Normalize symptom slug
        symptom = symptom_slug.lower().replace(" ", "_").replace("-", "_")

        # Fall back gracefully for unknown symptoms
        if symptom not in SYMPTOM_CAUSES:
            return DiagnosisResult(
                symptom=symptom,
                ranked_causes=[{
                    "name": "Unknown symptom — consult shop manual or experienced tech",
                    "severity": "normal",
                    "score": 0.0,
                }],
                tests=["Describe symptom more specifically (overheating, no-start, misfire, knocking, smoke color)"],
                repair_procedure="Cannot determine repair without known symptom.",
                confidence=0.05,
                estimated_time="Unknown",
                warnings=["No match in local knowledge base. Consider professional scan."],
                vehicle_info={"make": make, "model": model, "engine": engine, "year": year},
            )

        causes = SYMPTOM_CAUSES[symptom]
        family = _detect_engine_family(make, model, engine)

        # Score each cause
        scored: list[tuple[float, Cause]] = []
        for cause in causes:
            score = cause.prevalence

            # Boost if engine family is known and this cause is common for it
            if family and family in cause.engine_families:
                score *= 1.5

            # Year-based adjustments (some issues cluster by era)
            if year:
                if year < 1990 and "carburetor" in cause.name.lower():
                    score *= 1.2
                if year > 2005 and "coil" in cause.name.lower():
                    score *= 1.1

            scored.append((score, cause))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)

        # Build ranked causes output
        ranked = []
        for score, cause in scored:
            ranked.append({
                "name": cause.name,
                "severity": cause.severity,
                "score": round(score, 3),
                "parts_needed": cause.parts_needed,
            })

        # Top cause drives the tests and procedure
        top = scored[0][1]

        # Confidence formula: base 0.3 + 0.1 per provided param + bonus for known family
        num_params = sum(x is not None for x in [make, model, engine, year])
        confidence = min(0.3 + num_params * 0.15 + (0.2 if family else 0.0), 0.95)

        # Estimate time from severity
        severity_time = {
            "normal": "1–3 hours",
            "urgent": "2–4 hours",
            "critical": "4–10+ hours (possible engine removal)",
        }
        est_time = severity_time.get(top.severity, "Unknown")

        # Warnings
        warnings: list[str] = []
        if top.severity == "critical":
            warnings.append("This is a critical repair. Stop driving immediately.")
        if family and family in ["honda_b_series", "mazda_13b"]:
            warnings.append("Interference engine — timing failure risks valve damage.")

        return DiagnosisResult(
            symptom=symptom,
            ranked_causes=ranked,
            tests=top.field_tests,
            repair_procedure=top.repair_procedure,
            confidence=round(confidence, 2),
            estimated_time=est_time,
            warnings=warnings,
            vehicle_info={"make": make, "model": model, "engine": engine, "year": year},
        )
