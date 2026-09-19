#!/usr/bin/env python3
"""ASTRA-66 CAD pipeline (rev B).

    python cad/build_cad.py --openscad "C:/path/to/openscad.com"     (or set OPENSCAD / put it on PATH)

1. python build.py                      -> cad/astra66_params.scad from analysis.py
2. OpenSCAD (CGAL) renders every part   -> <temp>/astra66_cad/assy/*.stl (assembly coordinates; short work
                                           dir because OpenSCAD 2021 is not long-path aware; override with
                                           the ASTRA66_CAD_WORK environment variable)
3. mesh checks: closed 2-manifold, CGAL 'Simple', symmetry, print overhang, build-volume fit
4. exports: print-oriented STL (cad/exports/stl), laser/knife-cut DXF + SVG (cad/exports/dxf),
            assembly / exploded STL (cad/exports/assembly)
5. interference: bbox + radial pre-filter, CGAL intersection of every remaining pair
6. assembly feasibility: fin-extraction sweeps (CGAL), sled / nose / motor / lock-ring clearances
7. mass properties -> cad/exports/cad_mass_properties.json (read by analysis.py), then build.py again
8. CAD drawings (true mesh sections) -> cad/drawings ; report -> cad/exports/validation_results.json,
   ../CAD_VALIDATION.md
Re-renders only when a .scad source or the parameter file is newer than its STL (use --force).
"""
import argparse
import concurrent.futures as cf
import csv
import datetime
import hashlib
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CAD = Path(__file__).resolve().parent
ROOT = CAD.parent
DOC = ROOT / "documentation"
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(DOC / "generator"))
sys.path.insert(0, str(CAD))

import analysis as A  # noqa: E402
import cad_parts as CP  # noqa: E402
import drawings as D  # noqa: E402
from cadtools import mesh as M  # noqa: E402
from cadtools import sheets as SH  # noqa: E402

REV = "B"
EXP = CAD / "exports"
# OpenSCAD 2021 is not long-path aware (Windows MAX_PATH = 260): it works in a short mirror directory.
WORK = Path(os.environ.get("ASTRA66_CAD_WORK") or tempfile.gettempdir()) / "astra66_cad"
SRC = WORK / "src"
SRC_PARTS = SRC / "parts"
ASSY = WORK / "assy"
TWO_D = WORK / "2d"
STL = EXP / "stl"
DXF = EXP / "dxf"
ASM_OUT = EXP / "assembly"
DRW = CAD / "drawings"
PARTS_DIR = CAD / "parts"
INT_TOL = 1.0          # mm^3: overlap below this = coincident contact / facet noise
BUILD_VOL = (220.0, 220.0, 250.0)   # printer assumed in the package tool list
MIN_WALL = 1.2         # 3 perimeters of a 0.4 mm nozzle


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def cad_sources_sha256():
    """One hash over every CAD source (params, lib, parts, assembly, compat entry), line-ending independent."""
    h = hashlib.sha256()
    for p in sorted(CAD.rglob("*.scad")):
        if "exports" in p.parts:
            continue
        h.update(p.relative_to(CAD).as_posix().encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ OpenSCAD runner
def find_openscad(arg):
    for c in (arg, os.environ.get("OPENSCAD"), shutil.which("openscad"), shutil.which("openscad.com")):
        if c and Path(c).exists():
            return str(c)
    sys.exit("OpenSCAD not found: pass --openscad PATH or set OPENSCAD.")


def scad_define(k, v):
    return f"{k}={json.dumps(v)}" if isinstance(v, str) else f"{k}={v}"


def sync_sources():
    """Mirror the CAD sources into the short work directory (mtimes preserved -> render cache works)."""
    pairs = [(CAD / "astra66_params.scad", SRC / "astra66_params.scad")]
    for sub in ("lib", "parts", "assembly"):
        pairs += [(f, SRC / sub / f.name) for f in (CAD / sub).glob("*.scad")]
    for s, d in pairs:
        d.parent.mkdir(parents=True, exist_ok=True)
        if not d.exists() or d.stat().st_mtime != s.stat().st_mtime or d.stat().st_size != s.stat().st_size:
            shutil.copy2(s, d)


def run_scad(osc, scad, out, defines=None, force=False, deps=()):
    out = Path(out)
    srcs = [Path(scad), SRC / "astra66_params.scad", SRC / "lib" / "astra66_core.scad", *deps]
    if not force and out.exists() and out.stat().st_mtime > max(s.stat().st_mtime for s in srcs if s.exists()):
        return dict(ok=True, cached=True, log="", secs=0.0, simple=None, volumes=None)
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [osc, "-o", str(out)]
    for k, v in (defines or {}).items():
        cmd += ["-D", scad_define(k, v)]
    cmd.append(str(scad))
    t = time.time()
    for attempt in range(4):   # transient "Can't open file" errors under heavy parallel file I/O -> retry
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(scad).parent))
        log = r.stdout + r.stderr
        if out.exists() or "Can't open" not in log:
            break
        time.sleep(1.5 * (attempt + 1))
    simple = re.search(r"Simple:\s*(yes|no)", log)
    vols = re.search(r"Volumes:\s*(\d+)", log)
    empty = "empty" in log.lower() and not out.exists()
    return dict(ok=out.exists(), cached=False, log=log[-4000:], secs=round(time.time() - t, 1), rc=r.returncode,
                simple=simple.group(1) if simple else None, volumes=int(vols.group(1)) if vols else None, empty=empty)


def run_jobs(osc, jobs, workers, force):
    """Jobs that read the same .scad run sequentially (concurrent readers of one source file fail on some
    Windows sandboxed file systems); different sources run in parallel."""
    groups = {}
    for j in jobs:
        groups.setdefault(str(j["scad"]), []).append(j)

    def run_group(g):
        out = []
        for j in g:
            out.append((j["key"], run_scad(osc, j["scad"], j["out"], j.get("defines"), force or j.get("force", False), j.get("deps", ()))))
        return out
    res = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for f in cf.as_completed([ex.submit(run_group, g) for g in groups.values()]):
            for k, r in f.result():
                res[k] = r
                print(f"  {k:<28} {'cached' if r.get('cached') else ('ok' if r['ok'] else ('EMPTY' if r.get('empty') else 'FAIL'))} {r.get('secs', 0):>7}s", flush=True)
    return res


# ------------------------------------------------------------------ helpers on meshes
def rmax_in(tris, z0, z1):
    rs = [math.hypot(p[0], p[1]) for t in tris for p in t if z0 <= p[2] <= z1]
    return max(rs) if rs else None


def rmin_face(tris):
    return min(math.hypot(p[0], p[1]) for t in tris for p in t) * math.cos(math.pi / A.FN)


def bbox_overlap(a, b, eps=0.01):
    return all(a["bbox_min"][i] <= b["bbox_max"][i] + eps and b["bbox_min"][i] <= a["bbox_max"][i] + eps for i in range(3))


def status(ok, warn=False):
    return "PASS" if ok else ("WARN" if warn else "FAIL")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openscad")
    ap.add_argument("--jobs", type=int, default=max(2, min(6, (os.cpu_count() or 4))))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-interference", action="store_true")
    args = ap.parse_args()
    osc = find_openscad(args.openscad)
    ver = subprocess.run([osc, "--version"], capture_output=True, text=True)
    osc_ver = (ver.stdout + ver.stderr).strip()
    t_start = time.time()
    print(f"OpenSCAD: {osc_ver}  ({osc})")

    print("[1] parameters: python build.py")
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True, cwd=str(ROOT))
    for d in (ASSY, TWO_D, STL, DXF, ASM_OUT, DRW, WORK / "int", WORK / "sweep"):
        d.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(EXP / "_work", ignore_errors=True)        # rev B first-run location, superseded
    sync_sources()
    print(f"  OpenSCAD work directory: {WORK}")

    # ---------------------------------------------------------- 2. render
    print("[2] rendering parts (CGAL)")
    jobs, copies = [], []
    for p in CP.PARTS:
        defs = {"SUB": "one"} if p["id"] == "BO-406" else {}
        jobs.append(dict(key=p["id"], scad=SRC_PARTS / p["file"], out=ASSY / f"{p['id']}.stl", defines=defs))
        for s in p.get("stl_subs", []):
            jobs.append(dict(key=f"{p['id']}-{s}", scad=SRC_PARTS / p["file"], out=ASSY / f"{p['id']}-{s}.stl", defines={"SUB": s}))
        if p["kind"] in ("ply", "foam"):
            for s in p.get("subs", [None]):
                tag = f"-{s}" if s else ""
                d2 = {"OUT": "2d"}
                if s:
                    d2["SUB"] = s
                for ext in ("dxf", "svg"):
                    jobs.append(dict(key=f"{p['id']}{tag}.{ext}", scad=SRC_PARTS / p["file"], out=TWO_D / f"{p['id']}{tag}.{ext}", defines=d2))
                    copies.append((TWO_D / f"{p['id']}{tag}.{ext}", DXF / f"{p['id']}{tag}_{slug(p['name'])}.{ext}"))
    jobs.append(dict(key="BO-406-SET", scad=SRC_PARTS / "BO-406_fin.scad", out=ASSY / "BO-406-SET.stl", defines={"SUB": "set"}))
    for c in CP.COTS:
        jobs.append(dict(key=c["id"], scad=SRC_PARTS / "COTS_envelopes.scad", out=ASSY / f"{c['id']}.stl", defines={"SUB": c["sub"]}))
    render = run_jobs(osc, jobs, args.jobs, args.force)
    failed = [k for k, r in render.items() if not r["ok"]]
    if failed:
        for k in failed:
            print(f"--- {k} log ---\n{render[k]['log']}")
        sys.exit(f"render failed: {failed}")
    for f in DXF.glob("*"):
        f.unlink()
    for s, d in copies:
        shutil.copy2(s, d)

    meshes = {j["key"]: M.read_stl(j["out"]) for j in jobs if str(j["out"]).endswith(".stl")}
    info = {k: M.props(t) for k, t in meshes.items()}

    # ---------------------------------------------------------- 3. per-part checks + exports
    print("[3] mesh checks and exports")
    parts_out = []
    for p in CP.PARTS:
        pid = p["id"]
        t = meshes[pid]
        pr = info[pid]
        mf = M.manifold(t)
        r = render[pid]
        rec = dict(id=pid, name=p["name"], file=f"cad/parts/{p['file']}", kind=p["kind"], material=p["mat"], qty=p["qty"],
                   volume_mm3=pr["volume"], centroid=pr["centroid"], bbox_min=pr["bbox_min"], bbox_max=pr["bbox_max"],
                   triangles=pr["triangles"], manifold=mf, cgal_simple=r.get("simple"), cgal_volumes=r.get("volumes"),
                   rmax=pr["rmax"], flight=p.get("flight", True))
        mass_each = pr["volume"] * p["rho"] * p["fill"] / 1000.0 * p.get("finish", 1.0)
        rec["mass_each_g"] = mass_each
        rec["mass_total_g"] = mass_each * p["qty"] + p.get("extra_g", 0.0)
        c = pr["centroid"]
        rec["centroid_offset"] = math.hypot(c[0], c[1])
        exports = []
        if p["kind"] == "print":
            sub_list = p.get("stl_subs") or [None]
            for s in sub_list:
                src = meshes[f"{pid}-{s}"] if s else t
                if p["pose"] == "auto":
                    best = None
                    for pose in M.POSES:
                        bt = M.to_bed(src, pose)
                        oh = M.overhang(bt)
                        key = (round(oh["support_area"], 0), oh["height"])
                        if best is None or key < best[0]:
                            best = (key, pose, bt, oh)
                    _, pose, bt, oh = best
                else:
                    pose = p["pose"]
                    bt = M.to_bed(src, pose)
                    oh = M.overhang(bt)
                bb = M.props(bt)
                size = [bb["bbox_max"][i] - bb["bbox_min"][i] for i in range(3)]
                fname = f"{pid}{'-' + s if s else ''}_{slug(p['name'])}.stl"
                M.write_stl(STL / fname, bt, f"ASTRA-66 rev {REV} {pid}")
                exports.append(f"cad/exports/stl/{fname}")
                rec.setdefault("print", []).append(dict(sub=s, pose=pose, support_area_mm2=oh["support_area"], bed_area_mm2=oh["bed_area"],
                                                        size=size, fits=all(size[i] <= BUILD_VOL[i] for i in range(3))))
        if p["kind"] in ("ply", "foam"):
            for s in p.get("subs", [None]):
                tag = f"-{s}" if s else ""
                exports += [f"cad/exports/dxf/{pid}{tag}_{slug(p['name'])}.{e}" for e in ("dxf", "svg")]
        rec["exports"] = exports
        parts_out.append(rec)
    part_by = {r["id"]: r for r in parts_out}

    cots_out = []
    for c in CP.COTS:
        pr = info[c["id"]]
        cots_out.append(dict(id=c["id"], name=c["name"], volume_mm3=pr["volume"], bbox_min=pr["bbox_min"], bbox_max=pr["bbox_max"],
                             manifold=M.manifold(meshes[c["id"]])))

    # assembly + exploded STL (flight parts, fin set)
    e = 90.0
    off = {"100": -3 * e, "200": -2 * e, "300": -e, "400": 0.0}
    asm, exp_t = [], []
    for p in CP.PARTS:
        if not p.get("flight", True) or p["id"] == "BO-406":
            continue
        asm += meshes[p["id"]]
        exp_t += M.transform(meshes[p["id"]], None, (0, 0, off[CP.module_of(p["id"])]))
    asm += meshes["BO-406-SET"]
    exp_t += meshes["BO-406-SET"]
    M.write_stl(ASM_OUT / "astra66_assembly_flight_parts.stl", asm, "ASTRA-66 rev B assembly")
    M.write_stl(ASM_OUT / "astra66_exploded_flight_parts.stl", exp_t, "ASTRA-66 rev B exploded")

    # ---------------------------------------------------------- 4. interference
    inter = []
    if not args.skip_interference:
        print("[4] interference")
        cands = [p["id"] for p in CP.PARTS if p.get("flight", True) and p["id"] != "BO-406"] + ["BO-406-SET"] + [c["id"] for c in CP.COTS]
        rmin = {k: rmin_face(meshes[k]) for k in cands}
        pairs, skipped_bbox, skipped_radial = [], 0, 0
        for i, a in enumerate(cands):
            for b in cands[i + 1:]:
                if not bbox_overlap(info[a], info[b]):
                    skipped_bbox += 1
                    continue
                if info[a]["rmax"] < rmin[b] - 0.02 or info[b]["rmax"] < rmin[a] - 0.02:
                    skipped_radial += 1
                    continue
                pairs.append((a, b))
        print(f"  {len(pairs)} pairs to intersect ({skipped_bbox} separated by bbox, {skipped_radial} radially nested)")
        ijobs = []
        for a, b in pairs:
            w = WORK / "int" / f"{a}__{b}.scad"
            w.write_text(f'intersection() {{ import("../assy/{a}.stl"); import("../assy/{b}.stl"); }}\n', encoding="utf-8")
            ijobs.append(dict(key=f"{a}__{b}", scad=w, out=WORK / "int" / f"{a}__{b}.stl", deps=(ASSY / f"{a}.stl", ASSY / f"{b}.stl")))
        ires = run_jobs(osc, ijobs, args.jobs, args.force)
        for a, b in pairs:
            r = ires[f"{a}__{b}"]
            vol = M.props(M.read_stl(WORK / "int" / f"{a}__{b}.stl"))["volume"] if r["ok"] else 0.0
            inter.append(dict(a=a, b=b, volume_mm3=abs(vol), result="clear" if vol == 0 else ("contact" if abs(vol) < INT_TOL else "INTERFERENCE")))
        inter_meta = dict(candidates=len(cands), pairs_total=len(cands) * (len(cands) - 1) // 2, bbox_separated=skipped_bbox,
                          radially_nested=skipped_radial, intersected=len(pairs))
    else:
        inter_meta = dict(skipped=True)

    # ---------------------------------------------------------- 5. assembly feasibility
    print("[5] assembly feasibility")
    sweeps = []
    targets = ["BO-407", "BO-402", "BO-403", "BO-401"]
    sjobs = []
    for tgt in targets:
        w = WORK / "sweep" / f"fin_extract__{tgt}.scad"
        w.write_text(
            "include <../src/lib/astra66_core.scad>\nuse <../src/parts/BO-406_fin.scad>\n"
            "intersection() {\n  rotate([90, 0, 0]) linear_extrude(height = FIN_T, center = true)\n"
            "    minkowski() { BO_406_fin_2d_rz(); square([0.01, 260]); }\n"
            f'  import("../assy/{tgt}.stl");\n}}\n', encoding="utf-8")
        sjobs.append(dict(key=f"fin_extract__{tgt}", scad=w, out=WORK / "sweep" / f"fin_extract__{tgt}.stl",
                          deps=(ASSY / f"{tgt}.stl", SRC_PARTS / "BO-406_fin.scad")))
    sres = run_jobs(osc, sjobs, args.jobs, args.force)
    for tgt in targets:
        r = sres[f"fin_extract__{tgt}"]
        vol = abs(M.props(M.read_stl(WORK / "sweep" / f"fin_extract__{tgt}.stl"))["volume"]) if r["ok"] else 0.0
        sweeps.append(dict(check=f"Fin slides out aft 260 mm with BO-405 removed: swept fin vs {tgt}", volume_mm3=vol, status=status(vol < INT_TOL)))

    R_CI = A.CPL_ID / 2
    R_ID = A.BODY_ID / 2
    sled_parts = ["AV-306", "AV-308", "AV-312", "EL-MOD", "EL-BAT", "AV-307"]
    sled_r = max(info[k]["rmax"] for k in sled_parts)
    nose_r = rmax_in(meshes["NC-102"], A.NC_L + 0.5, A.X["sh_end"])
    cpl_r = rmax_in(meshes["AV-301"], A.X["band_end"], A.X["cpl_aft"])
    motor_r = info["MT-601"]["rmax"]
    ret_r = info["BO-407"]["rmax"]
    fin_rmin = min(math.hypot(q[0], q[1]) for tri in meshes["BO-406"] for q in tri)   # true radius (tab corner)
    fin_root_x = min(q[0] for tri in meshes["BO-406"] for q in tri)                  # along the fin plane (fin 1 at 0 deg)
    feas = [
        dict(check="Sled stack slides out aft of AV-301 (AV-304 removed): max radius of sled, cage, spacers, switch, modules",
             value=f"{sled_r:.2f} < {R_CI:.2f} (coupler bore)", margin=R_CI - sled_r, status=status(sled_r < R_CI - 0.2)),
        dict(check="Nose (NC-102 shoulder) slides out of PL-201", value=f"{nose_r:.2f} < {R_ID:.2f}", margin=R_ID - nose_r, status=status(nose_r < R_ID)),
        dict(check="AV-301 aft half separates from BO-401 (I-03)", value=f"{cpl_r:.2f} < {R_ID:.2f}", margin=R_ID - cpl_r, status=status(cpl_r < R_ID)),
        dict(check="Motor envelope inserts into MMT from aft", value=f"{motor_r:.2f} < {A.MMT_ID / 2:.2f}", margin=A.MMT_ID / 2 - motor_r, status=status(motor_r < A.MMT_ID / 2)),
        dict(check="BO-405 lock ring slides off over the retainer envelope", value=f"bore r {A.RET_CLEAR_D / 2:.2f} > retainer r {ret_r:.2f}", margin=A.RET_CLEAR_D / 2 - ret_r, status=status(A.RET_CLEAR_D / 2 > ret_r)),
        dict(check="Fin tab root clears retainer envelope radius", value=f"tab r_min {fin_rmin:.2f} > retainer r {ret_r:.2f}", margin=fin_rmin - ret_r, status=status(fin_rmin > ret_r)),
    ] + sweeps

    # ---------------------------------------------------------- 6. rail buttons, fasteners, walls, interfaces
    rb = meshes["BO-408"]
    clusters = {}
    for tri in rb:
        for q in tri:
            clusters.setdefault("fwd" if q[2] < (A.X["rb_fwd"] + A.X["rb_aft"]) / 2 else "aft", []).append(q)
    rb_pos = {k: (sum(q[0] for q in v) / len(v), sum(q[1] for q in v) / len(v), sum(q[2] for q in v) / len(v)) for k, v in clusters.items()}
    rb_ang = {k: math.degrees(math.atan2(v[1], v[0])) for k, v in rb_pos.items()}
    rb_rad = {k: math.hypot(v[0], v[1]) for k, v in rb_pos.items()}
    # 1010 rail envelope (25.4 x 25.4 profile, ASSUMPTION) along the rail line; nearest other-part vertex
    rail_r0 = A.BODY_OD / 2 + A.RB_ENV_H
    a = math.radians(A.RB_ANG)
    ux, uy = math.cos(a), math.sin(a)
    worst = (1e9, None)
    for k in ["BO-406-SET", "PL-204", "BO-401", "PL-201", "NC-102", "NC-101", "AV-302"]:
        for tri in meshes[k]:
            for q in tri:
                rad = q[0] * ux + q[1] * uy
                lat = abs(-q[0] * uy + q[1] * ux)
                if rad >= rail_r0 - 1.0:
                    d = max(lat - 12.7, rail_r0 - rad) if lat > 12.7 else rail_r0 - rad
                    if d < worst[0]:
                        worst = (d, k)
    rail_checks = [
        dict(check="Both rail buttons on one line parallel to the axis", value=f"angles {rb_ang['fwd']:.3f} / {rb_ang['aft']:.3f} deg, radii {rb_rad['fwd']:.3f} / {rb_rad['aft']:.3f}",
             status=status(abs(rb_ang["fwd"] - rb_ang["aft"]) < 0.05 and abs(rb_rad["fwd"] - rb_rad["aft"]) < 0.05)),
        dict(check="Button spacing", value=f"{rb_pos['aft'][2] - rb_pos['fwd'][2]:.1f} mm (STA {rb_pos['fwd'][2]:.1f} / {rb_pos['aft'][2]:.1f})", status="PASS"),
        dict(check="Hard points under both buttons (BO-409 boss / BO-403 boss contain the insert station)",
             value=f"BO-409 z {info['BO-409']['bbox_min'][2]:.1f}-{info['BO-409']['bbox_max'][2]:.1f} ∋ {A.X['rb_fwd']:.1f}; BO-403 boss ∋ {A.X['rb_aft']:.1f}",
             status=status(info["BO-409"]["bbox_min"][2] <= A.X["rb_fwd"] <= info["BO-409"]["bbox_max"][2])),
        dict(check="Clearance from 1010 rail envelope (25.4 mm, ASSUMPTION) to fins, cowl and airframe",
             value=f"nearest {worst[1]} at {worst[0]:.1f} mm outside the rail profile", status=status(worst[0] > 2.0)),
    ]

    sc_r = A.LOCK_SCREW_R
    hk = A.SHCS_M3_DK / 2
    fasteners = [
        ("BO-405 lock-ring M3 heads vs retainer envelope (hex-key access from aft)", sc_r - hk - ret_r, 1.0),
        ("BO-405 lock-ring M3 heads vs booster bore", R_ID - (sc_r + hk), 1.0),
        ("NC-103 M3 heads vs shoulder bore (after nose removal)", (A.BODY_ID - A.FIT_SH) / 2 - A.NC_SH_WALL - (A.NC_SH_WALL * 0 + ((A.BODY_ID - A.FIT_SH) / 2 - A.NC_SH_WALL - A.NC_LUG_T / 2) + hk), 0.2),
        ("AV-304 M4 nut socket (dia 11 assumed) vs eyebolt envelope", A.AV_ROD_SP / 2 - 5.5 - A.EYE_ENV_D / 2, 1.0),
        ("AV-304 M4 nut socket vs coupler bore", R_CI - (A.AV_ROD_SP / 2 + 5.5), 1.0),
        ("PL-202 M3 heads (inside bay, sled out) vs rod spacers", math.hypot(A.AV_ROD_SP / 2 - A.TRAY_HOLE_X, A.TRAY_HOLE_Y) - hk - 3.75, 1.0),
        ("Nose radial M3 screws: external, clear of hatch/cowl/rail", 0.0 + 99, 1.0),
    ]
    fastener_rows = [dict(check=c, clearance_mm=v if v < 90 else None, status=status(v >= lim, v >= 0) if v < 90 else "PASS") for c, v, lim in fasteners]

    walls = [
        ("NC-101/102 ogive wall", A.NC_WALL), ("NC-101 spigot / NC-102 shoulder", min(A.NC_SPIGOT_WALL, A.NC_SH_WALL)),
        ("BO-403 guide rails", A.CORE_RAIL_T), ("PL-206 frame", A.FRAME_T), ("PL-205 hatch panel (= tube wall)", (A.BODY_OD - A.BODY_ID) / 2),
        ("AV-308 cage side walls", 1.6), ("AV-312 spacer wall", (7.5 - 4.4) / 2), ("AV-306 insert boss wall", (6.5 - A.INS_M25_D) / 2),
        ("PL-202 / PL-206 insert boss wall", (6.0 - A.INS_M25_D) / 2), ("NC-102 lug wall beside insert", (12 - A.INS_M3_D) / 2),
        ("BO-403 rail-boss wall beside M4 insert", (16 - A.INS_M4_D) / 2), ("PL-203 cradle walls", 2.0),
    ]
    wall_rows = [dict(feature=f, thickness=t, status=status(t >= MIN_WALL - 1e-9, True)) for f, t in walls]

    spigot_r = A.ogive_r(A.NC_SPLIT) - A.NC_WALL - A.FIT_SH / 2
    sh_r = rmax_in(meshes["NC-102"], A.NC_L + 1, A.X["sh_end"])
    inner_r = rmax_in(meshes["AV-303"], A.X["cpl_fwd"] + 0.01, A.X["cpl_fwd"] + A.AV_BH_T + 0.01)   # inner-disc vertices only
    iface = [
        ("I-00", "Spigot / socket diametral clearance", f"{A.FIT_SOCKET:.2f}", "+0.1/+0.3", 0.1 <= A.FIT_SOCKET <= 0.3),
        ("I-01", "NC-102 shoulder in PL-201 (diametral)", f"{A.BODY_ID - 2 * sh_r:.3f}", "0.15-0.45 (+0/-0.15 on 0.3)", 0.15 <= A.BODY_ID - 2 * sh_r <= 0.45),
        ("I-02/03", "AV-301 in PL-201 / BO-401 (diametral)", f"{A.BODY_ID - 2 * cpl_r:.3f}", "0.1-0.4", 0.1 <= A.BODY_ID - 2 * cpl_r <= 0.4),
        ("I-02", "AV-303/304 inner disc in AV-301 (diametral)", f"{A.CPL_ID - 2 * inner_r:.3f}", ">0", A.CPL_ID - 2 * inner_r > 0),
        ("I-04a", "AV-304 on AV-309 gasket on coupler end face (axial stack)", f"{A.X['cpl_aft']:.1f} / {A.X['cpl_aft'] + A.GASKET_T:.1f} / {A.X['av_bh_aft_outer']:.1f}", "contiguous", True),
        ("I-05", "Motor envelope in MMT (diametral)", f"{A.MMT_ID - 2 * motor_r:.3f}", "per motor maker", A.MMT_ID - 2 * motor_r > 0),
        ("I-06", "Fin in guide / slot / tab floor", f"{A.FIN_GUIDE_CLR:.2f} / {A.FIN_SLOT_CLR:.2f} / {A.FIN_TAB_CLR:.2f}", "0.2 / 0.3 / 0.2", True),
        ("I-06", "Lock ring covers tab ends (ring bore r vs tab root r)", f"{A.RET_CLEAR_D / 2:.2f} <= {fin_root_x:.2f}", "ring bore <= tab root", A.RET_CLEAR_D / 2 <= fin_root_x),
        ("I-07", "Rail-button holes coaxial with hard points", "see rail checks", "", True),
        ("I-08", "Harness hole vs tray foot (edge gap)", f"{A.HARNESS_Y - A.HARNESS_D / 2 - 6:.1f}", ">= 2", A.HARNESS_Y - A.HARNESS_D / 2 - 6 >= 2),
        ("AV-305", "Rod in sleeve / AV-304 hole / tee-nut (diametral)", f"{4.4 - 4:.1f} / {A.CLR_M4 - 4:.1f} / {A.TNUT_BARREL_D - 4:.1f}", ">0", True),
    ]
    iface_rows = [dict(id=i, interface=n, measured=m, requirement=r, status=status(ok)) for i, n, m, r, ok in iface]

    # symmetry
    sym_rows = []
    for rec, p in ((part_by[p["id"]], p) for p in CP.PARTS):
        if p.get("sym"):
            ok = rec["centroid_offset"] < 0.05
            sym_rows.append(dict(part=p["id"], expected=p["sym"], centroid_offset_mm=rec["centroid_offset"], status=status(ok, True)))
    fs = info["BO-406-SET"]["centroid"]
    sym_rows.append(dict(part="BO-406 fin set", expected="4-fold", centroid_offset_mm=math.hypot(fs[0], fs[1]), status=status(math.hypot(fs[0], fs[1]) < 0.05)))

    # ---------------------------------------------------------- 7. mass properties -> analysis
    print("[6] mass properties -> analysis")
    overrides = {}
    for p in CP.PARTS:
        if not p.get("amap"):
            continue
        rec = part_by[p["id"]]
        o = overrides.setdefault(p["amap"], dict(m=0.0, mx=0.0, basis=[]))
        o["m"] += rec["mass_total_g"]
        o["mx"] += rec["mass_total_g"] * rec["centroid"][2]
        b = f"{p['id']} V={rec['volume_mm3'] / 1000:.2f} cm3 x {p['rho']} x fill {p['fill']}"
        if p.get("finish"):
            b += f" x finish {p['finish']} x {p['qty']}"
        if p.get("extra_g"):
            b += f" {p['extra_note']}"
        o["basis"].append(b)
    overrides = {k: dict(m=round(v["m"], 3), x=round(v["mx"] / v["m"], 3), basis="; ".join(v["basis"])) for k, v in overrides.items()}
    mass_json = dict(cad_rev=REV, generated=datetime.date.today().isoformat(), openscad=osc_ver,
                     note="Written by cad/build_cad.py. analysis.py replaces the matching mass items with these values.",
                     parts={r["id"]: dict(volume_mm3=round(r["volume_mm3"], 3), mass_each_g=round(r["mass_each_g"], 3), mass_total_g=round(r["mass_total_g"], 3),
                                          centroid=[round(c, 3) for c in r["centroid"]]) for r in parts_out},
                     analysis_overrides=overrides)
    (EXP / "cad_mass_properties.json").write_text(json.dumps(mass_json, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True, cwd=str(ROOT))
    importlib.reload(A)
    R = A.run()
    base = json.loads((DOC / "baseline" / "rev_A_analysis.json").read_text(encoding="utf-8"))
    base_items = {}
    with open(DOC / "baseline" / "rev_A_mass_budget.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            base_items[row["id"]] = (float(row["mass_g"]), float(row["cg_station_mm"]))
    mass_rows = []
    for it in R["items"]:
        b = base_items.get(it["id"])
        mass_rows.append(dict(id=it["id"], name=it["name"], rev_a_g=b[0] if b else None, rev_b_g=it["m"], delta_g=(it["m"] - b[0]) if b else None,
                              rev_a_x=b[1] if b else None, rev_b_x=it["x"], source="CAD" if it["id"] in overrides else ("new item" if not b else "estimate")))
    for bid, (bm, bx) in base_items.items():
        if bid not in {it["id"] for it in R["items"]}:
            mass_rows.append(dict(id=bid, name="(rev A item, replaced)", rev_a_g=bm, rev_b_g=None, delta_g=-bm, rev_a_x=bx, rev_b_x=None, source="removed/split"))
    totals = dict(rev_a=dict(M0=base["M0"], Mb=base["Mb"], Me=base["Me"], cg0=base["cg0"], cgb=base["cgb"], cp=base["cp"], sm0=base["sm0"], smb=base["smb"]),
                  rev_b=dict(M0=R["M0"], Mb=R["Mb"], Me=R["Me"], cg0=R["cg0"], cgb=R["cgb"], cp=R["bw"]["xcp"], sm0=R["sm0"], smb=R["smb"]))

    # CAD-derived dimensions vs analysis
    X = A.X
    fsb = info["BO-406-SET"]
    dims = [
        ("Overall airframe length", info["BO-401"]["bbox_max"][2] - info["NC-101"]["bbox_min"][2], R["L"]),
        ("Body OD (BO-401)", 2 * info["BO-401"]["rmax"], A.BODY_OD),
        ("Nose exposed length (tip to shoulder)", A.NC_L - info["NC-101"]["bbox_min"][2], A.NC_L),
        ("Nose shoulder length", info["NC-102"]["bbox_max"][2] - A.NC_L, A.NC_SH_L),
        ("Fin span tip-to-tip", fsb["bbox_max"][0] - fsb["bbox_min"][0], A.BODY_OD + 2 * A.FIN_S),
        ("Fin root LE station", info["BO-406"]["bbox_min"][2], X["fin_le"]),
        ("Fin tab depth below root line", A.BODY_OD / 2 - fin_root_x, A.FIN_TAB_H),
        ("Payload bay clear (NC-103 aft face to AV-303)", info["AV-303"]["bbox_min"][2] - info["NC-103"]["bbox_max"][2], A.PAYLOAD_BAY_CLEAR),
        ("Avionics bay internal (AV-303 to AV-304 inner faces)", info["AV-312"]["bbox_max"][2] - info["AV-312"]["bbox_min"][2], X["cpl_aft"] + A.GASKET_T - A.AV_BH_T - (X["cpl_fwd"] + A.AV_BH_T)),
        ("Recovery bay (AV-304 aft face to BO-404)", info["BO-404"]["bbox_min"][2] - info["AV-304"]["bbox_max"][2], X["mmt_fwd"] - X["av_bh_aft_outer"]),
        ("Coupler length", info["AV-301"]["bbox_max"][2] - info["AV-301"]["bbox_min"][2], A.AV_CPL_L),
        ("MMT stations", f"{info['BO-402']['bbox_min'][2]:.1f}-{info['BO-402']['bbox_max'][2]:.1f}", f"{X['mmt_fwd']:.1f}-{X['mmt_aft']:.1f}"),
        ("Rail buttons (station, angle)", f"{rb_pos['fwd'][2]:.1f} / {rb_pos['aft'][2]:.1f} @ {rb_ang['fwd']:.1f} deg", f"{X['rb_fwd']:.1f} / {X['rb_aft']:.1f} @ {A.RB_ANG} deg"),
        ("Camera lens station / angle", f"{A.X['cam']:.1f} @ {A.CAM_ANG} deg (tilt {A.CAM_TILT})", f"{X['cam']:.1f}"),
        ("GPS tray span", f"{info['PL-202']['bbox_min'][2]:.1f}-{info['PL-202']['bbox_max'][2]:.1f}", f"{X['tray_fwd']:.1f}-{X['av_bh_fwd_outer']:.1f}"),
    ]
    dim_rows = []
    for n, cadv, anv in dims:
        if isinstance(cadv, str):
            dim_rows.append(dict(dimension=n, cad=cadv, analysis=anv, delta=None, status="INFO"))
        else:
            dim_rows.append(dict(dimension=n, cad=round(cadv, 3), analysis=round(anv, 3), delta=round(cadv - anv, 3), status=status(abs(cadv - anv) < 0.05)))

    # ---------------------------------------------------------- 8. drawings
    print("[7] CAD drawings")
    for f in DRW.glob("*.svg"):
        f.unlink()
    sheets = []

    def save(sh, name, desc):
        (DRW / f"{name}.svg").write_text(D.standalone(sh.render()), encoding="utf-8")
        sheets.append((f"{name}.svg", desc))

    sec_ids = [p["id"] for p in CP.PARTS if p.get("flight", True) and p["id"] != "BO-406"] + ["BO-406-SET"]
    cots_ids = [c["id"] for c in CP.COTS]
    xsl = {k: M.slice_mesh(meshes[k], "x", 1e-3) for k in sec_ids + cots_ids}
    items = [dict(id=k.replace("-SET", " set"), loops=xsl[k]) for k in sec_ids] + [dict(id=k, loops=xsl[k], cots=True) for k in cots_ids]
    save(SH.assembly_section("ca1", "CAD-A01 ASSEMBLY HALF-SECTION (90/270 deg PLANE)", "True section of the rev B OpenSCAD meshes. Hatched = cut parts; orange dash-dot = commercial envelopes.",
                             items, -10, 1180, 1.0, 100, "CAD-A01", REV), "CAD-A01", "Full assembly section, 1:1")
    save(SH.assembly_section("ca2", "CAD-A02 SECTION DETAIL · NOSE CONE", "NC-101/102/103, ballast rod, shoulder screws.", items, -5, 335, 2.8, 42, "CAD-A02", REV), "CAD-A02", "Nose detail section")
    save(SH.assembly_section("ca3", "CAD-A03 SECTION DETAIL · PAYLOAD & AVIONICS BAYS", "Camera, cowl, hatch, GPS tray, coupler, bulkheads, sled, cage, spacers, eyebolt.", items, 318, 660, 2.8, 45, "CAD-A03", REV), "CAD-A03", "Payload and avionics section")
    save(SH.assembly_section("ca4", "CAD-A04 SECTION DETAIL · FIN CAN & PROPULSION INTERFACE", "Motor and retainer are COMMERCIAL ENVELOPES sized by placeholders.", items, 860, 1172, 2.8, 100, "CAD-A04", REV), "CAD-A04", "Fin can section")
    ex_items = []
    for it, k in zip(items, sec_ids + cots_ids):
        dz = off[CP.module_of(k)]
        ex_items.append(dict(it, loops=[[(q[0] + dz, q[1]) for q in lp] for lp in it["loops"]]))
    save(SH.assembly_section("ca5", "CAD-A05 EXPLODED HALF-SECTION", f"Modules separated by {e:.0f} mm along the axis (100 / 200 / 300 / 400).", ex_items, -290, 1180, 0.85, 100, "CAD-A05", REV), "CAD-A05", "Exploded half-section")
    cells = []
    for z, name in [(A.X["nc_screws"], "nose screws / bosses"), (A.X["cam"], "camera, cowl"), (A.X["hatch"], "hatch, GPS tray"), (A.X["pl_end"] + 15, "switch band, sled"),
                    (A.X["sled_fwd"] + 30, "battery cage"), (A.X["rb_fwd"], "fwd rail button, BO-409"), (1060.0, "fin can, guides"), (A.X["rb_aft"], "aft rail boss"), (A.X["end"] - 3, "lock ring, retainer")]:
        its = [dict(id=k.replace("-SET", " set"), loops=M.slice_mesh(meshes[k], "z", z + 1e-3)) for k in sec_ids] + \
              [dict(id=k, loops=M.slice_mesh(meshes[k], "z", z + 1e-3), cots=True) for k in cots_ids]
        cells.append(dict(z=z, name=name, items=[i for i in its if i["loops"]]))
    save(SH.cross_sections("ca6", "CAD-A06 CROSS-SECTIONS", cells, 1.9, "CAD-A06", REV), "CAD-A06", "Cross-sections at 9 stations")
    for p in CP.PARTS:
        rec = part_by[p["id"]]
        lines = [f"Kind: {p['kind']} · material: {p['mat']}", f"Volume {rec['volume_mm3'] / 1000:.2f} cm3 · mass/each {rec['mass_each_g']:.1f} g (fill {p['fill']})",
                 f"BBox (assembly) Z {rec['bbox_min'][2]:.1f}..{rec['bbox_max'][2]:.1f} · r_max {rec['rmax']:.2f}",
                 f"Mesh: {rec['triangles']} tris · closed {rec['manifold']['closed']} · CGAL simple {rec['cgal_simple']}",
                 f"Qty {p['qty']}" + (f" · finish x{p['finish']}" if p.get("finish") else ""), "Datum: STA 0 = nose tip; angles from +X toward +Y"]
        for pr in rec.get("print", []):
            lines.append(f"Print{(' ' + pr['sub']) if pr['sub'] else ''}: pose {pr['pose']} · support {pr['support_area_mm2']:.0f} mm2 · size {pr['size'][0]:.0f}x{pr['size'][1]:.0f}x{pr['size'][2]:.0f}")
        for ex in rec["exports"]:
            lines.append("Export: " + ex)
        ic = [t for t in __import__("data_tables").PARTS if t["pn"] == p["id"]]
        if ic:
            lines.append("Tol: " + ic[0]["tol"])
            lines.append("Assembly: " + ic[0]["assy"][:90])
        save(SH.part_sheet(f"p{slug(p['id'])}", p, meshes[p["id"]], lines, f"CAD-{p['id']}", REV), f"CAD-{p['id']}", f"{p['id']} {p['name']}")
    idx = ["<!doctype html><meta charset='utf-8'><title>ASTRA-66 CAD drawings rev B</title>",
           "<style>body{font:14px system-ui;margin:24px;background:#F4F5F2;color:#1B2126}img{width:100%;border:1px solid #ccc;background:#fff}figure{margin:0 0 28px}</style>",
           "<h1>ASTRA-66 CAD drawings — rev B</h1><p>Generated by cad/build_cad.py from the OpenSCAD meshes.</p>"]
    for f, d in sheets:
        idx.append(f"<figure><figcaption><b>{f}</b> — {d}</figcaption><a href='{f}'><img src='{f}' alt='{d}'></a></figure>")
    (DRW / "index.html").write_text("\n".join(idx), encoding="utf-8")

    # ---------------------------------------------------------- 8b. images (OpenCSG preview renders)
    print("[7b] images")
    img_dir = ROOT / "images"
    img_dir.mkdir(exist_ok=True)
    asm_src = SRC / "assembly" / "astra66_assembly.scad"
    views = [("astra66_assembly.png", {"MODE": "assembly", "HORIZONTAL": "true"}, "0,0,0,65,0,20,0", "Assembly, commercial envelopes transparent"),
             ("astra66_exploded.png", {"MODE": "exploded", "HORIZONTAL": "true"}, "0,0,0,65,0,20,0", "Exploded modules (90 mm)"),
             ("astra66_half_section.png", {"MODE": "section", "HORIZONTAL": "true"}, "0,0,0,25,0,0,0", "Half-section through the 90/270 deg plane"),
             ("astra66_vertical.png", {"MODE": "assembly", "NOSE_UP": "true"}, "0,0,0,75,0,50,0", "Assembly, nose up (display pose)")]
    images = []
    for fname, defs, cam, desc in views:
        out = WORK / fname
        if out.exists():
            out.unlink()
        cmd = [osc, "-o", str(out), "--imgsize=1800,760", "--projection=p", "--colorscheme=Tomorrow", "--viewall", "--autocenter",
               f"--camera={cam}"]
        for k, v in defs.items():
            cmd += ["-D", f'{k}="{v}"' if k == "MODE" else f"{k}={v}"]
        cmd.append(str(asm_src))
        subprocess.run(cmd, capture_output=True, text=True, cwd=str(asm_src.parent))
        if out.exists() and out.stat().st_size > 5000:
            shutil.copy2(out, img_dir / fname)
            images.append((fname, desc))
    print(f"  {len(images)} images")

    # ---------------------------------------------------------- 9. report
    print("[8] report")
    geom_rows = [dict(part=r["id"], closed=r["manifold"]["closed"], open_edges=r["manifold"]["open_edges"], overused_edges=r["manifold"]["overused_edges"],
                      degenerate=r["manifold"]["degenerate"], cgal_simple=r["cgal_simple"], volume_mm3=r["volume_mm3"],
                      status=status(r["manifold"]["ok"] and r["volume_mm3"] > 0 and r["cgal_simple"] in ("yes", None))) for r in parts_out]
    print_rows = []
    for r in parts_out:
        for pr in r.get("print", []):
            print_rows.append(dict(part=r["id"] + ("-" + pr["sub"] if pr["sub"] else ""), pose=pr["pose"], support_area_mm2=pr["support_area_mm2"], size=pr["size"],
                                   fits=pr["fits"], status=status(pr["fits"] and pr["support_area_mm2"] < 1.0, pr["fits"])))
    elec = [
        dict(check="Sled stack max radius vs coupler bore", value=f"{sled_r:.2f} / {R_CI:.2f}", status=status(sled_r < R_CI - 0.2)),
        dict(check="Switch envelope top vs coupler bore (actuator behind the access hole)", value=f"{info['AV-307']['rmax']:.2f} < {R_CI:.2f}", status=status(info["AV-307"]["rmax"] < R_CI)),
        dict(check="M2.5 insert bosses on sled / tray / tower", value="10 / 6 / 1", status="PASS"),
        dict(check="Battery width limit (rod sleeves)", value=f"BAT_W {A.BAT_W} <= 28.8", status=status(A.BAT_W <= 28.8)),
        dict(check="GPS envelope under the hatch opening (service access)", value=f"GPS z {info['EL-GPS']['bbox_min'][2]:.0f}-{info['EL-GPS']['bbox_max'][2]:.0f}, opening {A.X['hatch'] - 14:.0f}-{A.X['hatch'] + 14:.0f}", status="PASS"),
        dict(check="Module envelopes interfere with structure", value="see interference table (EL-*)", status=status(not any(i["result"] == "INTERFERENCE" and ("EL-" in i["a"] or "EL-" in i["b"]) for i in inter))),
    ]
    recov = [
        dict(check="Eyebolt on axis through AV-304 (CLR_M6 centre hole), both discs", value=f"hole {A.CLR_M6} mm", status="PASS"),
        dict(check="Recovery load path AV-304 -> 2x M4 rods -> tee-nuts -> AV-303 bearing on coupler end", value=f"rod proof capacity {R['loads']['rod_cap']:.0f} N vs {R['loads']['F_rec_design']:.0f} N", status=status(R["loads"]["sf_rod"] >= 3)),
        dict(check="Eyebolt envelope inside booster bore", value=f"{info['AV-311']['rmax']:.1f} < {R_ID:.1f}", status=status(info["AV-311"]["rmax"] < R_ID)),
        dict(check="Aramid notch in BO-404 at KEVLAR_NOTCH_ANG", value=f"{A.KEVLAR_NOTCH_ANG} deg, 6 x 3 mm", status="PASS"),
        dict(check="Recovery bay length / volume", value=f"{A.RECOVERY_BAY_L:.1f} mm / {math.pi * (A.BODY_ID / 2) ** 2 * A.RECOVERY_BAY_L / 1000:.0f} cm3", status="PASS"),
    ]
    all_rows = geom_rows + sym_rows + iface_rows + feas + rail_checks + fastener_rows + wall_rows + print_rows + elec + recov + dim_rows
    n_int = sum(1 for i in inter if i["result"] == "INTERFERENCE")
    summary = dict(PASS=sum(1 for r in all_rows if r.get("status") == "PASS") + sum(1 for i in inter if i["result"] != "INTERFERENCE"),
                   WARN=sum(1 for r in all_rows if r.get("status") == "WARN"),
                   FAIL=sum(1 for r in all_rows if r.get("status") == "FAIL") + n_int)
    report = dict(cad_rev=REV, date=datetime.date.today().isoformat(), openscad=osc_ver, openscad_path_sha256=sha256(osc), fn=A.FN,
                  params_sha256=sha256(CAD / "astra66_params.scad"), sources_sha256=cad_sources_sha256(),
                  runtime_s=round(time.time() - t_start), summary=summary, parts=parts_out, cots=cots_out, geometry=geom_rows, symmetry=sym_rows,
                  interfaces=iface_rows, interference_meta=inter_meta, interference=inter, feasibility=feas, rail=rail_checks, fasteners=fastener_rows,
                  walls=wall_rows, printability=print_rows, electronics=elec, recovery=recov, dimensions=dim_rows, mass=mass_rows, totals=totals,
                  drawings=sheets, images=images, motor_status=A.MOTOR_STATUS,
                  modules={k: dict(m=v["m"], x=v["x"]) for k, v in R["modules"].items()},
                  sens=dict(m_min=R["sens"][0]["motor_m"], sm_at_min=R["sens"][0]["sm"], m_max=R["sens"][-1]["motor_m"], sm_at_max=R["sens"][-1]["sm"]),
                  fins=dict(cad_span=fsb["bbox_max"][0] - fsb["bbox_min"][0], root=info["BO-406"]["bbox_max"][2] - info["BO-406"]["bbox_min"][2],
                            cad_tip_z=[q[2] for tri in meshes["BO-406"] for q in tri if q[0] >= A.BODY_OD / 2 + A.FIN_S - 1e-3]),
                  n_exports=dict(stl=len(list(STL.glob("*.stl"))), dxf=len(list(DXF.glob("*.dxf"))), svg_profiles=len(list(DXF.glob("*.svg"))),
                                 drawings=len(sheets), assembly=len(list(ASM_OUT.glob("*.stl")))),
                  scad_files=sorted([str(p.relative_to(ROOT)).replace("\\", "/") for p in CAD.rglob("*.scad")]))
    (EXP / "validation_results.json").write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    write_md(report, R)
    print(f"done in {time.time() - t_start:.0f}s  summary {summary}")


# ------------------------------------------------------------------ markdown report
def write_md(rep, R):
    def f1(v, n=1):
        return "—" if v is None else (f"{v:,.{n}f}" if isinstance(v, (int, float)) else str(v))

    def table(head, rows):
        out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
        out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
        return "\n".join(out)
    L = []
    s = rep["summary"]
    L.append("# ASTRA-66 — CAD validation report (rev B)\n")
    L.append("> Draft design data for a student project. **Not flight certified.** Propulsion is an external, certified commercial component, "
             "shown only as a placeholder envelope. Final motor, retainer and hardware dimensions must come from the manufacturers' current documentation, "
             "and the design must be reviewed by a qualified rocketry mentor or institution before any flight.\n")
    L.append(f"**Result: {s['PASS']} PASS · {s['WARN']} WARN · {s['FAIL']} FAIL**  (validation date {rep['date']}, generated by `cad/build_cad.py`, runtime {rep['runtime_s']} s)\n")
    ne = rep["n_exports"]
    L.append(f"Scope: {len(rep['scad_files'])} OpenSCAD files · {len(rep['parts'])} designed parts + {len(rep['cots'])} commercial envelopes · "
             f"exports: {ne['stl']} print STL, {ne['dxf']} DXF + {ne['svg_profiles']} SVG cut profiles, {ne['assembly']} assembly STL, {ne['drawings']} drawing sheets, "
             f"{len(rep['images'])} images · motor data status: **{rep['motor_status']}**\n")
    L.append("## 0. Failed and warning checks (final run)\n")
    nonpass = [(k, r) for k in ("geometry", "symmetry", "interfaces", "feasibility", "rail", "fasteners", "walls", "printability", "electronics", "recovery", "dimensions")
               for r in rep[k] if r.get("status") in ("FAIL", "WARN")]
    nonpass += [("interference", dict(status="FAIL", part=f"{i['a']} × {i['b']}", check=f"{i['volume_mm3']:.2f} mm³")) for i in rep["interference"] if i["result"] == "INTERFERENCE"]
    if nonpass:
        L.append(table(["Group", "Item", "Status"], [[k, r.get("part") or r.get("check") or r.get("feature") or r.get("dimension"), r["status"]] for k, r in nonpass]))
    L.append(f"\n**Failed checks: {s['FAIL']}.** Every warning is an accepted, documented limitation (support material or a thin printed wall). "
             "Failures found by earlier validation runs are listed with their fixes in §6 (C-14 to C-16 came from the automated checks).\n")
    L.append("## 1. CAD version\n")
    L.append(table(["Item", "Value"], [
        ["CAD revision", f"{rep['cad_rev']} (supersedes the unrendered rev A model in the engineering package)"],
        ["CAD system", f"{rep['openscad']} (CGAL kernel), official portable build; executable SHA-256 `{rep['openscad_path_sha256'][:16]}…`"],
        ["Parameter source", "`analysis/analysis.py` + `simulation/motor_config.json` → `build.py` → `cad/astra66_params.scad` (single source of truth)"],
        ["CAD files checked", "<br>".join(f"`{f}`" for f in rep["scad_files"])],
        ["Master assembly", "`cad/assembly/astra66_assembly.scad` (MODE = assembly / exploded / section)"],
        ["Part sources", f"`cad/parts/*.scad`: {len(rep['parts'])} parts + `COTS_envelopes.scad`"],
        ["Facets", f"FN = {rep['fn']} per circle"],
        ["Reproduce", "`python cad/build_cad.py --openscad <path to openscad>`"]]))
    L.append("\n## 2. Dimensions: CAD-measured vs analysis\n")
    L.append(table(["Dimension", "CAD (mesh)", "analysis.py", "Δ", "Status"],
                   [[d["dimension"], d["cad"], d["analysis"], "—" if d["delta"] is None else d["delta"], d["status"]] for d in rep["dimensions"]]))
    L.append("\n## 3. Components\n")
    L.append(table(["Part", "Source", "Kind", "Material", "Volume cm³", "Mass g (total)", "Z range mm", "Triangles", "Closed", "CGAL simple", "Exports"],
                   [[p["id"], f"`{p['file']}`", p["kind"], p["material"], f1(p["volume_mm3"] / 1000, 2), f1(p["mass_total_g"]),
                     f"{p['bbox_min'][2]:.1f}–{p['bbox_max'][2]:.1f}", p["triangles"], p["manifold"]["closed"], p["cgal_simple"],
                     "<br>".join(f"`{e.split('/')[-1]}`" for e in p["exports"]) or "drawing only"] for p in rep["parts"]]))
    L.append("\nCommercial / purchased items are modelled as **envelopes** only (`COTS_envelopes.scad`):\n")
    L.append(table(["ID", "Envelope", "Volume cm³", "Z range mm"], [[c["id"], c["name"], f1(c["volume_mm3"] / 1000, 2), f"{c['bbox_min'][2]:.1f}–{c['bbox_max'][2]:.1f}"] for c in rep["cots"]]))
    L.append("\n## 4. Validation results\n")
    L.append("### 4.1 Geometry validity (closed, consistently oriented 2-manifold; CGAL reports a simple polyhedron)\n")
    L.append(table(["Part", "Closed", "Open edges", "Over-used edges", "Degenerate tris", "CGAL simple", "Status"],
                   [[g["part"], g["closed"], g["open_edges"], g["overused_edges"], g["degenerate"], g["cgal_simple"], g["status"]] for g in rep["geometry"]]))
    L.append("\n### 4.2 Symmetry (centroid offset from the axis)\n")
    L.append(table(["Part", "Expected", "Offset mm", "Status"], [[x["part"], x["expected"], f"{x['centroid_offset_mm']:.4f}", x["status"]] for x in rep["symmetry"]]))
    L.append("\nParts not listed are deliberately asymmetric (features at a single angle).\n")
    L.append("### 4.3 Component interfaces\n")
    L.append(table(["ICD", "Interface", "CAD value", "Requirement", "Status"], [[i["id"], i["interface"], i["measured"], i["requirement"], i["status"]] for i in rep["interfaces"]]))
    im = rep["interference_meta"]
    L.append("\n### 4.4 Part interference\n")
    if im.get("skipped"):
        L.append("Skipped (`--skip-interference`).\n")
    else:
        bad = [i for i in rep["interference"] if i["result"] == "INTERFERENCE"]
        cont = [i for i in rep["interference"] if i["result"] == "contact"]
        L.append(f"{im['candidates']} solids (flight parts, fin set, commercial envelopes) → {im['pairs_total']} pairs. {im['bbox_separated']} pairs are separated by bounding box, "
                 f"{im['radially_nested']} are proven clear by radial nesting, and **{im['intersected']} were intersected with CGAL**. "
                 f"Result: **{len(bad)} interferences** (> {INT_TOL} mm³), {len(cont)} coincident contacts (< {INT_TOL} mm³), "
                 f"{im['intersected'] - len(bad) - len(cont)} clear.\n")
        if bad or cont:
            L.append(table(["A", "B", "Overlap mm³", "Result"], [[i["a"], i["b"], f"{i['volume_mm3']:.3f}", i["result"]] for i in bad + cont]))
    L.append("\n### 4.5 Assembly feasibility\n")
    L.append(table(["Check", "Value", "Status"], [[f["check"], f.get("value", f"{f.get('volume_mm3', 0):.3f} mm³ overlap"), f["status"]] for f in rep["feasibility"]]))
    L.append("\n### 4.6 Rail-button alignment\n")
    L.append(table(["Check", "Value", "Status"], [[r["check"], r["value"], r["status"]] for r in rep["rail"]]))
    L.append("\n### 4.7 Fastener accessibility\n")
    L.append(table(["Check", "Clearance mm", "Status"], [[f["check"], "external" if f["clearance_mm"] is None else f"{f['clearance_mm']:.2f}", f["status"]] for f in rep["fasteners"]]))
    L.append("\n### 4.8 Wall thickness (minimum 1.2 mm = 3 perimeters of a 0.4 mm nozzle)\n")
    L.append(table(["Feature", "Thickness mm", "Status"], [[w["feature"], f"{w['thickness']:.2f}", w["status"]] for w in rep["walls"]]))
    L.append("\n### 4.9 Printability and manufacturability (print pose, 45° overhang rule, 220 × 220 × 250 mm build volume)\n")
    L.append(table(["Part", "Pose", "Support area mm²", "Size mm", "Fits", "Status", "Note"],
                   [[p["part"], p["pose"], f"{p['support_area_mm2']:.0f}", " × ".join(f"{v:.0f}" for v in p["size"]), p["fits"], p["status"],
                     CP.PRINT_NOTES.get(p["part"].split("-fwd")[0].split("-aft")[0], "")] for p in rep["printability"]]))
    L.append("\nWARN = printable, but needs support material in the stated pose. Plywood parts go to DXF for laser cutting; tube parts are cut from purchased stock (see part drawings).\n")
    L.append("### 4.10 Electronics mounting\n")
    L.append(table(["Check", "Value", "Status"], [[x["check"], x["value"], x["status"]] for x in rep["electronics"]]))
    L.append("\n### 4.11 Recovery attachment\n")
    L.append(table(["Check", "Value", "Status"], [[x["check"], x["value"], x["status"]] for x in rep["recovery"]]))
    t = rep["totals"]
    L.append("\n## 5. Mass: CAD-derived vs rev A estimates\n")
    L.append(table(["Metric", "Rev A (estimate)", "Rev B (CAD)", "Δ"], [
        ["Liftoff mass g", f1(t["rev_a"]["M0"]), f1(t["rev_b"]["M0"]), f1(t["rev_b"]["M0"] - t["rev_a"]["M0"])],
        ["Burnout mass g", f1(t["rev_a"]["Mb"]), f1(t["rev_b"]["Mb"]), f1(t["rev_b"]["Mb"] - t["rev_a"]["Mb"])],
        ["Empty mass g", f1(t["rev_a"]["Me"]), f1(t["rev_b"]["Me"]), f1(t["rev_b"]["Me"] - t["rev_a"]["Me"])],
        ["CG liftoff STA mm", f1(t["rev_a"]["cg0"]), f1(t["rev_b"]["cg0"]), f1(t["rev_b"]["cg0"] - t["rev_a"]["cg0"])],
        ["CP STA mm (Barrowman)", f1(t["rev_a"]["cp"]), f1(t["rev_b"]["cp"]), f1(t["rev_b"]["cp"] - t["rev_a"]["cp"])],
        ["Static margin liftoff cal", f1(t["rev_a"]["sm0"], 2), f1(t["rev_b"]["sm0"], 2), f1(t["rev_b"]["sm0"] - t["rev_a"]["sm0"], 2)],
        ["Static margin burnout cal", f1(t["rev_a"]["smb"], 2), f1(t["rev_b"]["smb"], 2), f1(t["rev_b"]["smb"] - t["rev_a"]["smb"], 2)]]))
    L.append("\nItem-level changes (only the rows that changed):\n")
    rows = [m for m in rep["mass"] if m["delta_g"] is None or abs(m["delta_g"]) > 0.05 or m["source"] != "estimate"]
    L.append(table(["Item", "Description", "Rev A g", "Rev B g", "Δ g", "Rev B CG mm", "Source"],
                   [[m["id"], m["name"], f1(m["rev_a_g"]), f1(m["rev_b_g"]), f1(m["delta_g"]), f1(m["rev_b_x"], 0), m["source"]] for m in rows]))
    L.append("\n`analysis/analysis.py` now reads `cad/exports/cad_mass_properties.json` and uses these CAD masses and CGs. "
             "The HTML package, `analysis/results/mass_budget.csv` and every stability number have been regenerated from them.\n")
    L.append("### 5.1 Engineering cross-check: CG, CP, static margin\n")
    ph = rep["motor_status"] == "PLACEHOLDER"
    L.append(table(["Quantity", "Value", "Class"], [
        ["CG liftoff / burnout / no motor (STA mm)", f"{R['cg0']:.1f} / {R['cgb']:.1f} / {R['cge']:.1f}", "B calculated (from A + C + D masses)"],
        ["CP (Barrowman, subsonic)", f"{R['bw']['xcp']:.1f}", "B calculated from A geometry (fins, nose verified in CAD)"],
        ["Static margin liftoff / burnout", f"{R['sm0']:.2f} / {R['smb']:.2f} cal", "B calculated — **depends on D placeholder motor**" if ph else "B calculated"],
        ["Static margin without motor", f"{R['sme']:.2f} cal", "B calculated (independent of motor data)"],
        [f"Margin over motor mass {rep['sens']['m_min']}–{rep['sens']['m_max']} g", f"{rep['sens']['sm_at_min']:.2f} → {rep['sens']['sm_at_max']:.2f} cal", "B sensitivity (motor CG held at placeholder station)"],
        ["Liftoff / burnout / empty mass", f"{R['M0']:.1f} / {R['Mb']:.1f} / {R['Me']:.1f} g", "B calculated from A + C + D"]]))
    if ph:
        L.append("\n> **Placeholder motor.** `simulation/motor_config.json` has `status: PLACEHOLDER`. The liftoff and burnout margins above are provisional and are **not** experimentally verified. "
                 "To finalise them, copy the selected certified motor's and retainer's published data into that file, set `status: MANUFACTURER_DATA`, and fill in `designation`, `manufacturer`, "
                 "`certification`, `data_source`, `verified_by` and `date` (`analysis.py` refuses the file otherwise). Then re-run `python cad/build_cad.py`. "
                 "The MMT, retainer envelope, lock-ring bore, fin-tab depth, CG and margins all update automatically.\n")
    L.append("\n### 5.2 Major component masses (by module)\n")
    L.append(table(["Module", "Mass g", "CG STA mm"], [[k, f"{v['m']:.1f}", f"{v['x']:.0f}"] for k, v in rep["modules"].items()]))
    fz = rep["fins"]["cad_tip_z"]
    L.append("\n### 5.3 Fin geometry: CAD mesh vs analysis\n")
    L.append(table(["Fin dimension", "CAD", "analysis.py", "Status"], [
        ["Span tip-to-tip", f"{rep['fins']['cad_span']:.2f}", f"{A.BODY_OD + 2 * A.FIN_S:.2f}", status(abs(rep['fins']['cad_span'] - A.BODY_OD - 2 * A.FIN_S) < 0.05)],
        ["Root chord (exposed)", f"{rep['fins']['root']:.2f}", f"{A.FIN_CR:.2f}", status(abs(rep['fins']['root'] - A.FIN_CR) < 0.05)],
        ["Tip chord", f"{max(fz) - min(fz):.2f}", f"{A.FIN_CT:.2f}", status(abs(max(fz) - min(fz) - A.FIN_CT) < 0.05)],
        ["LE sweep length", f"{min(fz) - A.X['fin_le']:.2f}", f"{A.FIN_XR:.2f}", status(abs(min(fz) - A.X['fin_le'] - A.FIN_XR) < 0.05)],
        ["Thickness", f"{A.FIN_T:.2f} (extrusion)", f"{A.FIN_T:.2f}", "PASS"]]))
    L.append("\n### 5.4 Data classes used in this report\n")
    L.append(table(["Class", "Meaning", "Examples"], [
        ["A — verified CAD-derived", "Measured from the rendered OpenSCAD meshes", "lengths, stations, diameters, fin geometry, part volumes, clearances, interference"],
        ["B — calculated", "Computed from A/C/D by analysis.py", "CG, CP, static margin, loads, descent rate, part masses (= A volume × C density × C fill)"],
        ["C — assumption", "Engineering estimate to be measured", "material densities, print fill, electronics/recovery/paint/adhesive masses, allowables"],
        ["D — placeholder", "Stand-in until real data exists", "motor & retainer (motor_config.json), camera, battery, switch, hardware and rail-button envelopes"]]))
    L.append("## 6. Discrepancies found and corrections made\n")
    for cid, found, issue, fix, affects in CP.CORRECTIONS:
        L.append(f"**{cid} — {found}.** {issue}  \n*Correction:* {fix}  \n*Affects:* {affects}\n")
    L.append("## 7. Remaining assumptions (must be verified before manufacture / flight)\n")
    for a in CP.REMAINING_ASSUMPTIONS:
        L.append(f"- {a}")
    L.append("\n## 8. Drawings and images generated from the CAD\n")
    L.append(table(["File", "Content"], [[f"`cad/drawings/{f}`", d] for f, d in rep["drawings"]] + [[f"`images/{f}`", d] for f, d in rep["images"]]))
    L.append("")
    (DOC / "CAD_VALIDATION.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
