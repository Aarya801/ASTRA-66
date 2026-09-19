# ASTRA-66 — Engineering status

> **Draft student engineering design. NOT flight certified.** Propulsion is an external, commercially certified component, never designed, modified or produced here. Any launch requires review and sign-off by a qualified rocketry mentor or institution and the range safety officer.

Generated 2026-09-19T21:18:28 by `python run_validation.py` from the current result files. Pipeline result: **PASS**. Motor data status: **PLACEHOLDER**.

## 1. Status summary

| Area | Status | Basis |
|---|---|---|
| CAD | PASS | 25 parametric parts + master assembly; committed validation current (source hash match) |
| CAD validation | PASS | 147 PASS · 12 WARN (accepted) · 0 FAIL · 0 interferences; `documentation/CAD_VALIDATION.md` |
| Simulation | PASS | 13/13 numerical verification checks; trajectory **ILLUSTRATIVE ONLY (placeholder propulsion)** |
| Stability | PASS (placeholder motor) | CP STA 870.32 mm (CAD cross-check exact); SM liftoff 2.63 / rail exit 2.67 / burnout 2.92 cal vs 1.5–3.0 target |
| Mass properties | PASS | liftoff 1210.7 g identical in analysis, CAD validation and simulation; CG STA 696.4 mm |
| Sensitivity analysis | PASS | 8 non-propulsion parameters; `simulation/results/sensitivity_report.md` |
| Reproducibility | PASS | one command, standard library only; regression tests re-derive committed outputs |
| Documentation | PASS | file references and disclaimers checked by `tests/test_docs.py` |

## 2. Value classes

### VERIFIED FROM CAD (measured on the rendered OpenSCAD meshes)
- Overall length 1144.0 mm; body OD 66.0 mm; nose length 264 mm; fin span tip-to-tip 186 mm; fin root / tip / sweep 150 / 60 / 70 mm; fin LE at STA 994 mm.
- Bay lengths: payload 114 mm, avionics 158.5 mm, recovery 273.5 mm. Rail buttons at STA 885 / 1115 on the 45° line.
- Part volumes of 21 structural items; closed-manifold geometry; zero interferences; fins removable with the retainer fitted.
### CALCULATED
- CP STA 870.32 mm (Barrowman, from CAD geometry); CG liftoff STA 696.4 mm; static margins; structural masses (volume × density × fill).
- Simulated trajectory, loads, descent rate 5.09 m/s, sensitivity deltas (1-DOF model).
### ASSUMED
- Material densities and print fill factors; electronics, recovery, paint and adhesive masses.
- Drag build-up coefficients (roughness 2e-05 m, protuberances 8%); parachute Cd 0.8.
- ISA standard atmosphere, no wind, vertical flight, parachute open at apogee; structural allowables; design load factor.
### PLACEHOLDER
- **Propulsion:** motor mass/length, thrust curve (`simulation/motors/PLACEHOLDER_TEST_INPUT.eng`, synthetic), retainer mass/OD, MMT bore/length. **Every trajectory, acceleration, altitude and apogee result depends on these and is NOT representative of any real motor.**
- Camera, battery and switch envelopes; heat-set insert and tee-nut sizes; rail-button, eyebolt and retainer envelopes; rail length 1.0 m; launch site (PLANNING_DEFAULT: 0.0 m, ISA+0 K).
### REQUIRES PHYSICAL MEASUREMENT
- Tube, coupler and MMT diameters (3 stations × 2 axes); mass of every part and module; CG with the actual motor installed (test T-03).
- Printed fit coupons (shoulder, guide slot, inserts); fin alignment; separation force at I-03; recovery static proof load.
- Parachute descent rate (drop test); camera field of view through the Ø14 mm hole; battery endurance on the pad.

## 3. Unresolved issues (including minor)

1. **Propulsion data are placeholders** (`motor_config.json` status PLACEHOLDER). Stability margins with the motor and all trajectory values are provisional.
2. **Rail-exit speed 11.7 m/s** on the 1.0 m planning rail is below the 15 m/s guideline with the placeholder input. The range's rail and the certified motor must be checked together.
3. **Payload limit:** about 100 g extra in the payload bay pushes the margin above 3.0 cal (over-stable).
4. **No-motor margin:** the 3.23 cal value still includes the placeholder retainer mass and MMT geometry.
5. **CAD warnings:** 12 accepted. 11 printed parts need support in the chosen pose; the PL-205 hatch wall is 1.0 mm (0.25 mm nozzle recommended).
6. **Drag model** is an uncalibrated build-up. It needs cross-checking with OpenRocket/RASAero and flight data.
7. **Flight model** is 1-DOF: no wind, weathercocking, angle of attack or drift. Dynamic stability is not assessed.
8. **Structural adequacy** relies on hand calculations with conservative allowables. There is no FEA and no coupon test data yet.
9. **Printability** was judged by a 45° overhang rule only; not yet checked in a slicer.
10. **Tooling:** OpenSCAD is an external tool, not bundled. CAD regeneration needs it (`--with-cad`); the default run checks the committed CAD instead.
11. **Dates:** generated reports carry the run date, so outputs are deterministic except for those date fields.

## 4. Mentor / institution review required before any launch

- Selection of a legally obtainable certified motor and its published data. Motor preparation and handling are done by a certified person only.
- Ejection-delay choice from the manufacturer's options, using the simulated coast time.
- Static margin with the real motor and a measured CG. Rail-exit speed against the range's rules.
- Retainer installation, recovery hardware ratings and proof loads, and fin/rail alignment inspection.
- Complete flight-readiness review (package §18) and range safety officer approval on the day.

