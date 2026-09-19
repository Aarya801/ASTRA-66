"""Optional quick check: render the parts selectable through the rev A `PART=` entry point (cad/astra66.scad).

Superseded for REV-B by `python cad/build_cad.py` (or `python run_validation.py --with-cad`), which renders and
validates the complete CAD. This helper renders from the project path directly, so it may fail if that path is
longer than 260 characters on Windows (OpenSCAD 2021); build_cad.py avoids this with a short work directory.
Requires OpenSCAD (https://openscad.org). Rendering can take several minutes per part.

Usage (from the project root):
    python tools/openscad_render_check.py                    # uses `openscad` on PATH
    python tools/openscad_render_check.py --openscad "C:/Program Files/OpenSCAD/openscad.exe"
Output STLs go to build/stl/ (git-ignored).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ["nose_tip", "nose_base", "nose_bulkhead", "camera_cradle", "lens_cowl", "hatch", "hatch_frame", "gps_tray",
         "sled", "bulkhead_fwd", "bulkhead_aft", "fwd_centering_ring", "fincan_core", "lock_ring", "fin", "rail_boss",
         "fin_jig"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--openscad", default=shutil.which("openscad"))
    ap.add_argument("--parts", nargs="*", default=PARTS)
    args = ap.parse_args()
    if not args.openscad:
        sys.exit("OpenSCAD not found. Install it or pass --openscad <path>.")
    out_dir = ROOT / "build" / "stl"
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = []
    for part in args.parts:
        out = out_dir / f"{part}.stl"
        cmd = [args.openscad, "-o", str(out), "-D", f'PART="{part}"', str(ROOT / "cad" / "astra66.scad")]
        print("rendering", part, flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = r.returncode == 0 and out.exists() and out.stat().st_size > 0
        print("  OK" if ok else f"  FAILED\n{r.stderr[-2000:]}")
        if not ok:
            failed.append(part)
    if failed:
        sys.exit(f"failed parts: {', '.join(failed)}")
    print("all parts rendered")


if __name__ == "__main__":
    main()
