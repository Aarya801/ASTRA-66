> **PLACEHOLDER TEST INPUT.** `simulation/motor_config.json` has `status: PLACEHOLDER`. The thrust curve is the synthetic signal `simulation/motors/PLACEHOLDER_TEST_INPUT.eng`: it is not a real motor, a product or performance data. Trajectory numbers here verify the software and show sensitivities only. They are **not predictions** and must not be used for flight planning. The design is **not flight certified**; a qualified mentor or institution must review it before any flight.

# ASTRA-66 sensitivity report

One-at-a-time variation of **non-propulsion** parameters around the baseline. The motor input is held fixed (PLACEHOLDER-TEST, placeholder). Absolute values are illustrative while the placeholder is used; the relative changes show which assumptions matter.

Baseline: apogee 328.2 m, v_max 80.3 m/s, a_max 7.4 g, rail exit 11.7 m/s, SM rail exit 2.67 cal, descent 5.09 m/s.

## Airframe mass: `mass_scale` [x]

all non-motor mass scaled, CG unchanged

| x | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| 0.8 | 429.6 | 30.9 | 99.8 | 9.31 | 13.15 | 2.54 | 4.58 |
| 0.9 | 376.3 | 14.6 | 89.2 | 8.27 | 12.39 | 2.61 | 4.84 |
| 1.0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 1.1 | 286.0 | -12.9 | 72.8 | 6.73 | 11.16 | 2.72 | 5.32 |
| 1.2 | 249.3 | -24.0 | 66.3 | 6.13 | 10.65 | 2.76 | 5.55 |

## Payload mass: `payload_g` [g]

added at the payload-bay centre (STA 381)

| g | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| 0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 50 | 308.3 | -6.1 | 76.7 | 7.10 | 11.47 | 2.86 | 5.20 |
| 100 | 289.6 | -11.8 | 73.4 | 6.79 | 11.21 | 3.04 | 5.30 |
| 150 | 272.0 | -17.1 | 70.3 | 6.50 | 10.97 | 3.20 | 5.41 |
| 200 | 255.6 | -22.1 | 67.4 | 6.23 | 10.74 | 3.35 | 5.51 |
| 300 | 226.1 | -31.1 | 62.1 | 5.76 | 10.31 | 3.62 | 5.71 |

## Airframe CG shift: `cg_shift_mm` [mm]

+ = aft; trajectory unchanged in 1-DOF

| mm | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| -30 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 3.09 | 5.09 |
| -20 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.95 | 5.09 |
| -10 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.81 | 5.09 |
| 0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 10 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.53 | 5.09 |
| 20 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.40 | 5.09 |
| 30 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.26 | 5.09 |

## Drag coefficient: `cd_scale` [x]

multiplier on the build-up Cd

| x | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| 0.7 | 350.2 | 6.7 | 81.2 | 7.43 | 11.74 | 2.67 | 5.09 |
| 0.8 | 342.4 | 4.3 | 80.9 | 7.43 | 11.74 | 2.67 | 5.09 |
| 0.9 | 335.1 | 2.1 | 80.6 | 7.43 | 11.74 | 2.67 | 5.09 |
| 1.0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 1.1 | 321.7 | -2.0 | 80.0 | 7.43 | 11.74 | 2.67 | 5.09 |
| 1.2 | 315.5 | -3.9 | 79.7 | 7.43 | 11.73 | 2.67 | 5.09 |
| 1.3 | 309.7 | -5.7 | 79.5 | 7.43 | 11.73 | 2.67 | 5.09 |

## Air density: `density_scale` [x]

multiplier on ISA density

| x | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| 0.9 | 334.9 | 2.0 | 80.6 | 7.43 | 11.74 | 2.67 | 5.36 |
| 0.95 | 331.5 | 1.0 | 80.4 | 7.43 | 11.74 | 2.67 | 5.22 |
| 1.0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 1.05 | 325.0 | -1.0 | 80.2 | 7.43 | 11.74 | 2.67 | 4.96 |
| 1.1 | 321.9 | -1.9 | 80.0 | 7.43 | 11.74 | 2.67 | 4.85 |

## Site elevation: `site_elevation_m` [m]

ISA standard day

| m | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| 0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 500 | 331.4 | 1.0 | 80.4 | 7.43 | 11.74 | 2.67 | 5.21 |
| 1000 | 334.4 | 1.9 | 80.6 | 7.43 | 11.74 | 2.67 | 5.34 |
| 1500 | 337.5 | 2.8 | 80.7 | 7.43 | 11.74 | 2.67 | 5.47 |
| 2000 | 340.5 | 3.7 | 80.8 | 7.43 | 11.74 | 2.67 | 5.61 |

## ISA temperature offset: `temp_offset_K` [K]

sea-level site

| K | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| -15 | 324.7 | -1.1 | 80.1 | 7.43 | 11.74 | 2.67 | 4.95 |
| 0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 15 | 331.5 | 1.0 | 80.4 | 7.43 | 11.74 | 2.67 | 5.22 |
| 30 | 334.5 | 1.9 | 80.6 | 7.43 | 11.74 | 2.67 | 5.34 |

## Launch rail length: `rail_length_m` [m]

range equipment; affects rail-exit speed only

| m | apogee m | Δ apogee % | v_max m/s | a_max g | rail exit m/s | SM rail cal | descent m/s |
|---|---|---|---|---|---|---|---|
| 1.0 | 328.2 | 0.0 | 80.3 | 7.43 | 11.74 | 2.67 | 5.09 |
| 1.5 | 328.2 | 0.0 | 80.3 | 7.43 | 14.41 | 2.68 | 5.09 |
| 2.0 | 328.2 | 0.0 | 80.3 | 7.43 | 16.65 | 2.69 | 5.09 |
| 2.5 | 328.2 | 0.0 | 80.3 | 7.43 | 18.60 | 2.70 | 5.09 |
| 3.0 | 328.2 | 0.0 | 80.3 | 7.43 | 20.35 | 2.70 | 5.09 |

## Ranking (apogee swing over the tested range)

| Parameter | Tested range | Apogee swing % |
|---|---|---|
| Airframe mass | 0.8…1.2 x | 54.9 |
| Payload mass | 0…300 g | 31.1 |
| Drag coefficient | 0.7…1.3 x | 12.3 |
| Air density | 0.9…1.1 x | 4.0 |
| Site elevation | 0…2000 m | 3.7 |
| ISA temperature offset | -15…30 K | 3.0 |
| Airframe CG shift | -30…30 mm | 0.0 |

## Observations
- Largest apogee driver over the tested ranges: **Airframe mass** (55 %). Next: Payload mass (31 %).
- CG location and payload placement drive the static margin; drag and density do not (1-DOF, CP fixed).
- **Rail-exit speed** is 11.7 m/s on a 1.0 m rail and 20.4 m/s on a 3.0 m rail with the placeholder input, against the 15 m/s guideline. The rail offered by the range, and the certified motor's early thrust, must be checked together (mentor/RSO).
- Descent rate depends on burnout mass and air density only (parachute Cd·A fixed).
- The drag build-up is the least verified input. Cross-check it with OpenRocket/RASAero and, after flight, with altimeter data.

Plots: `simulation/plots/altitude_vs_time.svg`, `simulation/plots/velocity_vs_time.svg`, `simulation/plots/acceleration_vs_time.svg`, `simulation/plots/thrust_input_vs_time.svg`, `simulation/plots/vehicle_mass_vs_time.svg`, `simulation/plots/static_margin_vs_time.svg`, `simulation/plots/drag_coefficient_vs_mach.svg`, `simulation/plots/apogee_vs_drag_scale.svg`, `simulation/plots/apogee_vs_airframe_mass.svg`, `simulation/plots/apogee_vs_payload_mass.svg`, `simulation/plots/static_margin_vs_payload_mass.svg`, `simulation/plots/static_margin_vs_cg_shift.svg`, `simulation/plots/apogee_vs_site_elevation.svg`, `simulation/plots/rail_exit_velocity_vs_rail_length.svg`, `simulation/plots/tornado_apogee.svg`, `simulation/plots/tornado_static_margin.svg`

