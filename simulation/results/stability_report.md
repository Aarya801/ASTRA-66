> **PLACEHOLDER TEST INPUT.** `simulation/motor_config.json` has `status: PLACEHOLDER`. The thrust curve is the synthetic signal `simulation/motors/PLACEHOLDER_TEST_INPUT.eng`: it is not a real motor, a product or performance data. Trajectory numbers here verify the software and show sensitivities only. They are **not predictions** and must not be used for flight planning. The design is **not flight certified**; a qualified mentor or institution must review it before any flight.

# ASTRA-66 stability report

Generated 2026-09-19 by `simulation/flight_simulation.py` from CAD rev B (0 FAIL in CAD validation).

Target range used below is an **engineering requirement** (1.5–3.0 calibres, from the package's operating envelope), not a flight approval.

## 1. Centre of pressure

| Source | CNα nose | CNα fins | CNα total /rad | CP STA mm |
|---|---|---|---|---|
| Independent Barrowman on CAD-measured geometry (`stability.py`) | 2.00 | 8.233 | 10.233 | 870.32 |
| `analysis.py` (design parameters) | 2.00 | 8.233 | 10.233 | 870.32 |

CAD geometry used: nose 264.0 mm; fins N=4, root 150.0, tip 60.0, semispan 60.0, LE sweep 70.0 mm; LE at STA 994.0; d = 66.0 mm.

## 2. Centre of gravity and static margin

| Condition | Mass g | CG STA mm | Static margin cal | Data basis |
|---|---|---|---|---|
| No motor (airframe only) | 1,100.7 | 656.9 | 3.23 | A×C airframe; motor excluded but includes placeholder retainer mass and MMT geometry |
| Liftoff | 1,210.7 | 696.4 | 2.63 | includes D placeholder motor |
| Rail exit (t = 0.19 s) | — | — | 2.67 | placeholder |
| Minimum during powered flight | — | — | 2.63 | placeholder |
| Burnout | 1,155.7 | — | 2.92 | placeholder |

## 3. Requirement check

| ID | Requirement | Value cal | Result |
|---|---|---|---|
| REQ-STAB-1 | 1.5 <= SM <= 3.0 cal at rail exit | 2.67 | PASS (placeholder motor) |
| REQ-STAB-2 | SM >= 1.5 cal throughout powered flight | 2.63 | PASS (placeholder motor) |
| REQ-STAB-3 | SM <= 3.0 cal at liftoff | 2.63 | PASS (placeholder motor) |

## 4. Sensitivity of the margin

**Airframe mass** (all non-motor mass scaled, CG unchanged)

| mass_scale [x] | SM liftoff | SM rail exit | SM burnout | REQ-STAB-1 |
|---|---|---|---|---|
| 0.8 | 2.50 | 2.54 | 2.85 | PASS |
| 0.9 | 2.57 | 2.61 | 2.89 | PASS |
| 1.0 | 2.63 | 2.67 | 2.92 | PASS |
| 1.1 | 2.68 | 2.72 | 2.95 | PASS |
| 1.2 | 2.73 | 2.76 | 2.97 | PASS |

**Payload mass** (added at the payload-bay centre (STA 381))

| payload_g [g] | SM liftoff | SM rail exit | SM burnout | REQ-STAB-1 |
|---|---|---|---|---|
| 0 | 2.63 | 2.67 | 2.92 | PASS |
| 50 | 2.82 | 2.86 | 3.11 | PASS |
| 100 | 3.00 | 3.04 | 3.28 | FAIL |
| 150 | 3.16 | 3.20 | 3.44 | FAIL |
| 200 | 3.31 | 3.35 | 3.58 | FAIL |
| 300 | 3.58 | 3.62 | 3.85 | FAIL |

**Airframe CG shift** (+ = aft; trajectory unchanged in 1-DOF)

| cg_shift_mm [mm] | SM liftoff | SM rail exit | SM burnout | REQ-STAB-1 |
|---|---|---|---|---|
| -30 | 3.05 | 3.09 | 3.35 | FAIL |
| -20 | 2.91 | 2.95 | 3.21 | PASS |
| -10 | 2.77 | 2.81 | 3.06 | PASS |
| 0 | 2.63 | 2.67 | 2.92 | PASS |
| 10 | 2.50 | 2.53 | 2.78 | PASS |
| 20 | 2.36 | 2.40 | 2.63 | PASS |
| 30 | 2.22 | 2.26 | 2.49 | PASS |

**Low-cost build** (removes EL-CAM, EL-GPS, PL-203, PL-204): SM liftoff 2.34, rail exit 2.37, burnout 2.62 cal. Nose ballast needed to restore a 1.5 cal liftoff margin: 0 g.

## 5. Findings

- **Payload limit:** more than about **100 g** added at the payload-bay centre pushes the liftoff margin above 3.0 cal (over-stable, strong weathercocking). Heavier payloads need mentor agreement, a more aft position, or a re-check with the real motor, which usually lowers the margin.

- CP from the CAD geometry agrees with `analysis.py` to 0.000 mm.
- The airframe **without a motor** has 3.23 cal. This value excludes the motor but still contains the placeholder retainer mass (25 g) and the MMT sized from placeholder data. Any motor adds mass aft and lowers the margin: the heavier the certified motor, the lower the margin (see the `analysis/analysis.py` sensitivity).
- Every 10 mm of airframe CG error changes the margin by about 0.14 cal. **Measure the CG with the real motor installed** (test T-03).
- Liftoff margin with the placeholder motor (2.63 cal) sits in the upper half of the target range. A heavier motor, more aft paint/epoxy or a lighter nose moves it down.

## 6. Limitations
- Barrowman: subsonic, small angle of attack, no body lift, rigid body, no fin–body interference beyond K_FB. OpenRocket/RASAero cross-check required.
- Static margin only; dynamic stability (pitch damping, roll coupling) is not assessed.
- Masses are CAD volume × assumed density/fill, plus assumed electronics and recovery masses. Weigh every part.

