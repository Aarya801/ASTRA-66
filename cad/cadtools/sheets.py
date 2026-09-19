"""CAD-derived drawing sheets for ASTRA-66: every outline is a true plane section of the rendered
OpenSCAD meshes (no hand-drawn geometry). Reuses the Sheet class and style of drawings.py."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "analysis", ROOT / "documentation" / "generator"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import drawings as D  # noqa: E402
from . import mesh as M  # noqa: E402

HATCH = ["h1", "h2", "h3"]


def path_d(loops, tf):
    out = []
    for lp in loops:
        pts = [tf(p) for p in lp]
        out.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z")
    return " ".join(out)


def draw_loops(sh, loops, tf, hatch=None, cls="cut"):
    d = path_d(loops, tf)
    if not d:
        return
    fill = f' fill="url(#{hatch}-{sh.k})"' if hatch else ""
    sh.raw(f'<path d="{d}" class="{cls}"{fill} fill-rule="evenodd"/>')


def title_block(sh, dwg, title, cells):
    y = sh.h - 50
    sh.rect(12, y, sh.w - 24, 38, "ln thin")
    widths = [120, 420] + [(sh.w - 24 - 540) / max(1, len(cells))] * len(cells)
    x = 12
    items = [("DWG NO.", dwg), ("TITLE", title)] + list(cells)
    for (lab, val), w in zip(items, widths):
        sh.line(x, y, x, y + 38, "ln thin")
        sh.text(x + 6, y + 13, lab, "tm ts", "start")
        sh.text(x + 6, y + 30, str(val), "tb" if lab == "TITLE" else "", "start")
        x += w


def _place_labels(sh, anchors, y_rows_up, y_rows_dn, min_dx=150):
    """anchors: list of (px, py, text, up). Greedy row assignment to avoid overlap."""
    rows_up = [[] for _ in y_rows_up]
    rows_dn = [[] for _ in y_rows_dn]
    for px, py, text, up in sorted(anchors, key=lambda a: a[0]):
        rows, ys = (rows_up, y_rows_up) if up else (rows_dn, y_rows_dn)
        w = max(min_dx, 7.0 * len(text) + 12)
        for r, row in enumerate(rows):
            if all(abs(px - x) > (w + ww) / 2 for x, ww in row):
                row.append((px, w))
                sh.leader(px, py, px, ys[r], text, "middle", "ts")
                break
        else:
            sh.leader(px, py, px, ys[-1], text, "middle", "ts")


def assembly_section(key, title, sub, items, z0, z1, scale, ymax, dwg, rev, labels=True, offsets=None):
    """items: list of dict(id, loops (z,y), cots(bool)). Loops outside [z0, z1] are clipped."""
    w = int((z1 - z0) * scale + 140)
    rows = 3
    top = 70 + rows * 20
    h = int(top + 2 * ymax * scale + rows * 20 + 110)
    sh = D.Sheet(key, w, h, title)
    ox, oy = 70, top + ymax * scale

    def tf(p):
        return (ox + (p[0] - z0) * scale, oy - p[1] * scale)
    sh.raw(f'<clipPath id="cp-{key}"><rect x="{ox - 2}" y="{top - 4}" width="{(z1 - z0) * scale + 4}" height="{2 * ymax * scale + 8}"/></clipPath>')
    sh.raw(f'<g clip-path="url(#cp-{key})">')
    anchors = []
    for i, it in enumerate(items):
        loops = it["loops"]
        if not loops:
            continue
        if it.get("cots"):
            draw_loops(sh, loops, tf, None, "ph")
        else:
            draw_loops(sh, loops, tf, HATCH[i % 3])
        vis = [p for lp in loops for p in lp if z0 + 2 <= p[0] <= z1 - 2 and abs(p[1]) <= ymax]
        if vis and labels:
            p = max(vis, key=lambda q: abs(q[1]) - 0.001 * abs(q[0] - (z0 + z1) / 2))
            px, py = tf(p)
            anchors.append((px, py, it["id"], p[1] >= 0))
    sh.raw("</g>")
    sh.centerline(ox - 10, ox + (z1 - z0) * scale + 10, oy)
    if labels:
        _place_labels(sh, anchors, [top - 12 - 20 * r for r in range(rows)],
                      [oy + ymax * scale + 24 + 20 * r for r in range(rows)], min_dx=60)
    # station scale
    step = 50 if (z1 - z0) > 400 else 25
    ys = oy + ymax * scale + 24 + 20 * rows
    s0 = int(math.ceil(z0 / step) * step)
    for st in range(s0, int(z1) + 1, step):
        x = ox + (st - z0) * scale
        sh.line(x, ys - 4, x, ys + 4, "dim")
        if (st // step) % 2 == 0:
            sh.text(x, ys + 16, f"{st}", "td ts")
    sh.text(ox, ys - 8, "STATION mm", "td ts", "start")
    sh.title(18, 24, title, sub)
    title_block(sh, dwg, title, [("SCALE", f"{scale:g}:1 vb"), ("UNITS", "mm"), ("SOURCE", "CAD mesh section"), ("REV", rev)])
    return sh


def cross_sections(key, title, cells, scale, dwg, rev):
    """cells: list of dict(z, name, items=[dict(id, loops (x,y), cots)])."""
    ncol = 3
    cw, chh = 420, 430
    nrow = math.ceil(len(cells) / ncol)
    sh = D.Sheet(key, ncol * cw + 40, nrow * chh + 120, title)
    for n, c in enumerate(cells):
        cx = 20 + (n % ncol) * cw + cw / 2
        cy = 80 + (n // ncol) * chh + 190

        def tf(p, cx=cx, cy=cy):
            return (cx + p[0] * scale, cy - p[1] * scale)
        ids = []
        for i, it in enumerate(c["items"]):
            if not it["loops"]:
                continue
            draw_loops(sh, it["loops"], tf, None if it.get("cots") else HATCH[i % 3], "ph" if it.get("cots") else "cut")
            ids.append(it["id"])
        sh.line(cx - 100 * scale, cy, cx + 100 * scale, cy, "ctr")
        sh.line(cx, cy - 100 * scale, cx, cy + 100 * scale, "ctr")
        sh.text(cx, cy - 175, f"SECTION @ STA {c['z']:.0f} · {c['name']}", "tb ts")
        txt = ", ".join(ids)
        for k in range(0, len(txt), 58):
            sh.text(cx, cy + 190 + (k // 58) * 13, txt[k:k + 58], "tm ts")
    sh.title(18, 24, title, "Looking aft; +Y (90 deg, switch/hatch side) up, +X (fin 1) right. Orange dash-dot = commercial envelopes.")
    title_block(sh, dwg, title, [("SCALE", f"{scale:g}:1 vb"), ("UNITS", "mm"), ("SOURCE", "CAD mesh section"), ("REV", rev)])
    return sh


def part_sheet(key, part, tris, info, dwg, rev):
    """Manufacturing sheet: longitudinal section + end view from the CAD mesh, bbox dimensions, data."""
    sh = D.Sheet(key, 1300, 760, f"{part['id']} {part['name']} manufacturing drawing")
    ang = part.get("ang", 90)
    rt = M.transform(tris, M.rot("z", 90 - ang))
    if part["id"] == "BO-406":
        long_loops = M.slice_mesh(M.transform(tris, None), "y", 1e-3)       # fin flat profile (z, x)
    else:
        long_loops = M.slice_mesh(rt, "x", 1e-3)
    end_loops = M.slice_mesh(rt, "z", part["end_z"] + 1e-3)
    views = [("A", long_loops, (40, 90, 780, 430), "SECTION A-A (axial plane through the feature angle)" if part["id"] != "BO-406" else "FLAT PATTERN (true shape)"),
             ("B", end_loops, (860, 90, 400, 430), f"SECTION B-B @ STA {part['end_z']:.1f} (looking aft)")]
    for tag, loops, (bx, by, bw, bh), cap in views:
        sh.text(bx, by - 8, cap, "tb ts", "start")
        if not loops:
            sh.text(bx + bw / 2, by + bh / 2, "(no material in this plane)", "tm ts")
            continue
        x0, y0, x1, y1 = M.loops_bbox(loops)
        s = min((bw - 90) / max(x1 - x0, 1e-6), (bh - 90) / max(y1 - y0, 1e-6))
        s = min(s, 12.0)
        ox = bx + (bw - (x1 - x0) * s) / 2 - x0 * s
        oy = by + (bh - (y1 - y0) * s) / 2 + y1 * s

        def tf(p, ox=ox, oy=oy, s=s):
            return (ox + p[0] * s, oy - p[1] * s)
        draw_loops(sh, loops, tf, "h1")
        X0, Y1 = tf((x0, y0))
        X1, Y0 = tf((x1, y1))
        sh.dim_h(X0, X1, Y1 + 30, f"{x1 - x0:.1f}", Y1, Y1, below=True)
        sh.dim_v(Y0, Y1, X1 + 34, f"{y1 - y0:.1f}", X1, X1, right=True)
        sh.text(bx + bw - 4, by + bh - 4, f"view scale {s:.2f}:1", "tm ts", "end")
    y = 560
    col = [40, 460, 880]
    for i, line in enumerate(info):
        sh.text(col[i % 3], y + (i // 3) * 16, line, "ts", "start")
    sh.title(18, 24, f"{part['id']} · {part['name'].upper()}", f"Source: cad/parts/{part['file']} · generated from the CAD mesh")
    title_block(sh, dwg, f"{part['id']} {part['name']}", [("MATERIAL", part["mat"]), ("QTY", part["qty"]), ("UNITS", "mm"), ("REV", rev)])
    return sh
