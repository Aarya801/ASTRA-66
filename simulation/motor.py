"""External motor data interface (read-only).

The motor is an external, commercially certified component. This module only READS a thrust-time table
in the standard RASP (.eng) format and the masses from simulation/motor_config.json. It performs no
propulsion design. Mass during burn follows the usual convention (also used by OpenRocket):
    m_motor(t) = m_total - m_prop * I(t) / I_total,   I(t) = integral of F dt from 0 to t.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "motor_config.json")
PLACEHOLDER_FILE = "motors/PLACEHOLDER_TEST_INPUT.eng"


def parse_eng(path):
    header, pts, comments = None, [], []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(";"):
                comments.append(line[1:].strip())
                continue
            if header is None:
                f = line.split()
                if len(f) < 7:
                    raise ValueError(f"{path}: RASP header needs 7 fields, got {line!r}")
                header = dict(name=f[0], diameter_mm=float(f[1]), length_mm=float(f[2]), delays=f[3],
                              prop_mass_kg=float(f[4]), total_mass_kg=float(f[5]), maker=" ".join(f[6:]))
                continue
            t, F = (float(x) for x in line.split()[:2])
            pts.append((t, F))
    if header is None or len(pts) < 2:
        raise ValueError(f"{path}: no header or thrust data")
    if pts[0][0] != 0.0:
        pts.insert(0, (0.0, 0.0))
    if pts[-1][1] != 0.0:
        raise ValueError(f"{path}: last thrust point must be 0 N")
    if any(b[0] <= a[0] for a, b in zip(pts, pts[1:])):
        raise ValueError(f"{path}: time values must increase")
    return dict(header, points=pts, comments=comments)


class Motor:
    """Piecewise-linear thrust curve with impulse-proportional propellant consumption."""

    def __init__(self, points, total_mass_kg, prop_mass_kg, name="", placeholder=True, source=""):
        self.pts = list(points)
        self.name, self.placeholder, self.source = name, placeholder, source
        self.total_mass = total_mass_kg
        self.prop_mass = prop_mass_kg
        self.cum = [0.0]
        for (t0, f0), (t1, f1) in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + 0.5 * (f0 + f1) * (t1 - t0))
        self.total_impulse = self.cum[-1]
        self.burn_time = self.pts[-1][0]

    def _seg(self, t):
        for i in range(len(self.pts) - 1):
            if t < self.pts[i + 1][0]:
                return i
        return len(self.pts) - 2

    def thrust(self, t):
        if t <= 0.0 or t >= self.burn_time:
            return 0.0
        i = self._seg(t)
        (t0, f0), (t1, f1) = self.pts[i], self.pts[i + 1]
        return f0 + (f1 - f0) * (t - t0) / (t1 - t0)

    def impulse(self, t):
        if t <= 0.0:
            return 0.0
        if t >= self.burn_time:
            return self.total_impulse
        i = self._seg(t)
        t0, f0 = self.pts[i]
        f = self.thrust(t)
        return self.cum[i] + 0.5 * (f0 + f) * (t - t0)

    def mass_kg(self, t):
        if self.total_impulse <= 0:
            return self.total_mass
        return self.total_mass - self.prop_mass * self.impulse(t) / self.total_impulse

    def describe(self):
        return dict(name=self.name, placeholder=self.placeholder, source=self.source, total_impulse_Ns=self.total_impulse,
                    burn_time_s=self.burn_time, average_thrust_N=self.total_impulse / self.burn_time if self.burn_time else 0.0,
                    peak_thrust_N=max(f for _, f in self.pts), total_mass_g=self.total_mass * 1000, prop_mass_g=self.prop_mass * 1000,
                    burnout_mass_g=(self.total_mass - self.prop_mass) * 1000)


def load_config(path=CONFIG):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_motor(config_path=CONFIG):
    """Load the motor named in motor_config.json and cross-check it against the config masses/length."""
    cfg = load_config(config_path)
    rel = cfg.get("thrust_curve_file") or PLACEHOLDER_FILE
    path = os.path.join(os.path.dirname(os.path.abspath(config_path)), rel)
    eng = parse_eng(path)
    status = cfg.get("status")
    if status == "MANUFACTURER_DATA" and rel.replace("\\", "/") == PLACEHOLDER_FILE:
        raise ValueError("motor_config.json: MANUFACTURER_DATA requires the certified motor's published .eng file, not the placeholder test input")
    m = cfg["motor"]
    mmt_id = cfg["motor_mount"]["mmt_id_mm"]
    if eng["diameter_mm"] > mmt_id:
        raise ValueError(f"{rel}: motor diameter {eng['diameter_mm']} mm exceeds MMT bore {mmt_id} mm in motor_config.json")
    if m.get("diameter_class_mm") is not None and abs(eng["diameter_mm"] - m["diameter_class_mm"]) > 0.5:
        raise ValueError(f"{rel}: diameter {eng['diameter_mm']} mm disagrees with motor.diameter_class_mm {m['diameter_class_mm']}")
    if not 0 < eng["prop_mass_kg"] < eng["total_mass_kg"]:
        raise ValueError(f"{rel}: propellant mass must be positive and below the total mass")
    checks = [("loaded mass", eng["total_mass_kg"] * 1000, m["loaded_mass_g"], 1.0),
              ("burnout mass", (eng["total_mass_kg"] - eng["prop_mass_kg"]) * 1000, m["burnout_mass_g"], 1.0),
              ("length", eng["length_mm"], m["length_mm"], 0.5)]
    bad = [f"{n}: .eng {a:.1f} vs config {b:.1f}" for n, a, b, tol in checks if abs(a - b) > tol]
    if bad:
        raise ValueError("motor_config.json and " + rel + " disagree -> " + "; ".join(bad))
    return Motor(eng["points"], eng["total_mass_kg"], eng["prop_mass_kg"], name=eng["name"],
                 placeholder=(status != "MANUFACTURER_DATA"), source=rel)
