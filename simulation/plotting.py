"""Minimal, dependency-free SVG plotting (line plots and tornado charts) with labelled axes, units and legends."""
import math

PALETTE = ["#1D6A86", "#C24A0C", "#2F6A47", "#6B4FA0", "#8A5A00"]
INK, MUTED, GRID, BG, BAND = "#1B2126", "#5A646B", "#DDE2DE", "#FFFFFF", "#E1EFE5"
FONT = "font-family:'IBM Plex Sans','Segoe UI',system-ui,sans-serif"


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def nice_ticks(lo, hi, n=6):
    if hi == lo:
        hi = lo + 1
    span = hi - lo
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if span / (m * mag) <= n)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 10))
        v += step
    return ticks


def _fmt(v):
    return f"{v:.0f}" if abs(v) >= 100 or float(v).is_integer() else (f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}".rstrip("0").rstrip("."))


def line_plot(path, series, xlabel, ylabel, title, subtitle="", bands=(), vlines=(), xlim=None, ylim=None, points=()):
    """series: [dict(label, x, y, dash=False)]; bands: [(y0, y1, label)]; vlines: [(x, label)]; points: [(x, y, label)]."""
    W, H = 820, 470
    l, r, t, b = 78, 28, 92 if len(series) > 1 else 74, 62
    xs = [x for s in series for x in s["x"]]
    ys = [y for s in series for y in s["y"]] + [v for b_ in bands for v in b_[:2]]
    x0, x1 = xlim or (min(xs), max(xs))
    if ylim:
        y0, y1 = ylim
    else:
        y0, y1 = min(ys), max(ys)
        if y1 == y0:
            y1 = y0 + 1
        pad = (y1 - y0) * 0.06
        y0 = 0.0 if 0 <= y0 < pad else y0 - pad     # snap to zero when the data start near it
        y1 = y1 + pad
    xt, yt = nice_ticks(x0, x1), nice_ticks(y0, y1)
    x0, x1 = min(x0, xt[0]), max(x1, xt[-1])
    y0, y1 = min(y0, yt[0]), max(y1, yt[-1])

    def X(v):
        return l + (v - x0) / (x1 - x0) * (W - l - r)

    def Y(v):
        return t + (1 - (v - y0) / (y1 - y0)) * (H - t - b)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}" style="background:{BG};{FONT}">',
         f'<rect width="{W}" height="{H}" fill="{BG}"/>',
         f'<text x="{l}" y="28" font-size="17" font-weight="600" fill="{INK}">{_esc(title)}</text>']
    if subtitle:
        o.append(f'<text x="{l}" y="48" font-size="12" fill="{MUTED}">{_esc(subtitle)}</text>')
    for b0, b1, lab in bands:
        o.append(f'<rect x="{l}" y="{Y(b1):.1f}" width="{W - l - r}" height="{Y(b0) - Y(b1):.1f}" fill="{BAND}"/>')
        o.append(f'<text x="{W - r - 6}" y="{Y(b1) + 14:.1f}" text-anchor="end" font-size="11" fill="#2F6A47">{_esc(lab)}</text>')
    for v in yt:
        if y0 <= v <= y1:
            o.append(f'<line x1="{l}" x2="{W - r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID}" stroke-width="1"/>')
            o.append(f'<text x="{l - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" font-size="11" fill="{MUTED}">{_fmt(v)}</text>')
    for v in xt:
        if x0 <= v <= x1:
            o.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{H - b}" y2="{H - b + 5}" stroke="{MUTED}"/>')
            o.append(f'<text x="{X(v):.1f}" y="{H - b + 19}" text-anchor="middle" font-size="11" fill="{MUTED}">{_fmt(v)}</text>')
    o.append(f'<line x1="{l}" x2="{W - r}" y1="{H - b}" y2="{H - b}" stroke="{MUTED}" stroke-width="1"/>')
    if y0 < 0 < y1:
        o.append(f'<line x1="{l}" x2="{W - r}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="{MUTED}" stroke-width="1"/>')
    for xv, lab in vlines:
        o.append(f'<line x1="{X(xv):.1f}" x2="{X(xv):.1f}" y1="{t}" y2="{H - b}" stroke="{MUTED}" stroke-dasharray="4 4"/>')
        o.append(f'<text x="{X(xv) + 4:.1f}" y="{H - b - 8}" font-size="11" fill="{MUTED}">{_esc(lab)}</text>')
    for i, s in enumerate(series):
        c = PALETTE[i % len(PALETTE)]
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(s["x"], s["y"]))
        dash = ' stroke-dasharray="7 5"' if s.get("dash") else ""
        o.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round"{dash}/>')
        if s.get("markers"):
            for x, y in zip(s["x"], s["y"]):
                o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4" fill="{c}" stroke="{BG}" stroke-width="1.5"/>')
    for x, y, lab in points:
        o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="5" fill="{INK}" stroke="{BG}" stroke-width="2"/>')
        o.append(f'<text x="{X(x) + 8:.1f}" y="{Y(y) - 8:.1f}" font-size="11" font-weight="600" fill="{INK}">{_esc(lab)}</text>')
    if len(series) > 1:
        lx = l
        for i, s in enumerate(series):
            c = PALETTE[i % len(PALETTE)]
            dash = ' stroke-dasharray="7 5"' if s.get("dash") else ""
            o.append(f'<line x1="{lx}" x2="{lx + 22}" y1="70" y2="70" stroke="{c}" stroke-width="2.5"{dash}/>')
            o.append(f'<text x="{lx + 28}" y="74" font-size="12" fill="{INK}">{_esc(s["label"])}</text>')
            lx += 40 + 7 * len(s["label"])
    o.append(f'<text x="{(l + W - r) / 2:.0f}" y="{H - 16}" text-anchor="middle" font-size="12" fill="{INK}">{_esc(xlabel)}</text>')
    o.append(f'<text x="18" y="{(t + H - b) / 2:.0f}" text-anchor="middle" font-size="12" fill="{INK}" transform="rotate(-90 18 {(t + H - b) / 2:.0f})">{_esc(ylabel)}</text>')
    o.append("</svg>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(o))


def tornado(path, rows, baseline, xlabel, title, subtitle=""):
    """rows: [dict(label, low, high, low_note, high_note)] values of the metric; sorted by swing."""
    rows = sorted(rows, key=lambda r: -abs(r["high"] - r["low"]))
    W = 820
    bh, gap = 26, 12
    l, r, t = 250, 40, 80
    H = t + len(rows) * (bh + gap) + 70
    vals = [baseline] + [v for r_ in rows for v in (r_["low"], r_["high"])]
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1
    lo, hi = lo - 0.08 * span, hi + 0.08 * span
    ticks = nice_ticks(lo, hi, 6)
    lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])

    def X(v):
        return l + (v - lo) / (hi - lo) * (W - l - r)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}" style="background:{BG};{FONT}">',
         f'<rect width="{W}" height="{H}" fill="{BG}"/>',
         f'<text x="24" y="30" font-size="17" font-weight="600" fill="{INK}">{_esc(title)}</text>',
         f'<text x="24" y="50" font-size="12" fill="{MUTED}">{_esc(subtitle)}</text>']
    for v in ticks:
        o.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{t - 6}" y2="{H - 60}" stroke="{GRID}"/>')
        o.append(f'<text x="{X(v):.1f}" y="{H - 42}" text-anchor="middle" font-size="11" fill="{MUTED}">{_fmt(v)}</text>')
    for i, row in enumerate(rows):
        y = t + i * (bh + gap)
        for val, note, c in ((row["low"], row["low_note"], PALETTE[0]), (row["high"], row["high_note"], PALETTE[1])):
            if abs(val - baseline) <= 1e-6 * max(1.0, abs(baseline)):
                continue                      # this end of the range IS the baseline: no bar, no label
            x_a, x_b = sorted((X(baseline), X(val)))
            o.append(f'<rect x="{x_a:.1f}" y="{y}" width="{max(x_b - x_a, 1):.1f}" height="{bh}" rx="3" fill="{c}"/>')
            anchor, dx = ("end", -6) if val < baseline else ("start", 6)
            o.append(f'<text x="{X(val) + dx:.1f}" y="{y + bh / 2 + 4}" text-anchor="{anchor}" font-size="11" fill="{INK}">{_esc(note)}: {_fmt(val)}</text>')
        o.append(f'<text x="{l - 12 - 150:.0f}" y="{y + bh / 2 + 4}" font-size="12" fill="{INK}">{_esc(row["label"])}</text>')
    o.append(f'<line x1="{X(baseline):.1f}" x2="{X(baseline):.1f}" y1="{t - 10}" y2="{H - 60}" stroke="{INK}" stroke-width="1.5"/>')
    o.append(f'<text x="{X(baseline):.1f}" y="{t - 14}" text-anchor="middle" font-size="11" font-weight="600" fill="{INK}">baseline {_fmt(baseline)}</text>')
    o.append(f'<rect x="{W - 260}" y="{H - 26}" width="12" height="12" fill="{PALETTE[0]}"/><text x="{W - 242}" y="{H - 16}" font-size="11" fill="{INK}">lower setting</text>')
    o.append(f'<rect x="{W - 150}" y="{H - 26}" width="12" height="12" fill="{PALETTE[1]}"/><text x="{W - 132}" y="{H - 16}" font-size="11" fill="{INK}">higher setting</text>')
    o.append(f'<text x="{(l + W - r) / 2:.0f}" y="{H - 16}" text-anchor="middle" font-size="12" fill="{INK}">{_esc(xlabel)}</text>')
    o.append("</svg>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(o))
