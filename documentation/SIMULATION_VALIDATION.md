> **PLACEHOLDER TEST INPUT.** `simulation/motor_config.json` has `status: PLACEHOLDER`. The thrust curve is the synthetic signal `simulation/motors/PLACEHOLDER_TEST_INPUT.eng`: it is not a real motor, a product or performance data. Trajectory numbers here verify the software and show sensitivities only. They are **not predictions** and must not be used for flight planning. The design is **not flight certified**; a qualified mentor or institution must review it before any flight.

# ASTRA-66 — Simulation validation report

Generated 2026-09-19 by `simulation/flight_simulation.py` (run as part of `python run_validation.py`). CAD rev B, CAD validation 147 PASS / 12 WARN / 0 FAIL. Motor data status: **PLACEHOLDER**.

## 1. Inputs

| Input | Value | Source | Class |
|---|---|---|---|
| Body diameter / length | 66.0 / 1144.0 mm | CAD meshes (validation_results.json) | A |
| Fins | N=4, root 150, tip 60, semispan 60, sweep 70, t 3 mm | CAD meshes | A |
| Airframe mass / CG (no motor) | 1100.7 g / STA 656.9 | analysis.py mass budget (21 CAD-derived items) | A×C + C |
| Motor total / propellant mass | 110 / 55 g | motor_config.json + .eng | D |
| Thrust-time input | PLACEHOLDER-TEST: 115.8 N·s, 1.50 s | motors/PLACEHOLDER_TEST_INPUT.eng | D (synthetic test signal) |
| Drag coefficient | build-up, 0.446 at v_max | aerodynamics.py | C |
| Parachute | ⌀1067 mm, Cd 0.8 | analysis.py | C |
| Rail length / travel to guidance loss | 1.00 m / 0.971 m | analysis.py RAIL_L (USER), button station | C/USER |
| Atmosphere | ISA, sea-level site, no wind | atmosphere.py | C |

## 2. Equations and methods

- **Atmosphere:** ISO 2533 ISA troposphere/tropopause; Sutherland viscosity.
- **Motion:** `m(t) dv/dt = T(t) − ½ρ v|v| C_d A_ref − m g`, `dh/dt = v`. Classical RK4 with dt = 1 ms (burn), 5 ms (coast), 20 ms (descent).
- **Motor mass:** `m_motor(t) = m_total − m_prop · I(t)/I_total` (thrust-curve read-only, RASP .eng format).
- **Drag:** component build-up.
  - Skin friction: `max(0.074 Re^-0.2, 0.032 (ε/L)^0.2)` with form factor `1 + 1/(2 L/D)`.
  - Base drag: `0.12 + 0.13 M²`, with the MMT bore filled by exhaust during the burn.
  - Fin leading/trailing-edge pressure terms, plus an 8 % protuberance allowance.
  - Reference area 34.21 cm²; wetted areas: body 0.2193 m², fins 0.0504 m².
- **Stability:** Barrowman CP re-implemented independently in `stability.py` from CAD-measured geometry; margin = (CP − CG)/d, with CG(t) from the airframe plus the burning motor.
- **Recovery:** after apogee, drag = ½ρ v|v| C_d,chute A_chute (idealised instant deployment at apogee; body drag neglected).
- **Verification:** closed-form comparisons, a time-step convergence test and cross-checks against analysis.py (§6).

## 3. Assumptions

- **Flight model:** vertical 1-DOF flight with no wind, no weathercocking and no angle of attack. The rail only defines where guidance is lost.
- **Drag:** the build-up coefficients, 20 µm surface roughness and 8 % protuberance allowance are ASSUMPTIONS.
- **Recovery:** the parachute opens fully at apogee. The real timing depends on the certified motor's ejection delay (see the ejection-timing table).
- **Mass:** masses are CAD volume × assumed density/fill. Electronics, recovery, paint and adhesive masses are estimates.
- **Atmosphere:** ISA standard day at a sea-level site unless varied. Gravity is constant (9.80665 m/s²).

## 4. Verified CAD-derived values (class A)

| Quantity | Value |
|---|---|
| Overall length | 1144.0 mm |
| Body OD | 66.0 mm |
| Fin span tip-to-tip | 186.0 mm |
| Fin root LE station | 994.0 mm |
| Fin root / tip / sweep | 150.0 / 60.0 / 70.0 mm |
| Nose length | 264.0 mm |
| Structural part masses | 637.5 g (CAD volume × assumed density) |
| CP (from CAD geometry) | STA 870.32 mm (class B, computed from A) |

## 5. Placeholder values (class D)

| Item | Value | Replace with |
|---|---|---|
| Motor total / burnout mass | 110 / 55 g | certified motor data (motor_config.json) |
| Motor length / MMT / retainer | 125 mm / ⌀29×260 mm / ⌀39 mm | manufacturer drawings |
| Thrust-time curve | PLACEHOLDER-TEST (synthetic) | certified motor's published .eng file |
| Retainer mass (in airframe mass, also in the no-motor margin) | 25 g | weighed commercial retainer |
| Burn-phase base-drag relief area | MMT_ID ⌀29 mm | certified motor/MMT data |
| Camera, battery, switch envelopes | see analysis/results/parameters.csv (USER) | measured parts |
| Rail length | 1.0 m | range data |

Mass by data class: A x C (CAD volume x assumed density/fill): 637 g; B calculated: 53 g; C assumption: 350 g; D placeholder (user to measure): 35 g; D placeholder (external component): 135 g

## 6. Simulation outputs

| Result | Value | Note |
|---|---|---|
| Thrust-to-weight, peak / average | 8.4 / 6.5 | placeholder input; liftoff (T > W) at t = 0.006 s |
| Rail-exit velocity | 11.7 m/s | at t = 0.19 s |
| Burnout | t 1.50 s, h 68.5 m, v 79.9 m/s |  |
| Max velocity / Mach | 80.3 m/s / 0.236 |  |
| Max acceleration | 7.4 g |  |
| Max dynamic pressure | 3925 Pa |  |
| Apogee | 328.2 m at t = 8.51 s | illustrative |
| Coast burnout → apogee | 7.01 s | compare with the motor's delay options (mentor) |
| Descent rate / time | 5.09 m/s / 64.4 s | chute ⌀1067 mm |

**Envelope checks (design limits from the package):**

| Check | Value | Result |
|---|---|---|
| Rail-exit velocity >= 15 m/s (guideline) | 11.74 | FAIL (placeholder) |
| Max velocity <= 90 m/s (airframe design limit) | 80.30 | PASS (placeholder) |
| Max axial acceleration <= 15 g (design load factor) | 7.43 | PASS (placeholder) |
| Mach < 0.3 (incompressible assumptions valid) | 0.24 | PASS (placeholder) |
| Descent rate 4.5-6.0 m/s (package target) | 5.09 | PASS (placeholder) |

**Recovery-event timing sensitivity** (speed if the event happens Δt from apogee, ballistic):

| Δt s | speed m/s | altitude m |
|---|---|---|
| -3 | 30.2 | 283.5 |
| -2 | 19.8 | 308.5 |
| -1 | 9.8 | 323.3 |
| 0 | 0.0 | 328.2 |
| 1 | 9.8 | 323.3 |
| 2 | 19.4 | 308.7 |
| 3 | 28.7 | 284.6 |

**Numerical verification:**

| Check | Expected | Computed | Tolerance | Result |
|---|---|---|---|---|
| ISA density at 0 m [kg/m3] | 1.22500 | 1.22500 | 0.05 % | PASS |
| ISA density at 11 000 m [kg/m3] | 0.36392 | 0.36392 | 0.1 % | PASS |
| ISA speed of sound at 0 m [m/s] | 340.29400 | 340.29399 | 0.01 % | PASS |
| Thrust-curve impulse, midpoint quadrature vs piecewise-analytic [N s] | 115.75000 | 115.75000 | 0.01 % | PASS |
| Motor mass after burnout [g] | 55.00000 | 55.00000 | 1e-07 % | PASS |
| Burnout altitude, constant thrust & mass, no drag [m] | 79.42347 | 79.42355 | 0.1 % | PASS |
| Apogee, same case [m] | 401.36831 | 401.36848 | 0.1 % | PASS |
| Landing descent rate vs terminal velocity [m/s] | 5.08599 | 5.08631 | 0.5 % | PASS |
| Apogee time-step convergence (dt halved) | 328.23586 | 328.23588 | 0.1 % | PASS |
| Liftoff mass: simulation vehicle vs analysis.py [g] | 1,210.69950 | 1,210.69950 | 0.0001 % | PASS |
| Liftoff CG: simulation vehicle vs analysis.py [mm] | 696.42134 | 696.42134 | 0.0001 % | PASS |
| CP: independent Barrowman on CAD-measured geometry vs analysis.py [mm] | 870.31511 | 870.31511 | 0.05 | PASS |
| Build-up Cd at 50 m/s coasting within 0.35-0.75 (plausibility band for similar model rockets, ASSUMPTION) | 0.35-0.75 | 0.46371 | band | PASS |

## 7. Stability results

| Condition | Static margin cal |
|---|---|
| No motor | 3.23 |
| Liftoff | 2.63 |
| Rail exit | 2.67 |
| Min. powered | 2.63 |
| Burnout | 2.92 |

| Requirement | Value | Result |
|---|---|---|
| REQ-STAB-1 1.5 <= SM <= 3.0 cal at rail exit | 2.67 | PASS |
| REQ-STAB-2 SM >= 1.5 cal throughout powered flight | 2.63 | PASS |
| REQ-STAB-3 SM <= 3.0 cal at liftoff | 2.63 | PASS |

**Placeholder dependence:**

| Result | Dependence on propulsion data |
|---|---|
| apogee, velocity, acceleration, dynamic pressure, burnout state, coast time, rail-exit speed | DEPENDS ON PLACEHOLDER (thrust curve, motor mass) |
| static margin at liftoff / rail exit / burnout | DEPENDS ON PLACEHOLDER (motor mass and CG station) |
| descent rate, descent time | DEPENDS ON PLACEHOLDER (burnout mass) |
| burn-phase base drag | DEPENDS ON PLACEHOLDER (MMT_ID sets the exhaust-filled base area) |
| no-motor static margin, airframe mass and CG | motor excluded, but includes the PLACEHOLDER retainer mass (RET_MASS) and the MMT, retainer envelope and fin-tab depth sized from placeholder data |
| CP (Barrowman on CAD geometry) | independent of propulsion data |
| drag build-up coefficients (coast) | independent of propulsion data (ASSUMPTION model) |
| sensitivity deltas | trends are meaningful; absolute values DEPEND ON PLACEHOLDER |

Details: `simulation/results/stability_report.md`.

## 8. Sensitivity results

| Parameter (tested range) | Apogee swing % |
|---|---|
| Airframe mass (0.8…1.2 x) | 54.9 |
| Payload mass (0…300 g) | 31.1 |
| Drag coefficient (0.7…1.3 x) | 12.3 |
| Air density (0.9…1.1 x) | 4.0 |
| Site elevation (0…2000 m) | 3.7 |
| ISA temperature offset (-15…30 K) | 3.0 |
| Airframe CG shift (-30…30 mm) | 0.0 |

Details: `simulation/results/sensitivity_report.md`, `simulation/results/sensitivity_table.csv`.

## 9. Limitations

- 1-DOF: no wind, weathercocking, angle of attack, rail tip-off or drift. Apogee would be lower with a tilted rail or wind.
- Barrowman CP and the drag build-up are low-order methods, uncalibrated against wind-tunnel or flight data.
- Deployment is idealised at apogee. Opening shock, snatch loads and chute inflation time are not modelled here (see package §7.6 loads).
- **With the placeholder motor, trajectory values are not performance predictions.**

## 10. Items requiring real-world validation

- **T-03** Weigh every module and measure the CG with the actual motor installed. Update analysis.py and re-run.
- Drag coefficient: cross-check with OpenRocket and RASAero; after flight, compare with altimeter/IMU data.
- Parachute Cd and descent rate: drop test (package T-series), then flight data.
- Printed-part densities and fills: weigh the printed parts.
- Rail length, site elevation and expected temperature: use the actual range values.

## 11. Items requiring qualified mentor / range review

- Selection of a legally obtainable certified motor. Its published data go into `simulation/motor_config.json` (`status: MANUFACTURER_DATA`) together with its official `.eng` file, then the pipeline is re-run.
- Ejection-delay choice from the manufacturer's options, using the simulated coast time and the timing table above.
- Stability margin with the real motor and measured CG, and rail-exit velocity against the range's rules.
- Recovery hardware ratings, retainer installation, and the complete flight-readiness review (package §18).
- Confirmation that the flight envelope (apogee, field size, wind) fits the range's limits.

## Plots

- `simulation/plots/altitude_vs_time.svg`
- `simulation/plots/velocity_vs_time.svg`
- `simulation/plots/acceleration_vs_time.svg`
- `simulation/plots/thrust_input_vs_time.svg`
- `simulation/plots/vehicle_mass_vs_time.svg`
- `simulation/plots/static_margin_vs_time.svg`
- `simulation/plots/drag_coefficient_vs_mach.svg`
- `simulation/plots/apogee_vs_drag_scale.svg`
- `simulation/plots/apogee_vs_airframe_mass.svg`
- `simulation/plots/apogee_vs_payload_mass.svg`
- `simulation/plots/static_margin_vs_payload_mass.svg`
- `simulation/plots/static_margin_vs_cg_shift.svg`
- `simulation/plots/apogee_vs_site_elevation.svg`
- `simulation/plots/rail_exit_velocity_vs_rail_length.svg`
- `simulation/plots/tornado_apogee.svg`
- `simulation/plots/tornado_static_margin.svg`

