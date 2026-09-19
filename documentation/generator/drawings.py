"""
ASTRA-66 drawing generator -- parametric SVG engineering sheets.

All geometry is read from analysis.py, so changing a parameter there regenerates
consistent drawings. Output SVG uses CSS classes (styled by the HTML package, or by
the embedded <style> in the standalone files written to drawings/).
"""
import math
import analysis as A

X = A.X
R_OD = A.BODY_OD / 2
R_ID = A.BODY_ID / 2
R_SH = (A.BODY_ID - A.FIT_SH) / 2          # printed shoulder / ring OD radius
R_CO = A.CPL_OD / 2
R_CI = A.CPL_ID / 2
R_MO = A.MMT_OD / 2
R_MI = A.MMT_ID / 2


def fm(v, nd=1):
    s = f"{v:.{nd}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


class View:
    def __init__(self, x0, ox, oy, s):
        self.x0, self.ox, self.oy, self.s = x0, ox, oy, s

    def X(self, st):
        return self.ox + (st - self.x0) * self.s

    def Y(self, r):
        return self.oy - r * self.s


class Sheet:
    def __init__(self, key, w, h, label):
        self.k, self.w, self.h, self.label = key, w, h, label
        self.o = []

    # primitives -------------------------------------------------------------
    def raw(self, s):
        self.o.append(s)

    def line(self, x1, y1, x2, y2, c="ln"):
        self.o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{c}"/>')

    def rect(self, x, y, w, h, c="ln", hatch=None, rx=0):
        if w < 0:
            x, w = x + w, -w
        if h < 0:
            y, h = y + h, -h
        fill = f' fill="url(#{hatch}-{self.k})"' if hatch else ""
        rxs = f' rx="{rx:.1f}"' if rx else ""
        self.o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"{rxs} class="{c}"{fill}/>')

    def poly(self, pts, c="ln", hatch=None, closed=True):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        fill = f' fill="url(#{hatch}-{self.k})"' if hatch else ""
        tag = "polygon" if closed else "polyline"
        self.o.append(f'<{tag} points="{d}" class="{c}"{fill}/>')

    def path(self, d, c="ln", hatch=None):
        fill = f' fill="url(#{hatch}-{self.k})"' if hatch else ""
        self.o.append(f'<path d="{d}" class="{c}"{fill}/>')

    def circle(self, cx, cy, r, c="ln"):
        self.o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" class="{c}"/>')

    def ellipse(self, cx, cy, rx, ry, c="ln"):
        self.o.append(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" class="{c}"/>')

    def text(self, x, y, s, c="", a="middle", rot=None):
        tr = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot is not None else ""
        cls = f' class="{c}"' if c else ""
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.o.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{a}"{cls}{tr}>{s}</text>')

    # drafting helpers -------------------------------------------------------
    def dim_h(self, x1, x2, y, label, ey1=None, ey2=None, below=False):
        for x, ey in ((x1, ey1), (x2, ey2)):
            if ey is not None:
                d = 5 if y > ey else -5
                self.line(x, ey + (3 if y > ey else -3), x, y + d, "ext")
        self.o.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="dim" '
                      f'marker-start="url(#a-{self.k})" marker-end="url(#a-{self.k})"/>')
        ty = y + 15 if below else y - 5
        self.text((x1 + x2) / 2, ty, label, "td")

    def dim_v(self, y1, y2, x, label, ex1=None, ex2=None, right=False):
        for y, ex in ((y1, ex1), (y2, ex2)):
            if ex is not None:
                d = 5 if x > ex else -5
                self.line(ex + (3 if x > ex else -3), y, x + d, y, "ext")
        self.o.append(f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" class="dim" '
                      f'marker-start="url(#a-{self.k})" marker-end="url(#a-{self.k})"/>')
        tx = x + 14 if right else x - 6
        self.text(tx, (y1 + y2) / 2, label, "td", rot=-90)

    def leader(self, px, py, lx, ly, label, a="middle", c=""):
        self.circle(px, py, 1.8, "dot")
        ey = ly + (4 if ly < py else -12)
        self.line(px, py, lx, ey, "ldr")
        self.text(lx, ly, label, c, a)

    def pill(self, cx, cy, label, px=None, py=None):
        w = 7.4 * len(label) + 16
        if px is not None:
            self.circle(px, py, 1.8, "dot")
            self.line(px, py, cx, cy + (11 if py > cy else -11), "ldr")
        self.rect(cx - w / 2, cy - 11, w, 22, "pill", rx=11)
        self.text(cx, cy + 4, label, "tb ts")

    def title(self, x, y, s, sub=None):
        self.text(x, y, s, "tl", "start")
        if sub:
            self.text(x, y + 16, sub, "tm ts", "start")

    def centerline(self, x1, x2, y):
        self.line(x1, y, x2, y, "ctr")

    def render(self):
        k = self.k
        defs = (f'<defs>'
                f'<marker id="a-{k}" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="9" markerHeight="9" '
                f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,1.5 L10,5 L0,8.5 z" class="mk"/></marker>'
                f'<marker id="b-{k}" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="10" markerHeight="10" '
                f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" class="mkink"/></marker>'
                f'<marker id="c-{k}" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="10" markerHeight="10" '
                f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" class="mkacc"/></marker>'
                f'<pattern id="h1-{k}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                f'<rect width="5" height="5" class="hatchbg"/><line x1="0" y1="0" x2="0" y2="5" class="hatch"/></pattern>'
                f'<pattern id="h2-{k}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">'
                f'<rect width="5" height="5" class="hatchbg"/><line x1="0" y1="0" x2="0" y2="5" class="hatch"/></pattern>'
                f'<pattern id="h3-{k}" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">'
                f'<rect width="9" height="9" class="hatchbg2"/><line x1="0" y1="0" x2="0" y2="9" class="hatch"/></pattern>'
                f'</defs>')
        body = "".join(self.o)
        label = self.label.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
        return (f'<svg viewBox="0 0 {self.w} {self.h}" class="dwg" role="img" aria-label="{label}" '
                f'xmlns="http://www.w3.org/2000/svg">{defs}{body}</svg>')


STANDALONE_CSS = """
.ln{fill:none;stroke:#1B2126;stroke-width:1.3;stroke-linejoin:round}.thin{stroke-width:.8}
.body{fill:#E3E7E2;stroke:#1B2126;stroke-width:1.3}.band{fill:#D5DBD5;stroke:#1B2126;stroke-width:1}
.comp{fill:#DCE3EA;stroke:#1B2126;stroke-width:.8}.cut{stroke:#1B2126;stroke-width:1}
.hatch{stroke:#7D8784;stroke-width:.8}.hatchbg{fill:#F4F5F2}.hatchbg2{fill:#E9ECE7}
.hid{fill:none;stroke:#87918F;stroke-width:.9;stroke-dasharray:5 3}
.ctr{fill:none;stroke:#87918F;stroke-width:.7;stroke-dasharray:22 4 3 4}
.ph{fill:none;stroke:#C24A0C;stroke-width:1.2;stroke-dasharray:14 4 3 4 3 4}
.dim{fill:none;stroke:#1D6A86;stroke-width:.8}.ext{fill:none;stroke:#1D6A86;stroke-width:.6}
.mk{fill:#1D6A86}.mkink{fill:#1B2126}.mkacc{fill:#C24A0C}.ldr{fill:none;stroke:#4A545C;stroke-width:.7}.dot{fill:#4A545C}
text{font-family:'IBM Plex Mono',Consolas,monospace;font-size:12px;fill:#1B2126}
.td{fill:#1D6A86}.ta{fill:#C24A0C}.tm{fill:#4A545C}.tb{font-weight:600}.ts{font-size:10.5px}
.tl{font-size:15px;font-weight:600;letter-spacing:.06em}
.pill{fill:#F4F5F2;stroke:#1B2126;stroke-width:1}.cgf{fill:#1B2126}.cgb{fill:#F4F5F2;stroke:#1B2126;stroke-width:1.4}
.accf{fill:#C24A0C}.eye{fill:none;stroke:#1B2126;stroke-width:2.4}
.box{fill:#E9ECE7;stroke:#1B2126;stroke-width:1.1}.boxacc{fill:#F8E3D5;stroke:#C24A0C;stroke-width:1.2;stroke-dasharray:6 3}
.boxdim{fill:#DDEBF0;stroke:#1D6A86;stroke-width:1.1}
.arrow{fill:none;stroke:#1B2126;stroke-width:1.3}.arrowacc{fill:none;stroke:#C24A0C;stroke-width:1.5}
.arrowdim{fill:none;stroke:#1D6A86;stroke-width:1.3;stroke-dasharray:6 4}
"""


def standalone(svg):
    return svg.replace('class="dwg" role="img"', 'role="img"', 1).replace(
        "<defs>", f"<style>{STANDALONE_CSS}</style><defs>", 1).replace(
        "<svg ", '<svg style="background:#F4F5F2" ', 1)


# ============================================================================ shared geometry
def ogive_pts(v, x0, x1, off=0.0, sign=1, n=48):
    pts = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        r = max(A.ogive_r(x) - off, 0.0)
        pts.append((v.X(x), v.Y(sign * r)))
    return pts


def nose_wall(sh, v, sign, hatch="h1"):
    """Hatched ogive wall + base ring + shoulder wall for one half (sign=+1 top, -1 bottom)."""
    w = A.NC_WALL
    xs = A.NC_TIP_SOLID
    outer = [(v.X(0), v.Y(0))] + ogive_pts(v, 0.0, A.NC_L, 0, sign)
    inner = list(reversed(ogive_pts(v, xs, A.NC_L, w, sign)))
    sh.poly(outer + inner + [(v.X(xs), v.Y(0))], "cut", hatch)
    # base ring at nose base, then shoulder wall
    sh.poly([(v.X(A.NC_L - 1.6), v.Y(sign * (R_SH - A.NC_SH_WALL))), (v.X(A.NC_L), v.Y(sign * (R_SH - A.NC_SH_WALL))),
             (v.X(A.NC_L), v.Y(sign * R_OD)), (v.X(A.NC_L - 1.6), v.Y(sign * (A.ogive_r(A.NC_L - 1.6))))], "cut", hatch)
    sh.rect(v.X(A.NC_L), v.Y(sign * R_SH), A.NC_SH_L * v.s, sign * A.NC_SH_WALL * v.s, "cut", hatch)
    # print split + spigot (belongs to NC-101)
    rs = A.ogive_r(A.NC_SPLIT)
    sh.line(v.X(A.NC_SPLIT), v.Y(sign * (rs - w)), v.X(A.NC_SPLIT), v.Y(sign * rs), "ln")
    sp = rs - w - A.FIT_SH / 2
    sh.rect(v.X(A.NC_SPLIT - A.NC_SPLIT_WEB), v.Y(sign * sp), (A.NC_SPLIT_WEB + A.NC_SPIGOT_L) * v.s, sign * A.NC_SPIGOT_WALL * v.s, "cut", "h2")


def tube_walls(sh, v, x1, x2, r_in, r_out, hatch="h1", gaps_top=(), gaps_bot=()):
    for sign, gaps in ((1, gaps_top), (-1, gaps_bot)):
        segs = []
        cur = x1
        for g0, g1 in sorted(gaps):
            segs.append((cur, g0))
            cur = g1
        segs.append((cur, x2))
        for a, b in segs:
            if b > a:
                sh.rect(v.X(a), v.Y(sign * r_out), (b - a) * v.s, (r_out - r_in) * v.s, "cut", hatch)


def cg_symbol(sh, cx, cy, r=9):
    sh.circle(cx, cy, r, "cgb")
    sh.path(f"M{cx:.1f},{cy:.1f} L{cx + r:.1f},{cy:.1f} A{r},{r} 0 0 0 {cx:.1f},{cy - r:.1f} Z", "cgf")
    sh.path(f"M{cx:.1f},{cy:.1f} L{cx - r:.1f},{cy:.1f} A{r},{r} 0 0 0 {cx:.1f},{cy + r:.1f} Z", "cgf")


def cp_symbol(sh, cx, cy, r=9):
    sh.circle(cx, cy, r, "cgb")
    sh.circle(cx, cy, 3.2, "accf")
    sh.line(cx - r - 4, cy, cx + r + 4, cy, "ln thin")
    sh.line(cx, cy - r - 4, cx, cy + r + 4, "ln thin")


def fin_poly_st(s=A.FIN_S, xr=A.FIN_XR, ct=A.FIN_CT, cr=A.FIN_CR):
    le = X["end"] - cr
    return [(le, R_OD), (le + xr, R_OD + s), (le + xr + ct, R_OD + s), (X["end"], R_OD),
            (X["tab_aft"], R_OD), (X["tab_aft"], R_OD - A.FIN_TAB_H), (X["tab_fwd"], R_OD - A.FIN_TAB_H),
            (X["tab_fwd"], R_OD)]


# ============================================================================ A-001 general arrangement
def sheet_ga(R):
    L = X["end"]
    sh = Sheet("ga", 1320, 470, "General arrangement side elevation of ASTRA-66 with module lengths, fin station, centre of gravity and centre of pressure")
    v = View(0, 60, 240, 1.0)
    oy = v.oy
    top = ogive_pts(v, 0, A.NC_L, 0, 1)
    bot = list(reversed(ogive_pts(v, 0, A.NC_L, 0, -1)))
    sh.poly(top + bot, "body")
    sh.rect(v.X(A.NC_L), v.Y(R_OD), (L - A.NC_L) * v.s, 2 * R_OD * v.s, "body")
    sh.rect(v.X(X["pl_end"]), v.Y(R_OD), A.AV_BAND_L * v.s, 2 * R_OD * v.s, "band")
    sh.line(v.X(A.NC_SPLIT), v.Y(A.ogive_r(A.NC_SPLIT)), v.X(A.NC_SPLIT), v.Y(-A.ogive_r(A.NC_SPLIT)), "ln thin")
    for sign in (1, -1):
        pts = [(v.X(x), v.Y(sign * r)) for x, r in fin_poly_st()[:4]]
        sh.poly(pts, "body")
    sh.rect(v.X(X["fin_le"]), v.Y(A.FIN_T / 2), A.FIN_CR * v.s, A.FIN_T * v.s, "ln thin")
    # rail buttons at 45 deg (projected), camera cowl at 270 deg, retainer phantom
    for st in (X["rb_fwd"], X["rb_aft"]):
        sh.rect(v.X(st) - 5, v.Y(R_OD * math.sin(math.radians(45))) - 4, 10, 8, "comp", rx=2)
    c = X["cam"]
    sh.poly([(v.X(c - 15), v.Y(-R_OD)), (v.X(c - 3), v.Y(-R_OD - 8)), (v.X(c + 20), v.Y(-R_OD - 8)), (v.X(c + 26), v.Y(-R_OD))], "body")
    sh.rect(v.X(L), v.Y(19), 22 * v.s, 38 * v.s, "ph")
    sh.centerline(v.X(-15), v.X(L + 40), oy)
    # CG / CP
    cg, cp = R["cg0"], R["bw"]["xcp"]
    cg_symbol(sh, v.X(cg), oy)
    cp_symbol(sh, v.X(cp), oy)
    sh.dim_h(v.X(cg), v.X(cp), oy + 112, f"STATIC MARGIN {R['sm0']:.2f} CAL  ({cp - cg:.0f})", oy + 12, oy + 12)
    sh.text(v.X(cg), oy + 60, f"CG {cg:.0f}", "tb", "middle")
    sh.text(v.X(cg), oy + 74, "liftoff, placeholder motor", "tm ts")
    sh.text(v.X(cp), oy + 60, f"CP {cp:.0f}", "tb ta")
    sh.text(v.X(cp), oy + 74, "Barrowman, subsonic", "tm ts")
    # chains
    y1, y2 = oy - 122, oy - 156
    ch = [(0, A.NC_L, "264  NOSE"), (A.NC_L, X["pl_end"], f"{fm(A.PL_L)}  PAYLOAD"), (X["pl_end"], X["band_end"], fm(A.AV_BAND_L)),
          (X["band_end"], L, f"{fm(A.BO_L)}  BOOSTER")]
    for a, b, lab in ch:
        sh.dim_h(v.X(a), v.X(b), y1, lab, v.Y(R_OD) if a > 0 else oy, v.Y(R_OD) if b < L else v.Y(R_OD))
    sh.dim_h(v.X(0), v.X(L), y2, f"{fm(L)}  OVERALL AIRFRAME (EXCL. COTS RETAINER)", None, None)
    sh.line(v.X(0), oy - 3, v.X(0), y2 - 5, "ext")
    sh.line(v.X(L), v.Y(R_OD) - 3, v.X(L), y2 - 5, "ext")
    sh.dim_h(v.X(0), v.X(X["fin_le"]), oy + 176, f"{fm(X['fin_le'])}  FIN ROOT LE", None, v.Y(-R_OD), below=True)
    sh.line(v.X(0), oy + 3, v.X(0), oy + 181, "ext")
    xr = v.X(L) + 44
    sh.dim_v(v.Y(R_OD), v.Y(-R_OD), xr, f"⌀{fm(A.BODY_OD)}", v.X(L), v.X(L), right=True)
    sh.dim_v(v.Y(R_OD + A.FIN_S), v.Y(R_OD), xr + 44, f"{fm(A.FIN_S)} SPAN", v.X(X['end'] - 20), v.X(L), right=True)
    sh.text(v.X(L) + 11, oy + 36, "BO-407", "ta ts")
    sh.text(v.X(L) + 11, oy + 48, "COTS", "ta ts")
    sh.leader(v.X(X["rb_fwd"]), v.Y(23), v.X(X["rb_fwd"]) - 40, oy - 70, "RAIL BUTTONS @45° (1010)", "end", "tm ts")
    sh.line(v.X(X["rb_aft"]), v.Y(23), v.X(X["rb_fwd"]) - 38, oy - 66, "ldr")
    sh.leader(v.X(c + 5), v.Y(-R_OD - 8), v.X(c + 5), oy + 104, "CAMERA COWL @270°", "middle", "tm ts")
    sh.leader(v.X(X["pl_end"] + 15), v.Y(R_OD - 6), v.X(X["pl_end"] + 15), oy - 70, "SWITCH BAND", "middle", "tm ts")
    sh.leader(v.X(A.NC_SPLIT), v.Y(A.ogive_r(A.NC_SPLIT) - 4), v.X(A.NC_SPLIT) + 30, oy - 70, "PRINT SPLIT", "middle", "tm ts")
    return sh


# ============================================================================ A-002 exploded
def sheet_exploded(R):
    s = 0.78
    sh = Sheet("ex", 1320, 650, "Exploded assembly of ASTRA-66 in two rows with part-number balloons; motor and retainer shown as external phantom components")
    gap = 36
    # ---------------- row 1
    oy = 150
    cx = 40
    up = True

    def bal(label, x0, length, dy=None, py_r=None):
        nonlocal up
        cxm = x0 + length * s / 2
        yy = oy - 92 if up else oy + 92
        pr = (py_r if py_r is not None else R_OD) * s
        sh.pill(cxm, yy, label, cxm, oy - pr if up else oy + pr)
        up = not up

    def Y(r):
        return oy - r * s

    # NC-101
    pts = [(cx + x * s, Y(A.ogive_r(x))) for x in [A.NC_SPLIT * i / 30 for i in range(31)]]
    rs = A.ogive_r(A.NC_SPLIT)
    sp = rs - A.NC_WALL - 0.15
    poly = pts + [(cx + A.NC_SPLIT * s, Y(sp)), (cx + (A.NC_SPLIT + 10) * s, Y(sp)), (cx + (A.NC_SPLIT + 10) * s, Y(-sp)),
                  (cx + A.NC_SPLIT * s, Y(-sp))] + [(x, 2 * oy - y) for x, y in reversed(pts)]
    sh.poly(poly, "body")
    bal("NC-101", cx, 160, py_r=12)
    cx += 160 * s + gap
    # NC-102
    x0 = cx - A.NC_SPLIT * s
    pts = [(x0 + x * s, Y(A.ogive_r(x))) for x in [A.NC_SPLIT + (A.NC_L - A.NC_SPLIT) * i / 20 for i in range(21)]]
    poly = pts + [(x0 + A.NC_L * s, Y(R_SH)), (x0 + X["sh_end"] * s, Y(R_SH)), (x0 + X["sh_end"] * s, Y(-R_SH)),
                  (x0 + A.NC_L * s, Y(-R_SH))] + [(x, 2 * oy - y) for x, y in reversed(pts)]
    sh.poly(poly, "body")
    bal("NC-102", cx, 174)
    cx += 174 * s + gap
    # NC-103/104
    sh.rect(cx, Y(3), 80 * s, 6 * s, "comp")
    sh.rect(cx + 80 * s, Y(R_SH - A.NC_SH_WALL), 6 * s, 2 * (R_SH - A.NC_SH_WALL) * s, "body")
    bal("NC-103/104", cx, 86, py_r=3)
    cx += 86 * s + gap
    # PL-201 + hatch + cowl/cradle
    sh.rect(cx, Y(R_OD), A.PL_L * s, 2 * R_OD * s, "body")
    hx = cx + (X["hatch"] - A.NC_L) * s
    sh.rect(hx - 22 * s, Y(R_OD + 30), 44 * s, 5, "comp", rx=2)
    sh.line(hx, Y(R_OD + 28), hx, Y(R_OD), "hid")
    sh.text(hx, Y(R_OD + 36), "PL-205/206", "tb ts")
    camx = cx + (X["cam"] - A.NC_L) * s
    sh.poly([(camx - 15 * s, Y(-R_OD - 26)), (camx - 3 * s, Y(-R_OD - 34)), (camx + 20 * s, Y(-R_OD - 34)), (camx + 26 * s, Y(-R_OD - 26))], "body")
    sh.rect(camx - 20 * s, Y(-R_OD - 42), 46 * s, 14, "comp", rx=2)
    sh.line(camx, Y(-R_OD - 26), camx, Y(-R_OD), "hid")
    sh.text(camx + 60, Y(-R_OD - 36), "PL-203/204", "tb ts", "start")
    sh.pill(cx + A.PL_L * s / 2 + 40, oy - 92, "PL-201", cx + A.PL_L * s / 2 + 40, Y(R_OD))
    up = False
    cx += A.PL_L * s + gap
    # PL-202 tray
    sh.rect(cx, Y(1.25), 90 * s, 2.5 * s + 1, "body")
    sh.rect(cx + 12 * s, Y(9), 40 * s, 7.5 * s, "comp")
    bal("PL-202", cx, 90, py_r=1.25)
    cx += 90 * s + gap
    # AV-303
    sh.rect(cx, Y(R_CO), 6 * s, 2 * R_CO * s, "body")
    sh.rect(cx + 6 * s, Y(R_CI - 0.1), 6 * s, 2 * (R_CI - 0.1) * s, "body")
    bal("AV-303", cx, 12)
    cx += 12 * s + gap
    # AV-301/302
    sh.rect(cx, Y(R_CO), A.AV_CPL_L * s, 2 * R_CO * s, "body")
    sh.rect(cx + A.AV_INS * s, Y(R_OD), A.AV_BAND_L * s, 2 * R_OD * s, "band")
    bal("AV-301/302", cx, A.AV_CPL_L)
    cx += A.AV_CPL_L * s + gap
    # AV-306 sled + rods
    sh.rect(cx, Y(1.5), A.SLED_L * s, 3 * s + 1, "body")
    for bx, bl, bh in ((10, 50, 8), (70, 14, 4), (88, 13, 4), (106, 28, 7)):
        sh.rect(cx + bx * s, Y(1.5 + bh), bl * s, bh * s, "comp")
    sh.rect(cx + 10 * s, Y(-1.5), 60 * s, 9 * s, "comp")
    sh.rect(cx - 25 * s, Y(R_OD + 18), 190 * s, 4 * s, "comp")
    sh.text(cx + 70 * s, Y(R_OD + 24), "AV-305 ×2", "tb ts")
    bal("AV-306", cx, A.SLED_L, py_r=-9)
    cx += A.SLED_L * s + gap
    # AV-304 + eyebolt
    sh.rect(cx, Y(R_CI - 0.1), 6 * s, 2 * (R_CI - 0.1) * s, "body")
    sh.rect(cx + 6 * s, Y(R_CO), 6 * s, 2 * R_CO * s, "body")
    sh.rect(cx + 12 * s, Y(3), 14 * s, 6 * s, "comp")
    sh.ellipse(cx + 34 * s, oy, 10 * s, 9 * s, "eye")
    sh.pill(cx + 21 * s, oy + 92, "AV-304/311", cx + 21 * s, Y(-R_CO))
    sh.text(20, 34, "ROW 1 — FORWARD SECTION (NOSE · PAYLOAD · AVIONICS)", "tl", "start")

    # ---------------- row 2
    oy = 470
    cx = 40
    up = True
    sh.text(20, 312, "ROW 2 — BOOSTER · RECOVERY · EXTERNAL MOTOR SYSTEM", "tl", "start")
    # recovery bundle
    sh.rect(cx, Y(24), 100 * s, 48 * s, "comp", rx=10)
    zz = [(cx + 100 * s + i * 5, oy + (6 if i % 2 else -6)) for i in range(11)]
    sh.poly(zz, "ln", closed=False)
    sh.pill(cx + 60 * s, oy - 92, "RC-501…505", cx + 50 * s, Y(24))
    cx += 150 * s + gap
    # booster tube + exploded fins
    x0 = cx - X["band_end"] * s
    sh.rect(cx, Y(R_OD), A.BO_L * s, 2 * R_OD * s, "body")
    sh.rect(x0 + X["fin_le"] * s, Y(A.FIN_T / 2 + 0.3), A.FIN_CR * s, (A.FIN_T + 0.6) * s, "ln thin")
    for sign in (1, -1):
        off = 48
        pts = [(x0 + st * s, oy - sign * (r + off) * s) for st, r in fin_poly_st()]
        sh.poly(pts, "body")
        sh.line(x0 + (X["fin_le"] + 75) * s, oy - sign * (R_OD - A.FIN_TAB_H + off) * s, x0 + (X["fin_le"] + 75) * s, oy - sign * R_OD * s, "hid")
    sh.pill(x0 + (X["fin_le"] + 75) * s, oy - 150, "BO-406 ×4", x0 + (X["fin_le"] + 100) * s, oy - (R_OD + 48 + 40) * s)
    for st in (X["rb_fwd"], X["rb_aft"]):
        sh.rect(x0 + st * s - 4, Y(R_OD) - 6, 8, 6, "comp", rx=1.5)
    sh.pill(cx + 300 * s, oy - 92, "BO-401", cx + 300 * s, Y(R_OD))
    sh.pill(x0 + X["rb_fwd"] * s, oy + 92, "BO-408/409", x0 + X["rb_fwd"] * s, Y(R_OD) - 6)
    cx += A.BO_L * s + gap
    # BO-404
    sh.rect(cx, Y(R_SH), 6 * s, (R_SH - R_MO) * s, "body")
    sh.rect(cx, Y(-R_MO), 6 * s, (R_SH - R_MO) * s, "body")
    sh.pill(cx + 3 * s, oy + 150, "BO-404/410", cx + 3 * s, Y(-R_SH))
    cx += 6 * s + gap
    # MMT
    sh.rect(cx, Y(R_MO), A.MMT_L * s, 2 * R_MO * s, "body")
    sh.pill(cx + 130 * s, oy - 92, "BO-402", cx + 130 * s, Y(R_MO))
    cx += A.MMT_L * s + gap
    # core
    cl = X["core_aft"] - X["core_fwd"]
    sh.rect(cx, Y(R_SH), A.CORE_RING_T * s, (R_SH - R_MO) * s, "body")
    sh.rect(cx, Y(-R_MO), A.CORE_RING_T * s, (R_SH - R_MO) * s, "body")
    sh.rect(cx + (cl - A.CORE_RING_T) * s, Y(R_SH), A.CORE_RING_T * s, (R_SH - R_MO) * s, "body")
    sh.rect(cx + (cl - A.CORE_RING_T) * s, Y(-R_MO), A.CORE_RING_T * s, (R_SH - R_MO) * s, "body")
    for r in (R_SH - 3, R_MO + 3, -(R_SH - 3), -(R_MO + 3)):
        sh.line(cx + A.CORE_RING_T * s, Y(r), cx + (cl - A.CORE_RING_T) * s, Y(r), "ln thin")
    sh.pill(cx + cl * s / 2, oy + 92, "BO-403", cx + cl * s / 2, Y(-R_SH))
    cx += cl * s + gap
    # lock ring
    sh.rect(cx, Y(R_SH), 6 * s, (R_SH - A.RET_CLEAR_D / 2) * s, "body")
    sh.rect(cx, Y(-A.RET_CLEAR_D / 2), 6 * s, (R_SH - A.RET_CLEAR_D / 2) * s, "body")
    sh.pill(cx + 3 * s, oy - 92, "BO-405", cx + 3 * s, Y(R_SH))
    cx += 6 * s + gap
    # retainer + motor phantoms
    sh.rect(cx, Y(19), 22 * s, 38 * s, "ph")
    sh.pill(cx + 11 * s, oy + 92, "BO-407 COTS", cx + 11 * s, Y(-19))
    cx += 22 * s + gap
    sh.rect(cx, Y(R_MI), A.MOTOR_L * s, 2 * R_MI * s, "ph")
    sh.text(cx + A.MOTOR_L * s / 2, oy + 4, "MT-601", "ta tb ts")
    sh.text(cx + A.MOTOR_L * s / 2, oy - 40, "CERTIFIED MOTOR", "ta tb ts")
    sh.text(cx + A.MOTOR_L * s / 2, oy - 27, "EXTERNAL · NOT DESIGNED", "ta ts")
    sh.centerline(20, 1300, 150)
    sh.centerline(20, 1300, 470)
    return sh


# ============================================================================ avionics bay geometry (shared)
def draw_av(sh, v, x_end=640):
    tube_walls(sh, v, A.NC_L, X["pl_end"], R_ID, R_OD, "h1")
    tube_walls(sh, v, X["pl_end"], X["band_end"], R_ID, R_OD, "h1", gaps_top=[(526, 532)], gaps_bot=[(528, 530.5)])
    tube_walls(sh, v, X["band_end"], x_end, R_ID, R_OD, "h1")
    tube_walls(sh, v, X["cpl_fwd"], X["cpl_aft"], R_CI, R_CO, "h2", gaps_top=[(526, 532)], gaps_bot=[(528, 530.5)])
    for s_ in (1, -1):
        sh.line(v.X(X["pl_end"]), v.Y(s_ * R_ID), v.X(X["pl_end"]), v.Y(s_ * R_OD), "ln")
        sh.line(v.X(X["band_end"]), v.Y(s_ * R_ID), v.X(X["band_end"]), v.Y(s_ * R_OD), "ln")
    b = X["av_bh_fwd_outer"]
    sh.rect(v.X(b), v.Y(R_CO), 6 * v.s, 2 * R_CO * v.s, "cut", "h1")
    sh.rect(v.X(b + 6), v.Y(R_CI - 0.1), 6 * v.s, 2 * (R_CI - 0.1) * v.s, "cut", "h2")
    sh.rect(v.X(b - 1), v.Y(16), 14 * v.s, 6 * v.s, "comp", rx=1)
    a = X["cpl_aft"]
    sh.rect(v.X(a - 6), v.Y(R_CI - 0.1), 6 * v.s, 2 * (R_CI - 0.1) * v.s, "cut", "h2")
    sh.rect(v.X(a), v.Y(R_CO), 6 * v.s, 2 * R_CO * v.s, "cut", "h1")
    sh.rect(v.X(a - 7.5), v.Y(R_CI - 0.1), 1.5 * v.s, 2 * (R_CI - 0.1) * v.s, "comp")
    # rods (in sled plane, behind section) + nuts
    sh.rect(v.X(b + 2), v.Y(2), (a + 12 - b - 2) * v.s, 4 * v.s, "comp")
    sh.rect(v.X(a + 6), v.Y(3.5), 4 * v.s, 7 * v.s, "ln")
    # sled + modules
    sh.rect(v.X(X["sled_fwd"]), v.Y(1.5), A.SLED_L * v.s, 3 * v.s, "cut", "h2")
    sf = X["sled_fwd"]
    mods_top = [(11, 50, 8.5, "MCU"), (69, 14, 4, ""), (88, 13, 4, ""), (107, 28, 7, "")]
    for bx, bl, bh, lab in mods_top:
        sh.rect(v.X(sf + bx), v.Y(1.5 + bh), bl * v.s, bh * v.s, "comp")
    sh.rect(v.X(sf + 11), v.Y(-1.5), 60 * v.s, 10 * v.s, "comp")
    sh.rect(v.X(sf + 83), v.Y(-1.5), 26 * v.s, 4.5 * v.s, "comp")
    # switch
    sh.rect(v.X(523), v.Y(28), 12 * v.s, 16 * v.s, "comp")
    sh.rect(v.X(527), v.Y(33), 4 * v.s, 5 * v.s, "ln thin")
    # eyebolt
    sh.rect(v.X(a - 12), v.Y(3), (30) * v.s, 6 * v.s, "comp")
    sh.rect(v.X(a - 12), v.Y(5), 5 * v.s, 10 * v.s, "ln")
    sh.ellipse(v.X(a + 27), v.oy, 9 * v.s, 8 * v.s, "eye")


def sheet_section_fwd(R):
    sh = Sheet("sa", 1380, 600, "Longitudinal section A-A of the forward airframe: nose cone, payload bay with camera and GPS tray, and avionics bay with sled and bulkheads")
    v = View(0, 50, 285, 2.0)
    oy = v.oy
    nose_wall(sh, v, 1)
    nose_wall(sh, v, -1)
    # bosses + radial screw (top), lugs, bulkhead, ballast
    st = X["nc_screws"]
    sh.rect(v.X(st - 5), v.Y(R_SH - A.NC_SH_WALL), 10 * v.s, -3 * v.s, "cut", "h2")
    sh.rect(v.X(st - 1.6), v.Y(R_OD), 3.2 * v.s, (R_OD - R_SH + A.NC_SH_WALL + 3) * v.s, "comp")
    bh = X["sh_end"] - A.NC_BH_T
    sh.rect(v.X(bh), v.Y(R_SH - A.NC_SH_WALL - 0.1), A.NC_BH_T * v.s, 2 * (R_SH - A.NC_SH_WALL - 0.1) * v.s, "cut", "h2")
    sh.rect(v.X(bh - A.NC_LUG_L), v.Y(R_SH - A.NC_SH_WALL), A.NC_LUG_L * v.s, A.NC_LUG_T * v.s, "cut", "h1")
    sh.rect(v.X(X["sh_end"] - A.BALLAST_ROD_L), v.Y(3), (A.BALLAST_ROD_L + 6) * v.s, 6 * v.s, "comp")
    for nx in (X["sh_end"] - A.BALLAST_ROD_L + 2, X["sh_end"]):
        sh.rect(v.X(nx), v.Y(5), 5 * v.s, 10 * v.s, "ln")
    sh.rect(v.X(X["sh_end"] - A.BALLAST_ROD_L + 8), v.Y(10), 10 * v.s, 20 * v.s, "ph")
    # payload tube (with hatch & lens gaps) is drawn in draw_av from NC_L; add gaps by redrawing
    h0, h1 = X["hatch"] - 20, X["hatch"] + 20
    c = X["cam"]
    tube_walls(sh, v, A.NC_L, X["pl_end"], R_ID, R_OD, "h1", gaps_top=[(h0, h1)], gaps_bot=[(c - 7, c + 7)])
    draw_av_no_pl(sh, v)
    sh.rect(v.X(h0 + 0.5), v.Y(R_OD), 39 * v.s, 1 * v.s, "cut", "h2")
    sh.rect(v.X(h0 - 6), v.Y(R_ID), 6 * v.s, 2 * v.s, "cut", "h2")
    sh.rect(v.X(h1), v.Y(R_ID), 6 * v.s, 2 * v.s, "cut", "h2")
    # camera
    sh.rect(v.X(c - 25), v.Y(-R_ID), 55 * v.s, 20 * v.s, "ln thin")
    sh.rect(v.X(c - 20), v.Y(-14), 45 * v.s, -16 * v.s, "comp")
    sh.rect(v.X(c - 5), v.Y(-30), 10 * v.s, -3 * v.s, "comp")
    sh.poly([(v.X(c - 15), v.Y(-R_OD)), (v.X(c - 3), v.Y(-R_OD - 8)), (v.X(c + 20), v.Y(-R_OD - 8)), (v.X(c + 26), v.Y(-R_OD))], "cut", "h2")
    # tray + GPS
    t0 = X["tray_fwd"]
    sh.rect(v.X(t0), v.Y(A.TRAY_T / 2), (A.TRAY_L - A.TRAY_FOOT_T) * v.s, A.TRAY_T * v.s, "cut", "h2")
    sh.rect(v.X(X["av_bh_fwd_outer"] - A.TRAY_FOOT_T), v.Y(6), A.TRAY_FOOT_T * v.s, 26 * v.s, "cut", "h1")
    sh.rect(v.X(t0 + 12), v.Y(8), 40 * v.s, 6.75 * v.s, "comp")
    sh.rect(v.X(t0 + 17), v.Y(12), 25 * v.s, 4 * v.s, "comp")
    sh.centerline(v.X(-8), v.X(645), oy)

    # leaders ------------------------------------------------------------------
    T1, T2, B1, B2 = oy - 118, oy - 146, oy + 124, oy + 152
    L = sh.leader
    L(v.X(90), v.Y(A.ogive_r(90) - 0.6), v.X(70), T2, "NC-101 WALL 1.2", "middle", "ts")
    L(v.X(A.NC_SPLIT + 4), v.Y(A.ogive_r(A.NC_SPLIT) - 2), v.X(175), T1, "SPIGOT BOND JOINT", "middle", "ts")
    L(v.X(285), v.Y(R_SH - 0.8), v.X(250), T2, "NC-102 SHOULDER", "middle", "ts")
    L(v.X(st), v.Y(R_OD + 0.5), v.X(335), T1, "M3 × 8 + INSERT", "middle", "ts")
    L(v.X(bh + 3), v.Y(20), v.X(415), T2, "NC-103 BULKHEAD", "middle", "ts")
    L(v.X(X["hatch"]), v.Y(R_OD), v.X(X["hatch"] + 10), T1, "PL-205 HATCH", "middle", "ts")
    L(v.X(t0 + 30), v.Y(12), v.X(X["tray_fwd"] + 132), T2 + 0, "PL-202 GPS TRAY", "middle", "ts")
    L(v.X(X["av_bh_fwd_outer"] + 3), v.Y(25), v.X(X["av_bh_fwd_outer"] + 70), T1, "AV-303 (BONDED)", "middle", "ts")
    L(v.X(X["av_bh_fwd_outer"] + 5), v.Y(13), v.X(X["av_bh_fwd_outer"] + 140), T2, "HARNESS GROMMET", "middle", "ts")
    L(v.X(529), v.Y(22), v.X(560), T1, "AV-307 SWITCH", "middle", "ts")
    L(v.X(X["sled_fwd"] + 30), v.Y(8), v.X(X["sled_fwd"] + 170), T2, "MCU · IMU · BARO · RADIO", "middle", "ts")
    L(v.X(X["cpl_aft"] + 3), v.Y(28), v.X(650), T1, "AV-304 (REMOVABLE)", "middle", "ts")
    L(v.X(X["cpl_aft"] + 27), v.Y(8), v.X(680), T2, "AV-311 M6 EYEBOLT", "end", "ts")

    L(v.X(X["sh_end"] - 60), v.Y(-3), v.X(200), B1, "NC-104 BALLAST ROD", "middle", "ts")
    L(v.X(X["sh_end"] - 67), v.Y(-10), v.X(120), B2, "OPTIONAL BALLAST WASHERS", "middle", "ts")
    L(v.X(c), v.Y(-20), v.X(300), B2, "PL-203 CAMERA CRADLE", "middle", "ts")
    L(v.X(c + 10), v.Y(-R_OD - 8), v.X(395), B1, "PL-204 LENS COWL", "middle", "ts")
    L(v.X(X["sled_fwd"] + 40), v.Y(-8), v.X(470), B2, "AV-308 BATTERY CAGE", "middle", "ts")
    L(v.X(X["sled_fwd"] + 3), v.Y(-3), v.X(X["sled_fwd"] + 60), B1, "AV-312 SPACERS", "middle", "ts")
    L(v.X(529), v.Y(-R_OD + 0.5), v.X(610), B2, "STATIC PORTS @45° (NOT IN PLANE)", "middle", "ts")
    L(v.X(X["cpl_aft"] - 20), v.Y(-R_CO + 0.5), v.X(660), B1, "AV-301 COUPLER", "middle", "ts")
    L(v.X(X["sled_fwd"] + 130), v.Y(-1.5), v.X(X["sled_fwd"] + 190), B2 + 26, "AV-306 SLED / AV-305 RODS (BEHIND)", "middle", "ts")

    # dims ---------------------------------------------------------------------
    Dy = oy + 205
    sh.dim_h(v.X(A.NC_L), v.X(X["sh_end"]), Dy, fm(A.NC_SH_L), v.Y(-R_OD), v.Y(-R_OD))
    sh.dim_h(v.X(X["sh_end"]), v.X(X["av_bh_fwd_outer"]), Dy, f"{fm(A.PAYLOAD_BAY_CLEAR)} PAYLOAD BAY CLEAR", None, v.Y(-R_CO))
    sh.dim_h(v.X(X["cpl_fwd"]), v.X(X["cpl_aft"]), Dy + 34, f"{fm(A.AV_CPL_L)} AV-301", v.Y(-R_CO), v.Y(-R_CO))
    sh.dim_h(v.X(X["cpl_fwd"]), v.X(X["pl_end"]), Dy, fm(A.AV_INS), None, v.Y(-R_OD))
    sh.dim_h(v.X(X["band_end"]), v.X(X["cpl_aft"]), Dy, fm(A.AV_INS), v.Y(-R_OD), None)
    sh.dim_h(v.X(0), v.X(A.NC_L), Dy + 34, fm(A.NC_L), oy, v.Y(-R_OD))
    sh.title(18, 28, "SECTION A-A · FORWARD AIRFRAME · STA 0–640", "Cutting plane through 90°/270° (hatch and camera). Rods lie in the sled plane, shown behind.")
    return sh


def draw_av_no_pl(sh, v):
    """Avionics bay without re-hatching the payload tube (used when the tube has cut-outs)."""
    # draw band, booster stub, coupler, bulkheads, sled (static ports are at 45 deg: not in this plane)
    sw0, sw1 = X["pl_end"] + A.AV_BAND_L / 2 - A.SW_HOLE_D / 2, X["pl_end"] + A.AV_BAND_L / 2 + A.SW_HOLE_D / 2
    tube_walls(sh, v, X["pl_end"], X["band_end"], R_ID, R_OD, "h1", gaps_top=[(sw0, sw1)])
    tube_walls(sh, v, X["band_end"], 640, R_ID, R_OD, "h1")
    tube_walls(sh, v, X["cpl_fwd"], X["cpl_aft"], R_CI, R_CO, "h2", gaps_top=[(sw0, sw1)])
    _av_internals(sh, v)


def _av_internals(sh, v):
    for s_ in (1, -1):
        sh.line(v.X(X["pl_end"]), v.Y(s_ * R_ID), v.X(X["pl_end"]), v.Y(s_ * R_OD), "ln")
        sh.line(v.X(X["band_end"]), v.Y(s_ * R_ID), v.X(X["band_end"]), v.Y(s_ * R_OD), "ln")
    b = X["av_bh_fwd_outer"]
    a = X["cpl_aft"]
    g = A.GASKET_T
    ao = X["av_bh_aft_outer"]                                  # AV-304 aft face (rev B: + gasket)
    sw = X["pl_end"] + A.AV_BAND_L / 2
    sh.rect(v.X(b), v.Y(2), A.ROD_L * v.s, 4 * v.s, "comp")    # AV-305 rod (behind, in sled plane)
    for z0, z1 in ((b + 2 * A.AV_BH_T, X["sled_fwd"]), (X["sled_aft"], a + g - A.AV_BH_T)):
        sh.rect(v.X(z0), v.Y(3.75), (z1 - z0) * v.s, 7.5 * v.s, "comp")   # AV-312 spacers
    sh.rect(v.X(b), v.Y(R_CO), 6 * v.s, 2 * R_CO * v.s, "cut", "h1")
    sh.rect(v.X(b + 6), v.Y(R_CI - 0.1), 6 * v.s, 2 * (R_CI - 0.1) * v.s, "cut", "h2")
    sh.rect(v.X(b - 1), v.Y(A.HARNESS_Y + A.HARNESS_D / 2), 14 * v.s, A.HARNESS_D * v.s, "comp", rx=1)
    sh.rect(v.X(a + g - 6), v.Y(R_CI - 0.1), 6 * v.s, 2 * (R_CI - 0.1) * v.s, "cut", "h2")
    sh.rect(v.X(a + g), v.Y(R_CO), 6 * v.s, 2 * R_CO * v.s, "cut", "h1")
    for s_ in (1, -1):                                          # AV-309 face gasket on the coupler end
        sh.rect(v.X(a), v.Y(s_ * R_CO), g * v.s, s_ * (R_CO - R_CI) * v.s, "comp")
    sh.rect(v.X(ao), v.Y(3.5), (A.WASHER_M4_T + A.NUT_M4_H) * v.s, 7 * v.s, "ln")
    sf = X["sled_fwd"]
    sh.rect(v.X(sf), v.Y(1.5), A.SLED_L * v.s, 3 * v.s, "cut", "h2")
    for bx, bl, bh in ((11, 50, 8.5), (83, 26, 4.5), (111, 28, 7)):
        sh.rect(v.X(sf + bx), v.Y(9.5 + bh), bl * v.s, bh * v.s, "comp")
    cage_d = 2 + A.BAT_H + 0.4
    sh.rect(v.X(sf + 2), v.Y(-1.5), (12 + A.BAT_L + 0.6) * v.s, cage_d * v.s, "ln")                 # AV-308 cage
    sh.rect(v.X(sf + 8.3), v.Y(-3.7), A.BAT_L * v.s, A.BAT_H * v.s, "comp")                          # battery
    sh.rect(v.X(sw - 6), v.Y(1.5 + A.SW_TOWER_H), 12 * v.s, A.SW_TOWER_H * v.s, "cut", "h1")        # switch tower
    sh.rect(v.X(sw - 6), v.Y(R_CI - 1), 12 * v.s, (R_CI - 1 - 1.5 - A.SW_TOWER_H) * v.s, "comp")    # switch (USER)
    sh.rect(v.X(a + g - 12), v.Y(3), 30 * v.s, 6 * v.s, "comp")
    sh.rect(v.X(a + g - 6 - 7.6), v.Y(9), 7.6 * v.s, 18 * v.s, "ln")
    sh.ellipse(v.X(ao + 21), v.oy, 9 * v.s, 8 * v.s, "eye")


# ============================================================================ A-004 aft section
def sheet_section_aft(R):
    sh = Sheet("sb", 1060, 800, "Longitudinal section B-B of the fin can: motor mount tube, centering ring, printed fin-can core, slide-in fins, aft lock ring and the parameterised motor and retainer envelopes")
    x0 = 858
    v = View(x0, 40, 400, 2.5)
    oy = v.oy
    fe = X["end"]
    tube_walls(sh, v, x0, X["tab_fwd"], R_ID, R_OD, "h1")          # rev B: slot starts at the tab front
    for s_ in (1, -1):
        sh.line(v.X(X["tab_fwd"]), v.Y(s_ * R_ID), v.X(fe), v.Y(s_ * R_ID), "ln thin")
        sh.rect(v.X(X["core_fwd"]), v.Y(s_ * A.R_TAB_FLOOR), (X["core_aft"] - X["core_fwd"]) * v.s,
                s_ * (A.R_TAB_FLOOR - R_MO - A.FIT_SH / 2) * v.s, "cut", "h2")   # BO-403 tab floor (in plane)
    tube_walls(sh, v, X["mmt_fwd"], X["mmt_aft"], R_MI, R_MO, "h2")
    for s_ in (1, -1):
        sh.rect(v.X(X["mmt_fwd"]), v.Y(s_ * R_SH), A.CR_T * v.s, s_ * (R_SH - R_MO) * v.s, "cut", "h1")
        sh.rect(v.X(X["core_fwd"]), v.Y(s_ * R_SH), A.CORE_RING_T * v.s, s_ * (R_SH - R_MO) * v.s, "cut", "h1")
        sh.rect(v.X(X["core_aft"] - A.CORE_RING_T), v.Y(s_ * R_SH), A.CORE_RING_T * v.s, s_ * (R_SH - R_MO) * v.s, "hid")
        sh.rect(v.X(X["tab_fwd"]), v.Y(s_ * R_SH), (X["core_aft"] - A.CORE_RING_T - X["tab_fwd"]) * v.s, s_ * (R_SH - R_MO) * v.s, "hid")
        pts = [(v.X(st), v.Y(s_ * r)) for st, r in fin_poly_st()]
        sh.poly(pts, "cut", "h3")
        sh.rect(v.X(fe - A.LOCK_T), v.Y(s_ * R_SH), A.LOCK_T * v.s, s_ * (R_SH - A.RET_CLEAR_D / 2) * v.s, "cut", "h2")
        # epoxy fillets
        for fx in (X["mmt_fwd"], X["mmt_fwd"] + A.CR_T, X["core_fwd"]):
            sh.poly([(v.X(fx), v.Y(s_ * R_MO)), (v.X(fx + (3 if fx != X["mmt_fwd"] else -3)), v.Y(s_ * R_MO)),
                     (v.X(fx), v.Y(s_ * (R_MO + 3)))], "cgf")
    # kevlar leader
    kz = [(v.X(X["mmt_fwd"] + A.CR_T + 4 + i * 6), v.Y(R_MO + 1.5 + (1.2 if i % 2 else 0))) for i in range(15)]
    sh.poly(kz, "arrowacc", closed=False)
    sh.path(f"M{v.X(X['mmt_fwd'] + A.CR_T + 4):.1f},{v.Y(R_MO + 1.5):.1f} C{v.X(X['mmt_fwd'] - 8):.1f},{v.Y(R_MO + 6):.1f} "
            f"{v.X(X['mmt_fwd'] - 10):.1f},{v.Y(25):.1f} {v.X(x0 + 6):.1f},{v.Y(22):.1f}", "arrowdim")
    # phantoms
    sh.rect(v.X(X["motor_fwd"]), v.Y(R_MI - 0.3), A.MOTOR_L * v.s, 2 * (R_MI - 0.3) * v.s, "ph")
    sh.rect(v.X(fe), v.Y(19), 22 * v.s, 38 * v.s, "ph")
    sh.centerline(v.X(x0 - 4), v.X(fe + 30), oy)

    # labels (left zone)
    lx = v.X(x0) + 4
    L = sh.leader
    L(v.X(x0 + 12), v.Y(R_OD - 0.5), lx + 4, oy - 250, "BO-401 BOOSTER TUBE", "start", "ts")
    L(v.X(X["mmt_fwd"] + 3), v.Y(26), lx + 4, oy - 222, "BO-404 FWD CENTERING RING (PLY)", "start", "ts")
    L(v.X(X["mmt_fwd"] + 40), v.Y(R_MO + 2), lx + 4, oy - 194, "BO-410 ARAMID LEADER, BONDED", "start", "ts")
    L(v.X(x0 + 20), v.Y(22), lx + 4, oy - 166, "→ SHOCK CORD / RECOVERY BAY", "start", "ts")
    L(v.X(X["core_fwd"] + 4), v.Y(26), v.X(X["core_fwd"]) + 20, oy - 290, "BO-403 CORE FWD RING = FIN STOP", "middle", "ts")
    L(v.X(X["mmt_fwd"] + 20), v.Y(-R_MO + 0.5), lx + 4, oy + 170, "BO-402 MOTOR MOUNT TUBE", "start", "ts")
    L(v.X(X["motor_fwd"] + 20), v.Y(-R_MI + 2), lx + 4, oy + 198, "MT-601 MOTOR ENVELOPE — EXTERNAL, PER MFR", "start", "ta ts")
    L(v.X(fe + 11), v.Y(-19), v.X(fe) - 4, oy + 226, "BO-407 COTS RETAINER — PER MFR", "end", "ta ts")
    L(v.X(fe - 3), v.Y(-27), v.X(fe) - 20, oy + 254, "BO-405 LOCK RING, 4× M3", "end", "ts")
    L(v.X(X["tab_fwd"] + 60), v.Y(-22), lx + 4, oy + 226, "BO-406 FIN TAB (SLIDE-IN)", "start", "ts")
    L(v.X(X["tab_fwd"] + 30), v.Y(-R_SH + 3), lx + 4, oy + 254, "GUIDE RAILS (BEHIND TAB)", "start", "ts")
    L(v.X(X["tab_fwd"] + 90), v.Y(-(A.R_TAB_FLOOR - 1)), lx + 4, oy + 282, "BO-403 TAB FLOOR (TAB CLEARS RETAINER)", "start", "ts")

    # dims
    top = v.Y(R_OD + A.FIN_S)
    le = X["fin_le"]
    sh.dim_h(v.X(le), v.X(le + A.FIN_XR), top - 24, fm(A.FIN_XR), v.Y(R_OD), top)
    sh.dim_h(v.X(le + A.FIN_XR), v.X(le + A.FIN_XR + A.FIN_CT), top - 24, fm(A.FIN_CT), None, top)
    sh.dim_h(v.X(le), v.X(fe), top - 56, f"{fm(A.FIN_CR)} ROOT CHORD", None, v.Y(R_OD))
    sh.line(v.X(le), v.Y(R_OD) - 3, v.X(le), top - 61, "ext")
    sh.dim_h(v.X(X["core_fwd"]), v.X(X["core_aft"]), top - 88, f"{fm(X['core_aft'] - X['core_fwd'])} BO-403", v.Y(R_SH), v.Y(R_SH))
    bot = v.Y(-(R_OD + A.FIN_S))
    sh.dim_h(v.X(X["tab_fwd"]), v.X(X["tab_aft"]), bot + 30, f"{fm(A.FIN_TAB_L)} TAB", v.Y(-(R_OD - A.FIN_TAB_H)), v.Y(-(R_OD - A.FIN_TAB_H)), below=True)
    sh.dim_h(v.X(fe - A.LOCK_T), v.X(fe), bot + 30, fm(A.LOCK_T), None, v.Y(-R_OD), below=True)
    sh.dim_h(v.X(X["mmt_fwd"]), v.X(X["mmt_aft"]), bot + 64, f"{fm(A.MMT_L)} [MMT_L] — MIN. PER MOTOR MFR", v.Y(-R_MO), v.Y(-R_MO), below=True)
    sh.dim_h(v.X(X["motor_fwd"]), v.X(X["motor_aft"]), bot + 98, f"[MOTOR_L] PLACEHOLDER {fm(A.MOTOR_L)}", v.Y(-R_MI), None, below=True)
    sh.line(v.X(X["motor_aft"]), v.Y(-R_MI) + 3, v.X(X["motor_aft"]), bot + 103, "ext")
    xr = v.X(fe + 22) + 40
    sh.dim_v(v.Y(R_OD + A.FIN_S), v.Y(R_OD), xr, f"{fm(A.FIN_S)} SPAN", v.X(le + A.FIN_XR + A.FIN_CT), v.X(fe), right=True)
    sh.dim_v(v.Y(-(R_OD - A.FIN_TAB_H)), v.Y(-R_OD), xr, f"{fm(A.FIN_TAB_H)} TAB", v.X(X["tab_aft"]), v.X(fe), right=True)
    sh.dim_v(v.Y(R_MO), v.Y(-R_MO), xr + 50, f"⌀{fm(A.MMT_OD)} MMT", v.X(X["mmt_aft"]), v.X(X["mmt_aft"]), right=True)
    sh.title(18, 28, "SECTION B-B · FIN CAN & MOTOR INTERFACE · STA 858–1170", "Plane through fins 1 & 3. Orange dash-dot = external certified components; final dimensions from manufacturer documents.")
    return sh


# ============================================================================ A-005 fin + section C-C
def sheet_fin(R):
    sh = Sheet("fn", 1300, 680, "Fin flat pattern with dimensions and section C-C through the fin can showing four slide-in fins, guide rails, tube slots and rail button position")
    s = 3.0
    ox, oy = 70, 300

    def P(u, w):
        return ox + u * s, oy - w * s
    pts = [(0, 0), (A.FIN_XR, A.FIN_S), (A.FIN_XR + A.FIN_CT, A.FIN_S), (A.FIN_CR, 0), (A.FIN_CR - A.LOCK_T, 0),
           (A.FIN_CR - A.LOCK_T, -A.FIN_TAB_H), (A.FIN_TAB_FWD, -A.FIN_TAB_H), (A.FIN_TAB_FWD, 0)]
    sh.poly([P(*p_) for p_ in pts], "body")
    sh.line(*P(-8, 0), *P(A.FIN_CR + 8, 0), "ctr")
    sh.text(*P(A.FIN_CR / 2 + 20, 4), "ROOT LINE = TUBE OD", "tm ts")
    for i in range(5):
        u = 25 + i * 22
        sh.line(*P(u, 8), *P(u + 14, 8), "hid")
    sh.text(*P(68, 12), "OUTER-PLY GRAIN ∥ ROOT", "tm ts")
    sh.dim_h(*P(0, 0)[0:1], P(A.FIN_XR, 0)[0], P(0, A.FIN_S)[1] - 26, fm(A.FIN_XR), P(0, 0)[1], P(0, A.FIN_S)[1])
    sh.dim_h(P(A.FIN_XR, 0)[0], P(A.FIN_XR + A.FIN_CT, 0)[0], P(0, A.FIN_S)[1] - 26, fm(A.FIN_CT), None, P(0, A.FIN_S)[1])
    yb = P(0, -A.FIN_TAB_H)[1]
    sh.dim_h(P(0, 0)[0], P(A.FIN_CR, 0)[0], yb + 36, f"{fm(A.FIN_CR)} ROOT CHORD", P(0, 0)[1], P(0, 0)[1], below=True)
    sh.dim_h(P(0, 0)[0], P(A.FIN_TAB_FWD, 0)[0], yb + 18, fm(A.FIN_TAB_FWD), None, yb)
    sh.dim_h(P(A.FIN_TAB_FWD, 0)[0], P(A.FIN_CR - A.LOCK_T, 0)[0], yb + 74, f"{fm(A.FIN_TAB_L)} TAB", yb, yb, below=True)
    sh.dim_h(P(A.FIN_CR - A.LOCK_T, 0)[0], P(A.FIN_CR, 0)[0], yb + 18, fm(A.LOCK_T), None, None)
    sh.dim_v(P(0, A.FIN_S)[1], P(0, 0)[1], P(A.FIN_CR, 0)[0] + 40, f"{fm(A.FIN_S)} SPAN", P(A.FIN_XR + A.FIN_CT, 0)[0], P(A.FIN_CR, 0)[0], right=True)
    sh.dim_v(P(0, 0)[1], yb, P(0, 0)[0] - 18, f"{fm(A.FIN_TAB_H)}", P(A.FIN_TAB_FWD, 0)[0], P(A.FIN_TAB_FWD, 0)[0])
    sweep = math.degrees(math.atan(A.FIN_XR / A.FIN_S))
    sh.text(*P(22, 36), f"Λ LE {sweep:.1f}°", "td")
    sh.title(18, 28, f"BO-406 FIN · FLAT PATTERN · QTY {A.FIN_N} + 1 SPARE", "3 mm aircraft birch ply (baseline) · drawn 3×")
    # edge profile detail
    ex, ey = 70, 540
    sh.text(ex, ey - 40, "DETAIL D — EDGE PROFILE (8×)", "tb ts", "start")
    sh.rect(ex, ey - 12, 380, 24, "body", rx=12)
    sh.text(ex + 190, ey + 4, f"t = {fm(A.FIN_T)}", "ts")
    sh.leader(ex + 4, ey, ex - 10, ey + 44, "LE: FULL RADIUS R1.5", "start", "ts")
    sh.leader(ex + 376, ey, ex + 390, ey + 44, "TE: FULL RADIUS R1.5", "end", "ts")
    notes = ["PROFILE TOL ±0.3 · TAB HEIGHT +0/−0.2 (TAB ROOT ON BO-403 TAB FLOOR)",
             "TAB THICKNESS = SHEET; CHECK FIT IN GUIDE SLOT (FIN_T + 0.2)",
             "SEAL ALL EDGES (THIN EPOXY) BEFORE PRIMER; NO FILLETS ON TAB"]
    for i, n in enumerate(notes):
        sh.text(ex, ey + 80 + i * 17, n, "tm ts", "start")

    # ---- section C-C
    cx, cy, k = 960, 330, 3.0
    st = X["fin_le"] + 66
    r_le = A.R_LE = R_OD + A.FIN_S * (st - X["fin_le"]) / A.FIN_XR if st - X["fin_le"] < A.FIN_XR else R_OD + A.FIN_S
    sh.title(700, 28, f"SECTION C-C · STA {fm(st)} · LOOKING FORWARD", "drawn 3× · fins 1–4 at 0/90/180/270° · rail at 45°")

    def pol(r, ang):
        a = math.radians(ang)
        return cx + r * k * math.cos(a), cy - r * k * math.sin(a)

    def sector(r0, r1, a0, a1, cls, hatch):
        p0, p1 = pol(r1, a0), pol(r1, a1)
        p2, p3 = pol(r0, a1), pol(r0, a0)
        large = 1 if (a1 - a0) > 180 else 0
        d = (f"M{p0[0]:.1f},{p0[1]:.1f} A{r1 * k:.1f},{r1 * k:.1f} 0 {large} 0 {p1[0]:.1f},{p1[1]:.1f} "
             f"L{p2[0]:.1f},{p2[1]:.1f} A{r0 * k:.1f},{r0 * k:.1f} 0 {large} 1 {p3[0]:.1f},{p3[1]:.1f} Z")
        sh.path(d, cls, hatch)

    half = math.degrees(math.asin((A.FIN_T + A.FIN_SLOT_CLR) / 2 / R_OD))
    for fa in (0, 90, 180, 270):
        sector(R_ID, R_OD, fa + half, fa + 90 - half, "cut", "h1")
    sh.path(f"M{cx - R_MO * k:.1f},{cy:.1f} A{R_MO * k:.1f},{R_MO * k:.1f} 0 1 0 {cx + R_MO * k:.1f},{cy:.1f} "
            f"A{R_MO * k:.1f},{R_MO * k:.1f} 0 1 0 {cx - R_MO * k:.1f},{cy:.1f} Z "
            f"M{cx - R_MI * k:.1f},{cy:.1f} A{R_MI * k:.1f},{R_MI * k:.1f} 0 1 1 {cx + R_MI * k:.1f},{cy:.1f} "
            f"A{R_MI * k:.1f},{R_MI * k:.1f} 0 1 1 {cx - R_MI * k:.1f},{cy:.1f} Z", "cut", "h2")

    def radial_rect(r0, r1, off0, off1, ang, cls, hatch=None):
        a = math.radians(ang)
        ux, uy = math.cos(a), -math.sin(a)
        nx, ny = -uy, ux
        pts_ = []
        for r, o in ((r0, off0), (r1, off0), (r1, off1), (r0, off1)):
            pts_.append((cx + (ux * r + nx * o) * k, cy + (uy * r + ny * o) * k))
        sh.poly(pts_, cls, hatch)

    t2 = A.FIN_T / 2
    g = (A.FIN_T + A.FIN_GUIDE_CLR) / 2
    for fa in (0, 90, 180, 270):
        radial_rect(R_OD - A.FIN_TAB_H, r_le, -t2, t2, fa, "cut", "h3")
        radial_rect(R_MO + A.FIT_SH / 2, A.R_TAB_FLOOR, -g, g, fa, "cut", "h2")      # tab floor
        radial_rect(R_MO, R_SH, g, g + A.CORE_RAIL_T, fa, "cut", "h2")
        radial_rect(R_MO, R_SH, -g - A.CORE_RAIL_T, -g, fa, "cut", "h2")
    sh.circle(cx, cy, R_SH * k, "hid")
    for la in (45, 135, 225, 315):
        px, py = pol(26, la)
        sh.circle(px, py, 1.7 * k, "hid")
    radial_rect(R_OD, R_OD + 10, -5.5, 5.5, 45, "ph")
    sh.circle(cx, cy, 2, "dot")
    sh.line(cx - 110 * k, cy, cx + 110 * k, cy, "ctr")
    sh.line(cx, cy - 100 * k, cx, cy + 100 * k, "ctr")
    # angle arc 45
    ar = 46 * k
    sh.path(f"M{cx + ar:.1f},{cy:.1f} A{ar:.1f},{ar:.1f} 0 0 0 {cx + ar * math.cos(math.radians(45)):.1f},{cy - ar * math.sin(math.radians(45)):.1f}", "dim")
    sh.text(cx + 50 * k, cy - 17 * k, "45°", "td")
    br = 70 * k
    sh.path(f"M{cx + br * math.cos(math.radians(100)):.1f},{cy - br * math.sin(math.radians(100)):.1f} A{br:.1f},{br:.1f} 0 0 0 "
            f"{cx + br * math.cos(math.radians(170)):.1f},{cy - br * math.sin(math.radians(170)):.1f}", "dim")
    sh.text(cx - 46 * k, cy - 55 * k, "90° TYP ±0.5°", "td")
    L = sh.leader
    L(*pol(R_OD + 8, 45), cx + 40 * k, cy - 92 * k, "BO-408 RAIL BUTTON (COTS)", "start", "ta ts")
    L(*pol(R_OD - 0.5, 30), cx + 58 * k, cy - 62 * k, f"⌀{fm(A.BODY_OD)} / ⌀{fm(A.BODY_ID)} TUBE", "start", "ts")
    L(*pol(R_OD, 358), cx + 60 * k, cy + 28 * k, f"SLOT {fm(A.FIN_T + A.FIN_SLOT_CLR)} (FIN_T+{fm(A.FIN_SLOT_CLR)})", "start", "ts")
    L(*pol(24, 353), cx + 48 * k, cy + 44 * k, f"GUIDE {fm(A.FIN_T + A.FIN_GUIDE_CLR)} (FIN_T+{fm(A.FIN_GUIDE_CLR)})", "start", "ts")
    L(*pol(R_MO, 225), cx - 70 * k, cy + 62 * k, f"⌀{fm(A.MMT_OD)} MMT, ID PER MOTOR MFR", "start", "ts")
    L(*pol(26, 315), cx + 30 * k, cy + 80 * k, "4× M3 LOCK-RING SCREWS @R26 (AFT RING, REF)", "start", "ts")
    return sh


# ============================================================================ A-006 nose
def sheet_nose(R):
    sh = Sheet("nc", 1000, 470, "Nose cone half section with tangent ogive profile, print split, shoulder, insert bosses and key dimensions")
    v = View(0, 60, 235, 2.4)
    oy = v.oy
    nose_wall(sh, v, 1)
    bot = ogive_pts(v, 0, A.NC_L, 0, -1)
    sh.poly(bot + [(v.X(A.NC_L), v.Y(-R_SH)), (v.X(X["sh_end"]), v.Y(-R_SH)), (v.X(X["sh_end"]), oy), (v.X(0), oy)], "body")
    sh.line(v.X(A.NC_L), v.Y(-R_OD), v.X(A.NC_L), oy, "ln thin")
    sh.line(v.X(A.NC_SPLIT), v.Y(-A.ogive_r(A.NC_SPLIT)), v.X(A.NC_SPLIT), oy, "ln thin")
    st = X["nc_screws"]
    sh.rect(v.X(st - 5), v.Y(R_SH - A.NC_SH_WALL), 10 * v.s, -3 * v.s, "cut", "h2")
    sh.rect(v.X(st - 2), v.Y(R_SH - A.NC_SH_WALL + 0.2), 4 * v.s, 3.2 * v.s, "comp")
    sh.circle(v.X(st), v.Y(-R_SH * math.sin(math.radians(30))), 1.7 * v.s, "ln")
    lz1 = X["sh_end"] - A.NC_BH_T
    sh.rect(v.X(lz1 - A.NC_LUG_L), v.Y(R_SH - A.NC_SH_WALL), A.NC_LUG_L * v.s, A.NC_LUG_T * v.s, "cut", "h2")
    sh.rect(v.X(lz1 - A.INS_M3_L), v.Y(R_SH - A.NC_SH_WALL - A.NC_LUG_T / 2 + A.INS_M3_D / 2), A.INS_M3_L * v.s, A.INS_M3_D * v.s, "comp")
    sh.rect(v.X(lz1), v.Y(R_SH - A.NC_SH_WALL - 0.1), A.NC_BH_T * v.s, 2 * (R_SH - A.NC_SH_WALL - 0.1) * v.s, "ph")
    sh.centerline(v.X(-10), v.X(X["sh_end"] + 12), oy)
    nr = R["nose"]
    y_top = v.Y(R_OD)
    sh.dim_h(v.X(0), v.X(A.NC_SPLIT), y_top - 30, f"{fm(A.NC_SPLIT)} PRINT SPLIT", oy, v.Y(A.ogive_r(A.NC_SPLIT)))
    sh.dim_h(v.X(0), v.X(A.NC_L), y_top - 62, f"{fm(A.NC_L)} = 4.0 × ⌀", None, y_top)
    sh.line(v.X(0), oy - 3, v.X(0), y_top - 67, "ext")
    sh.dim_h(v.X(A.NC_L), v.X(X["sh_end"]), y_top - 30, fm(A.NC_SH_L), y_top, v.Y(R_SH))
    sh.dim_h(v.X(0), v.X(X["sh_end"]), y_top - 94, f"{fm(X['sh_end'])} OVERALL", None, v.Y(R_SH))
    sh.line(v.X(0), y_top - 67, v.X(0), y_top - 99, "ext")
    sh.dim_v(v.Y(R_OD), v.Y(-R_OD), v.X(A.NC_L) - 26, f"⌀{fm(A.BODY_OD)}", v.X(A.NC_L), v.X(A.NC_L))
    sh.dim_v(v.Y(R_SH), v.Y(-R_SH), v.X(X["sh_end"]) + 30, f"⌀{fm(2 * R_SH)} +0/−0.15", v.X(X["sh_end"]), v.X(X["sh_end"]), right=True)
    sh.dim_h(v.X(X["nc_base"]), v.X(st), v.Y(-R_OD) + 48, fm(st - A.NC_L), v.Y(-R_SH), v.Y(-R_SH * 0.5), below=True)
    L = sh.leader
    L(v.X(120), v.Y(A.ogive_r(120) - 0.6), v.X(110), v.Y(-R_OD) + 110, f"WALL {fm(A.NC_WALL)} (3 PERIMETERS)", "middle", "ts")
    L(v.X(A.NC_SPLIT + 3), v.Y(A.ogive_r(A.NC_SPLIT) - 2), v.X(A.NC_SPLIT + 70), v.Y(-R_OD) + 110, f"WEB {fm(A.NC_SPLIT_WEB)} + SPIGOT {fm(A.NC_SPIGOT_L)} × {fm(A.NC_SPIGOT_WALL)}, EPOXY", "middle", "ts")
    L(v.X(st), v.Y(R_SH - A.NC_SH_WALL - 2), v.X(st + 20), v.Y(-R_OD) + 130, "3× M3 HEAT-SET @120°", "middle", "ts")
    L(v.X(X["sh_end"] - 6), v.Y(R_SH - A.NC_SH_WALL - 3), v.X(X["sh_end"] - 10), v.Y(-R_OD) + 150, "3× LUG + M3 INSERT (NC-103)", "middle", "ts")
    L(v.X(8), v.Y(0.5), v.X(8), v.Y(-R_OD) + 150, f"TIP HALF-ANGLE {nr['tip_half_angle']:.1f}° → PRINTS WITHOUT SUPPORT", "start", "ts")
    sh.text(v.X(0) - 20, 70, f"TANGENT OGIVE  r(x) = √(ρ² − (L − x)²) + R − ρ     ρ = (R² + L²) / 2R = {nr['rho']:.1f}", "td", "start")
    sh.title(18, 28, "NC-101 / NC-102 NOSE CONE · HALF SECTION", "PETG · FDM · top half sectioned, lower half exterior · drawn 2.4×")
    return sh


# ============================================================================ A-007 avionics bay
def sheet_av(R):
    sh = Sheet("av", 1300, 560, "Avionics bay half section and bulkhead face views with rod pattern, eyebolt and harness hole")
    v = View(420, 40, 280, 2.2)
    oy = v.oy
    tube_walls(sh, v, 420, X["pl_end"], R_ID, R_OD, "h1")
    draw_av_no_pl_range(sh, v, 650)
    sh.centerline(v.X(425), v.X(655), oy)
    b, a = X["av_bh_fwd_outer"], X["cpl_aft"]
    yb = v.Y(-R_OD)
    sh.dim_h(v.X(X["cpl_fwd"]), v.X(X["pl_end"]), yb + 34, fm(A.AV_INS), v.Y(-R_CO), v.Y(-R_OD), below=True)
    sh.dim_h(v.X(X["pl_end"]), v.X(X["band_end"]), yb + 34, fm(A.AV_BAND_L), None, v.Y(-R_OD), below=True)
    sh.dim_h(v.X(X["band_end"]), v.X(a), yb + 34, fm(A.AV_INS), None, v.Y(-R_CO), below=True)
    sh.dim_h(v.X(X["cpl_fwd"]), v.X(a), yb + 70, f"{fm(A.AV_CPL_L)} AV-301", None, None, below=True)
    sh.dim_h(v.X(X["sled_fwd"]), v.X(X["sled_aft"]), yb + 106, f"{fm(A.SLED_L)} AV-306 SLED", v.Y(-1.5), v.Y(-1.5), below=True)
    sh.dim_h(v.X(b), v.X(b + 12), v.Y(R_OD) - 30, "6+6", v.Y(R_CO), v.Y(R_CI), )
    sh.dim_h(v.X(a + A.GASKET_T - 6), v.X(a + A.GASKET_T + 6), v.Y(R_OD) - 30, "6+6", v.Y(R_CI), v.Y(R_CO))
    sh.dim_h(v.X(b), v.X(b + A.ROD_L), v.Y(R_OD) - 62, f"{fm(A.ROD_L)} M4 A2-70 ROD ×2", None, None)
    L = sh.leader
    L(v.X(529), v.Y(33), v.X(529), v.Y(R_OD) - 92, "⌀8 SWITCH ACCESS (90°)", "middle", "ts")
    L(v.X(529), v.Y(-R_OD), v.X(560), yb + 140, "4× ⌀2 STATIC PORTS @45° (NOT IN PLANE) [SIZE PER SENSOR GUIDANCE]", "middle", "ts")
    L(v.X(a + 0.25), v.Y(-R_CO + 0.7), v.X(a - 40), yb + 170, f"AV-309 FACE GASKET 1.5 FREE / {fm(A.GASKET_T)} COMPRESSED", "middle", "ts")
    sh.title(18, 28, "AV-300 AVIONICS BAY · HALF SECTION & BULKHEAD FACES", "Coupler bonded into payload tube; aft bulkhead removable for sled service · drawn 2.2×")

    def bulkhead_face(cx, cy, fwd):
        k = 2.2
        sh.circle(cx, cy, R_CO * k, "body" if not fwd else "hid")
        sh.circle(cx, cy, (R_CI - 0.1) * k, "body" if fwd else "hid")
        sh.line(cx - 36 * k, cy, cx + 36 * k, cy, "ctr")
        sh.line(cx, cy - 36 * k, cx, cy + 36 * k, "ctr")
        for sx in (-1, 1):
            hx = cx + sx * A.AV_ROD_SP / 2 * k
            sh.circle(hx, cy, (2.0 if fwd else 2.25) * k, "ln")
            if not fwd:
                sh.circle(hx, cy, 4.2 * k, "hid")
        if fwd:
            sh.circle(cx, cy - A.HARNESS_Y * k, A.HARNESS_D / 2 * k, "ln")
            for sx in (-1, 1):
                sh.circle(cx + sx * A.TRAY_HOLE_X * k, cy - A.TRAY_HOLE_Y * k, A.CLR_M3 / 2 * k, "ln")
                sh.circle(cx + sx * A.AV_ROD_SP / 2 * k, cy, A.TNUT_FLANGE_D / 2 * k, "hid")
        else:
            sh.circle(cx, cy, 3.25 * k, "ln")
            sh.circle(cx, cy, 9 * k, "eye")
        sh.dim_h(cx - A.AV_ROD_SP / 2 * k, cx + A.AV_ROD_SP / 2 * k, cy - R_CO * k - 22, f"{fm(A.AV_ROD_SP)} ±0.2", cy, cy)
        sh.text(cx, cy + R_CO * k + 30, "AV-303 FWD BULKHEAD · VIEW FROM AFT" if fwd else "AV-304 AFT BULKHEAD · VIEW FROM AFT", "tb ts")
        lines = ([f"2× M4 TEE-NUT ⌀{fm(A.TNUT_BARREL_D)} (FLANGE ON FWD FACE, DASHED)", f"⌀{fm(A.HARNESS_D)} HARNESS HOLE + GROMMET", f"2× ⌀{fm(A.CLR_M3)} @ (±{fm(A.TRAY_HOLE_X)}, {fm(A.TRAY_HOLE_Y)}): M3 × 16 → PL-202", f"DISCS ⌀{fm(A.CPL_ID - 0.2)} + ⌀{fm(A.CPL_OD)}, 6 PLY EACH"]
                 if fwd else ["2× ⌀4.5 ROD CLEARANCE + NYLOCK WING NUT", "⌀6.5 M6 FORGED EYEBOLT, NUT + FENDER WASHER", "RATED LOAD ≥ DESIGN (SEE LOADS)", f"DISCS ⌀{fm(A.CPL_ID - 0.2)} + ⌀{fm(A.CPL_OD)}, 6 PLY EACH"])
        for i, t in enumerate(lines):
            sh.text(cx, cy + R_CO * k + 48 + i * 15, t, "tm ts")

    bulkhead_face(840, 250, True)
    bulkhead_face(1120, 250, False)
    return sh


def draw_av_no_pl_range(sh, v, x_end):
    sw0, sw1 = X["pl_end"] + A.AV_BAND_L / 2 - A.SW_HOLE_D / 2, X["pl_end"] + A.AV_BAND_L / 2 + A.SW_HOLE_D / 2
    tube_walls(sh, v, X["pl_end"], X["band_end"], R_ID, R_OD, "h1", gaps_top=[(sw0, sw1)])
    tube_walls(sh, v, X["band_end"], x_end, R_ID, R_OD, "h1")
    tube_walls(sh, v, X["cpl_fwd"], X["cpl_aft"], R_CI, R_CO, "h2", gaps_top=[(sw0, sw1)])
    _av_internals(sh, v)


# ============================================================================ system architecture
def diagram_architecture(R):
    sh = Sheet("arch", 1200, 520, "System architecture: four airframe modules with numbered interfaces, recovery tether, external certified motor, launch rail and ground station")
    y0, h = 150, 96
    mods = [("100", "NOSE CONE", "ogive · ballast mount", 40, 190),
            ("200", "PAYLOAD BAY", "camera · GPS tray · hatch", 270, 210),
            ("300", "AVIONICS BAY", "sled · battery · switch band", 520, 220),
            ("400", "BOOSTER", "recovery bay · fin can · MMT", 780, 300)]
    for num, name, sub, x, w in mods:
        sh.rect(x, y0, w, h, "box", rx=4)
        sh.text(x + 14, y0 + 26, num, "tl ta", "start")
        sh.text(x + 14, y0 + 50, name, "tb", "start")
        sh.text(x + 14, y0 + 70, sub, "tm ts", "start")
    ifs = [(230, "I-01", "radial M3 into inserts"), (490, "I-02", "bonded coupler"), (750, "I-03", "slip fit · SEPARATES")]
    for x, lab, sub in ifs:
        acc = lab == "I-03"
        sh.line(x, y0 - 18, x, y0 + h + 18, "arrowacc" if acc else "ln")
        sh.text(x, y0 - 40, lab, "tb" + (" ta" if acc else ""))
        sh.text(x, y0 - 26, sub, "tm ts" + (" ta" if acc else ""))
    # recovery tether
    ty = y0 + h + 70
    sh.path(f"M640,{y0 + h} L640,{ty} L960,{ty} L960,{y0 + h}", "arrowacc")
    sh.text(800, ty + 18, "500 RECOVERY TETHER — eyebolt I-04a → chute & cord → aramid anchor I-04b", "ta ts")
    # harness
    sh.path(f"M420,{y0 + h - 20} C470,{y0 + h + 30} 560,{y0 + h + 30} 600,{y0 + h - 20}", "arrowdim")
    sh.text(510, y0 + h + 44, "I-08 harness through AV-303 grommet", "td ts")
    # motor external
    mx, my = 960, 390
    sh.rect(mx, my, 200, 70, "boxacc", rx=4)
    sh.text(mx + 100, my + 28, "600 CERTIFIED MOTOR", "tb ta")
    sh.text(mx + 100, my + 46, "EXTERNAL · purchased · RSO-handled", "ta ts")
    sh.o.append(f'<line x1="1060" y1="{my}" x2="1060" y2="{y0 + h + 4}" class="arrowacc" marker-end="url(#c-arch)"/>')
    sh.text(1070, my - 30, "I-05 COTS retainer", "ta ts", "start")
    sh.text(1070, my - 16, "thrust → MMT → rings → tube", "tm ts", "start")
    # rail
    sh.rect(640, 420, 250, 40, "box", rx=4)
    sh.text(765, 445, "LAUNCH RAIL (range-supplied)", "ts tb")
    sh.o.append(f'<line x1="850" y1="420" x2="850" y2="{y0 + h + 4}" class="arrow" marker-end="url(#b-arch)"/>')
    sh.text(858, 398, "I-07 rail buttons", "ts", "start")
    # ground station
    sh.rect(40, 400, 250, 60, "box", rx=4)
    sh.text(165, 425, "GROUND STATION", "tb")
    sh.text(165, 443, "LoRa receiver + laptop", "tm ts")
    sh.o.append(f'<path d="M630,{y0 + h} C600,380 380,430 294,430" class="arrowdim" marker-end="url(#a-arch)"/>')
    sh.text(420, 380, "telemetry downlink only", "td ts")
    # fin interface
    sh.text(930, y0 + 26, "I-06 slide-in fins", "tm ts", "start")
    sh.text(930, y0 + 42, "locked by BO-405", "tm ts", "start")
    sh.text(40, 40, "ASTRA-66 SYSTEM ARCHITECTURE", "tl", "start")
    sh.text(40, 58, "Separation happens only at I-03. The electronics have no deployment outputs; motor ejection (a certified-motor feature) opens I-03.", "tm ts", "start")
    return sh


def diagram_avionics(R):
    sh = Sheet("elec", 1200, 470, "Avionics block diagram: battery and arming switch feed a regulator; microcontroller connects to IMU and barometer over I2C, SD card and LoRa radio over SPI, GPS over UART, and breakwire, buzzer and LED on GPIO; there are no pyrotechnic outputs")

    def box(x, y, w, h, t, sub="", cls="box"):
        sh.rect(x, y, w, h, cls, rx=4)
        sh.text(x + w / 2, y + h / 2 - (2 if sub else -4), t, "tb ts")
        if sub:
            sh.text(x + w / 2, y + h / 2 + 14, sub, "tm ts")

    def arrow(x1, y1, x2, y2, label="", cls="arrow", m="b"):
        sh.o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}" marker-end="url(#{m}-elec)"/>')
        if label:
            sh.text((x1 + x2) / 2, (y1 + y2) / 2 - 6, label, "td ts")

    box(40, 90, 150, 56, "1S LiPo", "protected cell")
    box(40, 200, 150, 56, "ARMING SWITCH", "via switch band")
    box(40, 310, 150, 56, "3.3 V REGULATOR", "LDO / buck")
    arrow(115, 146, 115, 198)
    arrow(115, 256, 115, 308)
    box(470, 180, 220, 110, "MICROCONTROLLER", "RP2040 / ESP32-S3 class")
    arrow(190, 338, 468, 262, "3V3")
    box(260, 40, 170, 50, "IMU ±32 g class", "")
    box(470, 40, 150, 50, "BAROMETER", "")
    box(650, 40, 150, 50, "TEMPERATURE", "")
    sh.line(300, 130, 760, 130, "arrow")
    for x in (345, 545, 725):
        sh.line(x, 90, x, 130, "arrow")
    arrow(580, 130, 580, 178, "I²C")
    box(850, 60, 170, 50, "microSD LOGGER", "")
    box(850, 150, 170, 50, "LoRa RADIO", "legal ISM band only")
    arrow(692, 205, 848, 90, "SPI")
    arrow(692, 225, 848, 175, "SPI")
    box(850, 250, 170, 56, "GPS MODULE", "in payload bay · I-08")
    arrow(848, 278, 694, 255, "UART")
    box(850, 340, 170, 50, "BREAKWIRE @ I-03", "separation sense")
    box(470, 350, 220, 50, "BUZZER + STATUS LED", "")
    arrow(848, 365, 694, 280, "GPIO in")
    arrow(580, 292, 580, 348, "GPIO out")
    sh.o.append('<line x1="1022" y1="175" x2="1150" y2="175" class="arrowdim" marker-end="url(#a-elec)"/>')
    sh.text(1100, 162, "downlink", "td ts")
    box(260, 400, 170, 50, "CAMERA", "own battery, isolated", "boxdim")
    sh.rect(20, 18, 1160, 444, "hid", rx=8)
    sh.text(40, 34, "NO PYROTECHNIC OUTPUTS — sensing, logging and telemetry only", "ta tb ts", "start")
    return sh


def diagram_states(R):
    sh = Sheet("fsm", 1200, 190, "Flight-phase detection state machine for data logging: pad, boost, coast, apogee, descent, landed, with transition conditions")
    st = [("PAD", "log 10 Hz"), ("BOOST", "log max rate"), ("COAST", "watch baro"), ("APOGEE", "timestamp"), ("DESCENT", "log 20 Hz"), ("LANDED", "beep + GPS")]
    cond = ["|a| > 3 g for 100 ms", "a_axial < 0", "baro alt falls 3 samples", "breakwire open OR t+", "baro rate ≈ 0 for 5 s"]
    w, gap, y = 150, 44, 70
    for i, (n, sub) in enumerate(st):
        x = 20 + i * (w + gap)
        sh.rect(x, y, w, 60, "box" if n != "APOGEE" else "boxdim", rx=30)
        sh.text(x + w / 2, y + 27, n, "tb")
        sh.text(x + w / 2, y + 45, sub, "tm ts")
        if i < len(cond):
            sh.o.append(f'<line x1="{x + w + 2}" y1="{y + 30}" x2="{x + w + gap - 2}" y2="{y + 30}" class="arrow" marker-end="url(#b-fsm)"/>')
            sh.text(x + w + gap / 2, y + (-12 if i % 2 == 0 else 82), cond[i], "td ts")
    sh.text(20, 24, "RECOVERY-DETECTION CONCEPT (LOGGING ONLY) · thresholds are ASSUMPTIONS to tune from ground and flight data", "tm ts", "start")
    return sh


def all_sheets(R):
    return {
        "ga": sheet_ga(R), "ex": sheet_exploded(R), "sa": sheet_section_fwd(R), "sb": sheet_section_aft(R),
        "fn": sheet_fin(R), "nc": sheet_nose(R), "av": sheet_av(R),
        "arch": diagram_architecture(R), "elec": diagram_avionics(R), "fsm": diagram_states(R),
    }
