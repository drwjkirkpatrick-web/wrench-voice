# Toyota 2JZ-GE / 2JZ-GTE

## Overview
The Toyota 2JZ is a 3.0 liter inline-6 produced from 1991 to 2007 in the Toyota Supra (MKIV), Lexus GS300, Lexus IS300, and Toyota Aristo. Two variants: 2JZ-GE (naturally aspirated, 220 hp) and 2JZ-GTE (twin-turbo, 276 hp in Japan, 320+ hp in export markets). Cast iron block, aluminum head, dual overhead cam, 24 valves, timing belt (interference design). The 2JZ is widely regarded as one of the most over-engineered and robust inline-6 engines ever built, capable of 800+ hp on stock internals with proper tuning and fuel.

## Known Issues
- **Timing belt tensioner failure** — Hydraulic tensioner leaks down, causing belt slack and valve timing drift. Rattle at startup. Replace tensioner with belt every 60k miles.
- **VVT-i solenoid oil screen clogging** — Oil screen on VVT-i solenoid traps debris, preventing cam phasing. Symptoms: rough idle, low-end torque loss, P0011/P0012 codes.
- **Camshaft seal leak** — Front cam seals harden and leak oil onto timing belt. Oil-soaked belt = accelerated wear = catastrophic failure on interference engine.
- **Turbocharger oil line restriction (GTE)** — Stock oil feed line has a small diameter that carbonizes with age. Restricted flow starves turbo bearings, causing seal failure and smoke. Upgrade to braided stainless line.
- **Supra sequential turbo transition lag (GTE)** — The #2 turbo activation solenoid fails, causing a dead zone around 4,000 RPM where boost drops before #2 spools. Replace solenoid and check vacuum lines.
- **Valve stem seal leakage (GE)** — Oil drips past hardened valve seals, causing blue smoke on cold start. Does not affect GTE as severely due to positive crankcase pressure from turbos.
- **Water pump weep hole seepage** — Ceramic seal wears, coolant weeps from pump. Early sign = crusty residue at weep hole.
- **Ignition coil failure (pre-1998)** — Early distributors and coil-on-plug systems had weaker coils. Misfire under boost on GTE.

## Torque Specs
| Component | ft-lbs | Nm | Notes |
|-----------|--------|----|-------|
| Head bolts | 34 + 90° | 46 + angle | TTY — MUST replace |
| Rod bolts | 30 + 90° | 41 + angle | Stretch gauge |
| Main cap bolts | 18 + 90° | 24 + angle | 
| Flywheel | 61 | 83 | 
| Harmonic balancer | 217 | 294 | Requires SST 09213-70010 holder |
| Intake manifold | 15 | 20 | 
| Exhaust manifold | 29 | 39 | Anti-seize on studs (GTE runs hot) |
| Valve cover | 7 | 10 | 
| Timing belt tensioner | 21 | 28 | 
| Idler pulley | 21 | 28 | 
| Spark plugs | 13 | 18 | 
| Water pump | 15 | 20 | 
| Turbocharger nuts (GTE) | 33 | 45 | Copper nuts on manifold side |
| Cam cap bolts | 9 | 12 | Inside → out sequence |
| VVT-i solenoid | 7 | 10 | 

## Fluid Capacities
| Fluid | Capacity | Specification |
|-------|----------|---------------|
| Engine oil | 5.5 quarts | 10W-30 synthetic (GTE: 10W-40 for high boost) |
| Coolant | 10.5 quarts | Toyota Red Long Life |
| Transmission (manual R154) | 2.6 quarts | 75W-90 GL-4 |
| Transmission (auto A340E) | 7.5 quarts | Dexron III |
| Differential (rear) | 1.5 quarts | 75W-90 GL-5 (GTE: use LSD additive if Torsen) |
| Brake fluid | Fill to max | DOT 3 or 4 |
| Power steering | Fill to max | Dexron II/III |
| Turbo oil (GTE reservoir) | 0.5 quart | Same as engine oil |

## Maintenance Schedule
| Interval | Service |
|----------|---------|
| 3,000 miles | Oil + filter (GTE: check oil for fuel dilution after track use) |
| 30,000 miles | Spark plugs (NGK BKR6E or 7E for boosted), inspect timing belt cover for oil |
| 60,000 miles | **TIMING BELT + tensioner + water pump + idler** — non-negotiable on interference engine |
| 60,000 miles | VVT-i oil screen cleaning or replacement |
| 100,000 miles | Turbo rebuild assessment (GTE — check shaft play and seal condition) |

## Common Procedures

### Timing Belt Replacement
1. Set to TDC #1 compression. Remove upper and lower timing covers.
2. Remove crank pulley (217 ft-lb — requires Toyota SST holder tool or strong impact).
3. **WARNING: Interference engine.** If belt is removed and cams/crank move independently, valves WILL contact pistons.
4. Loosen tensioner bolt. Remove old belt. Inspect for oil contamination (indicates cam seal leak).
5. If oil on belt: replace BOTH cam seals before installing new belt. This is mandatory.
6. Install new belt with Toyota marks aligned: crank sprocket dot at 12 o'clock, cam sprocket "E" or "I" marks aligned with backing plate marks.
7. Install new tensioner (always replace with belt). Set tensioner pin to retracted position.
8. Release tensioner. Belt should have approximately 1/2 inch deflection between cam sprocket and idler.
9. Hand-turn crank TWO full revolutions. Recheck marks. Must align perfectly.
10. Install covers, torque crank pulley to 217 ft-lb. Verify no leaks at cam seals.

### VVT-i Solenoid Cleaning / Replacement
1. Remove valve cover. Solenoid is on intake cam cover, near front.
2. Remove 10 mm bolt. Pull solenoid. Catch the small oil screen (it falls out).
3. Soak screen in brake cleaner. Blow out passages with compressed air.
4. Check solenoid resistance: 6.9–7.9 Ω at 68°F (20°C).
5. Reinstall with fresh O-ring. If screen is damaged or solenoid ohms out of spec, replace unit.
6. Clear adaptations. Drive 10 miles to relearn VVT-i position.

## Special Tools
- Toyota SST 09213-70010 (crankshaft pulley holder)
- SST 09960-10010 (timing belt installation tool — optional but helps)
- Torque angle gauge (TTY bolts mandatory)
- Dial indicator (checking VVT-i cam phasing range)
- Compressor tester with rotary adapter (not applicable — 2JZ is piston)

## Common Mistakes
- **Reusing timing belt tensioner** — The hydraulic damper loses pressure. New tensioner with every belt is mandatory.
- **Ignoring oil on timing belt** — A $15 cam seal prevents a $4,000 valve job. Always inspect.
- **Wrong spark plug heat range** — GTE under boost needs colder plugs (BKR7E or 8E). Stock heat range = detonation.
- **Neglecting turbo oil feed line** — The stock hard line carbonizes internally. Upgrade to braided line before failure.
- **GTE without LSD additive** — Torsen differentials chatter without friction modifier in GL-5.
- **Sequential turbo dead zone** — Vacuum line to turbo #2 actuator cracks with heat. Inspect all small hoses.

## GTE Turbo Notes
- Stock boost: 11 PSI sequential (turbo #1), 14 PSI combined
- Fuel cut: 14.5 PSI on stock ECU
- Injector limit: 440cc stock; 550cc+ needed for 400+ whp
- Intercooler: Stock is adequate to 400 whp; upgrade for more
- MAP sensor: Stock reads to 2.0 bar; replace for higher boost
- Head gasket: Stock MLS holds to ~600 whp on pump gas with proper tuning
