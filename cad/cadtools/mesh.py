"""Triangle-mesh utilities for the ASTRA-66 CAD pipeline (pure Python).

read/write STL, mass properties, manifold check, rigid transforms, print-overhang area,
plane slicing into closed loops.
"""
import math
import struct
from collections import defaultdict


def read_stl(path):
    data = open(path, "rb").read()
    if len(data) < 84:
        return []
    n_bin = struct.unpack("<I", data[80:84])[0]
    is_binary = len(data) == 84 + 50 * n_bin
    if not is_binary:
        tris, cur = [], []
        for line in data.decode("ascii", "replace").splitlines():
            s = line.strip()
            if s.startswith("vertex"):
                _, x, y, z = s.split()
                cur.append((float(x), float(y), float(z)))
                if len(cur) == 3:
                    tris.append(tuple(cur))
                    cur = []
        return tris
    tris, off = [], 84
    for _ in range(n_bin):
        v = struct.unpack("<12f", data[off:off + 48])
        off += 50
        tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
    return tris


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def tri_normal(a, b, c):
    n = _cross(_sub(b, a), _sub(c, a))
    L = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    return (n[0] / L, n[1] / L, n[2] / L) if L else (0.0, 0.0, 0.0), L / 2


def write_stl(path, tris, name="ASTRA-66"):
    with open(path, "wb") as fh:
        fh.write(name.encode("ascii", "replace")[:80].ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            n, _ = tri_normal(a, b, c)
            fh.write(struct.pack("<12fH", *n, *a, *b, *c, 0))


def props(tris):
    if not tris:
        return dict(volume=0.0, centroid=(0.0, 0.0, 0.0), area=0.0, bbox_min=[0.0] * 3, bbox_max=[0.0] * 3, triangles=0, rmax=0.0)
    V = cx = cy = cz = area = 0.0
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for a, b, c in tris:
        v = (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        V += v
        cx += v * (a[0] + b[0] + c[0]) / 4
        cy += v * (a[1] + b[1] + c[1]) / 4
        cz += v * (a[2] + b[2] + c[2]) / 4
        area += tri_normal(a, b, c)[1]
        for p in (a, b, c):
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    cen = (cx / V, cy / V, cz / V) if V else (0.0, 0.0, 0.0)
    rmax = max(math.hypot(p[0], p[1]) for t in tris for p in t) if tris else 0.0
    return dict(volume=V, centroid=cen, area=area, bbox_min=lo, bbox_max=hi, triangles=len(tris), rmax=rmax)


def manifold(tris, q=1e-4):
    """Edge-use check: a closed, consistently oriented 2-manifold uses every directed edge exactly once
    and its reverse exactly once."""
    def k(p):
        return (round(p[0] / q), round(p[1] / q), round(p[2] / q))
    directed = defaultdict(int)
    degenerate = 0
    for a, b, c in tris:
        ka, kb, kc = k(a), k(b), k(c)
        if ka == kb or kb == kc or kc == ka:
            degenerate += 1
            continue
        for u, v in ((ka, kb), (kb, kc), (kc, ka)):
            directed[(u, v)] += 1
    open_e = nonman = flipped = 0
    for (u, v), n in directed.items():
        r = directed.get((v, u), 0)
        if n > 1:
            nonman += 1
        if r == 0:
            open_e += 1
    return dict(closed=open_e == 0, open_edges=open_e, overused_edges=nonman, degenerate=degenerate,
                ok=open_e == 0 and nonman == 0)


def rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "x":
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == "y":
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def transform(tris, R=None, t=(0, 0, 0)):
    R = R or ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    def f(p):
        return (R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2] + t[0],
                R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2] + t[1],
                R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2] + t[2])
    return [(f(a), f(b), f(c)) for a, b, c in tris]


POSES = {"id": None, "rx180": ("x", 180), "rx90": ("x", 90), "rx-90": ("x", -90), "ry90": ("y", 90), "ry-90": ("y", -90)}


def to_bed(tris, pose):
    """Apply a named print pose, then centre in XY and drop onto Z = 0."""
    spec = POSES[pose]
    t2 = transform(tris, rot(*spec)) if spec else list(tris)
    p = props(t2)
    lo, hi = p["bbox_min"], p["bbox_max"]
    return transform(t2, None, (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]))


def overhang(tris, crit_deg=45.0, bed_tol=0.2):
    """Area (mm^2) of downward-facing facets steeper than crit_deg from vertical, not on the bed."""
    zmin = min(p[2] for t in tris for p in t)
    lim = -math.cos(math.radians(crit_deg))
    sup = bed = 0.0
    for a, b, c in tris:
        n, ar = tri_normal(a, b, c)
        if n[2] < lim:
            if min(a[2], b[2], c[2]) <= zmin + bed_tol and max(a[2], b[2], c[2]) <= zmin + bed_tol:
                bed += ar
            else:
                sup += ar
    height = max(p[2] for t in tris for p in t) - zmin
    return dict(support_area=sup, bed_area=bed, height=height)


AXES = {"x": (0, (2, 1)), "y": (1, (2, 0)), "z": (2, (0, 1))}


def slice_mesh(tris, axis, value):
    """Intersect with the plane <axis> = value; returns closed loops of 2-D points.
    x-plane -> (z, y); y-plane -> (z, x); z-plane -> (x, y)."""
    ai, (u, v) = AXES[axis]
    segs = []
    for tri in tris:
        d = [p[ai] - value for p in tri]
        if (d[0] > 0 and d[1] > 0 and d[2] > 0) or (d[0] < 0 and d[1] < 0 and d[2] < 0):
            continue
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (d[i] > 0) != (d[j] > 0):
                t = d[i] / (d[i] - d[j])
                a, b = tri[i], tri[j]
                pts.append((a[u] + (b[u] - a[u]) * t, a[v] + (b[v] - a[v]) * t))
        if len(pts) == 2:
            segs.append((pts[0], pts[1]))
    return chain(segs)


def chain(segs, q=1e-4):
    def k(p):
        return (round(p[0] / q), round(p[1] / q))
    adj = defaultdict(list)
    for i, (a, b) in enumerate(segs):
        adj[k(a)].append(i)
        adj[k(b)].append(i)
    used = [False] * len(segs)
    loops = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        a, b = segs[i]
        lp = [a, b]
        start, cur = k(a), k(b)
        while cur != start:
            nxt = next((j for j in adj[cur] if not used[j]), None)
            if nxt is None:
                break
            used[nxt] = True
            c, d = segs[nxt]
            if k(c) == cur:
                lp.append(d)
                cur = k(d)
            else:
                lp.append(c)
                cur = k(c)
        if len(lp) > 3:
            loops.append(lp)
    return loops


def loops_bbox(loops):
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None
