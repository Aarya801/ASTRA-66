# analysis/

| Path | Kind | Content |
|---|---|---|
| `analysis.py` | **source** | Every design parameter (with provenance tag), stations, mass budget, Barrowman CP, static margin, fin trade study, recovery, structural loads, flutter screening, vibration estimate |
| `results/analysis.json` | generated | Summary results (masses, CG, CP, margins, loads, recovery, stations, motor-data status) |
| `results/mass_budget.csv` | generated | Item-level mass budget; CAD-derived items are noted `CAD:` |
| `results/parameters.csv` | generated | All parameters with value, unit, provenance and note |

`python analysis/analysis.py` prints a quick summary. `python build.py` (at the project root) regenerates the results and
the whole package.

Inputs that `analysis.py` reads:
- `simulation/motor_config.json`: external motor / retainer data (PLACEHOLDER until verified);
- `cad/exports/cad_mass_properties.json`: masses and CGs measured from the CAD by `cad/build_cad.py`.
