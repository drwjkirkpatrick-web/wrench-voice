# Engine Family Matrix

Complete reference of all engine families tracked in `vehicle_specs.db` and `diagnostic_engine.py`.

## Subaru (Boxer)
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `subaru_ej18` | EJ18 | 1.8L | Flat-4 | 1993–1997 | Belt | Yes | Simple, reliable |
| `subaru_ej22` | EJ22 | 2.2L | Flat-4 | 1990–1997 | Belt | Yes | Bulletproof, no HG issues |
| `subaru_ej25_sohc` | EJ25 | 2.5L | Flat-4 | 1998–2010 | Belt | Yes | **External HG leak** |
| `subaru_ej25_dohc` | EJ25 | 2.5L | Flat-4 | 2004–2014 | Belt | Yes | Ringland failure |
| `subaru_ej20` | EJ20 | 2.0L | Flat-4 | 1992–2014 | Belt | Yes | Case half leak |
| `subaru_ea82` | EA82 | 1.8L | Flat-4 | 1985–1994 | Belt | Yes | Pushrod seal leak |
| `subaru_ez36` | EZ36 | 3.6L | Flat-6 | 2010–2019 | Chain | Yes | Timing chain guide rattle |
| `subaru_fa20` | FA20 | 2.0L | Flat-4 | 2012–2021 | Chain | Yes | Valve spring recall, RTV in pickup |
| `subaru_fa24` | FA24 | 2.4L | Flat-4 | 2022–present | Chain | Yes | Turbo wastegate rattle |
| `subaru_fb25` | FB25 | 2.5L | Flat-4 | 2011–present | Chain | Yes | Oil consumption, CVT chain slip |
| `subaru_fb20` | FB20 | 2.0L | Flat-4 | 2011–present | Chain | Yes | Oil consumption |
| `subaru_cb18` | CB18 | 1.8L | Flat-4 | 2020–present | Chain | Yes | New turbo DI, early data |

## Toyota
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `toyota_22re` | 22RE | 2.4L | I4 | 1983–2004 | Chain | No | Exhaust manifold crack, chain rattle |
| `toyota_2jz` | 2JZ | 3.0L | I6 | 1991–2005 | Belt | Yes | Turbo oil seal (GTE) |
| `toyota_1mz` | 1MZ-FE | 3.0L | V6 | 1993–2006 | Belt | Yes | Oil sludge (1997–2001) |
| `toyota_1zz` | 1ZZ-FE | 1.8L | I4 | 1997–2008 | Chain | Yes | Oil consumption (1998–2002) |
| `toyota_2zz` | 2ZZ-GE | 1.8L | I4 | 1999–2006 | Chain | Yes | Lift bolt wear |
| `toyota_2gr` | 2GR-FE | 3.5L | V6 | 2005–present | Chain | Yes | Water pump leak |
| `toyota_5vz` | 5VZ-FE | 3.4L | V6 | 1995–2004 | Belt | Yes | Valve cover gasket |
| `toyota_2tr` | 2TR-FE | 2.7L | I4 | 2004–present | Chain | Yes | Chain rattle |
| `toyota_3sgte` | 3S-GTE | 2.0L | I4 | 1986–1999 | Belt | Yes | Turbo oil line coking |
| `toyota_1uz` | 1UZ-FE | 4.0L | V8 | 1989–2000 | Belt | Yes | Front seal leak |
| `toyota_2uz` | 2UZ-FE | 4.7L | V8 | 1998–2011 | Belt | Yes | SAI pump failure |
| `toyota_7m` | 7M-GTE | 3.0L | I6 | 1986–1992 | Belt | Yes | **Blown HG (factory torque error)** |

## Honda
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `honda_b_series` | B-Series | 1.6–2.0L | I4 | 1989–2001 | Belt | Yes | VTEC solenoid clog |
| `honda_d_series` | D-Series | 1.5–1.7L | I4 | 1984–2005 | Belt | Yes | Oil seal leaks |
| `honda_f_series` | F-Series | 2.0–2.3L | I4 | 1989–2002 | Belt | Yes | Balance shaft seal |
| `honda_h_series` | H-Series | 2.2L | I4 | 1992–2001 | Belt | Yes | Oil consumption |
| `honda_j_series` | J-Series | 3.0–3.7L | V6 | 1996–present | Belt | Yes | **VCM oil consumption (J35)** |
| `honda_k_series` | K-Series | 2.0–2.4L | I4 | 2001–2015 | Chain | Yes | Chain rattle, VTC actuator |
| `honda_r_series` | R-Series | 1.8L | I4 | 2006–2015 | Chain | Yes | Chain rattle |

## Ford
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `ford_model_t` | T | 2.9L | I4 | 1908–1927 | Gear | No | No oil pump (splash) |
| `ford_model_a` | A | 3.3L | I4 | 1927–1931 | Gear | No | Babbitt bearings |
| `ford_flathead_v8` | Flathead | 3.6–4.2L | V8 | 1932–1953 | Gear | No | Block crack between exhaust valves |
| `ford_y_block` | Y-block | 4.5–5.1L | V8 | 1954–1964 | Gear | No | Rocker shaft sludge |
| `ford_fe` | FE | 5.4–7.0L | V8 | 1958–1976 | Gear | No | Cam gear failure (nylon) |
| `ford_windsor` | Windsor | 4.3–5.8L | V8 | 1961–2001 | Chain | No | Timing chain rattle |
| `ford_cleveland` | 351C | 5.8–6.6L | V8 | 1970–1982 | Chain | No | Oil starvation to rear main |
| `ford_300` | 300 | 4.9L | I6 | 1965–1996 | Gear | No | Simple, reliable |
| `ford_triton` | Triton | 4.6/5.4L | V8 | 1991–2010 | Chain | Yes | **Spark plug blowout, cam phaser** |
| `ford_ecoboost` | EcoBoost | 2.0–3.5L | I4/V6 | 2009–present | Chain | Yes | Carbon buildup, chain stretch |

## Nissan
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `nissan_ka24de` | KA24DE | 2.4L | I4 | 1997–2004 | Chain | Yes | Chain guide rattle |
| `nissan_sr20` | SR20 | 2.0L | I4 | 1990–2002 | Chain | Yes | Chain guide, oil pump seal |
| `nissan_vg` | VG | 3.0/3.3L | V6 | 1984–2004 | Belt | Yes | Belt failure, turbo oil line |
| `nissan_vq35` | VQ35DE | 3.5L | V6 | 2002–present | Chain | Yes | Oil consumption, chain rattle |

## Mazda
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `mazda_13b` | 13B | 1.3L | Rotary | 1986–2012 | Gear | N/A | Apex seal wear, flooding |
| `mazda_bp` | BP | 1.8L | I4 | 1989–2005 | Belt | Yes | Short-nose crank (B6) |
| `mazda_mzr` | MZR | 2.0–2.5L | I4 | 2003–2013 | Chain | Yes | VVT actuator rattle |

## Mitsubishi
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `mitsubishi_4g63` | 4G63 | 2.0L | I4 | 1981–2012 | Belt | Yes | Crank walk (7-bolt), balance shaft belt |

## BMW
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `bmw_m54` | M54 | 2.5/3.0L | I6 | 2000–2006 | Chain | Yes | CCV failure, cooling system |
| `bmw_n54` | N54 | 3.0L | I6 | 2006–2013 | Chain | Yes | HPFP failure, carbon buildup |
| `bmw_n55` | N55 | 3.0L | I6 | 2009–2019 | Chain | Yes | Electric water pump, Valvetronic |

## Volkswagen/Audi
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `vw_ea888` | EA888 | 1.8–2.0L | I4 | 2008–present | Chain | Yes | Tensioner failure, carbon buildup, oil consumption |

## Mercedes-Benz
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `mercedes_m112` | M112/M113 | 3.2–5.4L | V6/V8 | 1997–2006 | Chain | Yes | Breather hose, MAF failure |

## Chevrolet
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `chevy_350` | 350 | 5.7L | V8 | 1955–2002 | Chain | No | Timing chain rattle |
| `chevy_stovebolt_6` | Stovebolt | 3.2–4.3L | I6 | 1929–1962 | Gear | No | Babbitt bearings (early) |

## Jeep
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `jeep_4_0` | 4.0L | 4.0L | I6 | 1987–2006 | Chain | No | 0331 head crack, oil pump drive |

## Cummins
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `cummins_59` | 5.9/6.7 ISB | 5.9–6.7L | I6 | 1989–present | Gear | No | Killer Dowel Pin, VP44 failure |

## Ford Power Stroke
| Slug | Code | Disp. | Config | Years | Timing | Interference | Known Weakness |
|------|------|-------|--------|-------|--------|--------------|----------------|
| `ford_73_powerstroke` | 7.3L | 7.3L | V8 | 1994–2003 | Gear | No | CPS failure, UVCH failure |
| `ford_60_powerstroke` | 6.0L | 6.0L | V8 | 2003–2007 | Chain | No | **Head bolts, EGR cooler, oil cooler** |

## Maintenance Notes

### Timing Components
- **Belt engines** (most Toyota V6, Honda V6, Subaru EJ, Nissan VG): Replace belt + water pump + tensioner at interval. Interference = critical.
- **Chain engines** (Toyota 2GR, Honda K/R, Subaru FB/FA/EZ, Ford EcoBoost, VW EA888): Inspect tensioner at 120k. Rattle = replace.

### Head Gasket Notes
- **Subaru EJ25 SOHC**: Use MLS gaskets only. Composite fails.
- **Toyota 7M-GTE**: Factory torque spec was WRONG. Use 56 ft-lb or ARP studs.
- **Ford 6.0 Power Stroke**: Must use ARP studs. TTY bolts stretch.

### Oil Notes
- **Toyota 1MZ-FE (1997–2001)**: Prone to sludge. Use synthetic, change every 3k.
- **Honda J35 with VCM**: Disable VCM to prevent ring clogging.
- **VW EA888 Gen 1/2**: Oil consumption from piston rings. Revised pistons in TSB.
- **BMW N54/N55**: Use high-quality synthetic. HPFP sensitive to fuel quality.

## Data Source
All data lives in `data/vehicle_specs.db` (SQLite). Update via the migration scripts in `scripts/` or direct INSERT. Do not hand-edit this markdown without syncing the DB.
