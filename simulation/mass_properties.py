"""Vehicle mass properties for the simulation, taken from the project's single source of truth.

analysis/analysis.py builds the item-level mass budget; items whose note starts with "CAD:" carry masses and
CG stations measured from the rendered OpenSCAD meshes (cad/exports/cad_mass_properties.json). The motor item
(MT-601) is removed here and replaced by the time-varying motor mass from motor.py.

Data classes (used in every report):
  A  = verified CAD-derived (geometry / volume measured from the CAD meshes)
  B  = calculated (derived from A/C/D by documented equations)
  C  = assumption (engineering estimate awaiting measurement)
  D  = placeholder (stand-in until real data exist)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import analysis as A  # noqa: E402

MOTOR_ID = "MT-601"
PAYLOAD_X = (A.X["sh_end"] + A.X["av_bh_fwd_outer"]) / 2        # payload-bay centre station, mm
LOW_COST_REMOVED = ("EL-CAM", "EL-GPS", "PL-203", "PL-204")        # items absent in the low-cost build


def classify(item):
    if item["note"].startswith("CAD:"):
        return "A x C (CAD volume x assumed density/fill)"
    if item["tag"] == "COTS":
        return "D placeholder (external component)" if A.MOTOR_STATUS == "PLACEHOLDER" else "manufacturer data"
    if item["tag"] == "USER":
        return "D placeholder (user to measure)"
    if item["tag"] == "ASM":
        return "C assumption"
    return "B calculated"


def items():
    return [dict(i) for i in A.build_mass_items()]


class Vehicle:
    """Airframe (everything except the motor) plus optional payload; motor added at its station."""

    def __init__(self, mass_scale=1.0, payload_g=0.0, payload_x=PAYLOAD_X, cg_shift_mm=0.0, remove=()):
        its = items()
        motor = [i for i in its if i["id"] == MOTOR_ID][0]
        air = [i for i in its if i["id"] != MOTOR_ID and i["id"] not in remove]
        m = sum(i["m"] for i in air) * mass_scale
        mx = sum(i["m"] * i["x"] for i in air) * mass_scale
        if payload_g:
            m += payload_g
            mx += payload_g * payload_x
        self.air_g = m
        self.air_x = mx / m + cg_shift_mm
        self.motor_x = motor["x"]
        self.mass_scale, self.payload_g, self.cg_shift_mm = mass_scale, payload_g, cg_shift_mm

    def mass_kg(self, motor_mass_kg):
        return self.air_g / 1000.0 + motor_mass_kg

    def cg_mm(self, motor_mass_kg):
        mm = motor_mass_kg * 1000.0
        return (self.air_g * self.air_x + mm * self.motor_x) / (self.air_g + mm)


_AUDIT = {}


def audit_cached():
    if not _AUDIT:
        _AUDIT.update(audit())
    return _AUDIT


def audit():
    """Current model values with their data class, for the reports."""
    R = A.run()
    vr = json.load(open(os.path.join(ROOT, "cad", "exports", "validation_results.json"), encoding="utf-8"))
    dims = {d["dimension"]: d for d in vr["dimensions"]}
    its = items()
    by_class = {}
    for i in its:
        k = classify(i)
        by_class[k] = by_class.get(k, 0.0) + i["m"]
    return dict(
        cad_rev=vr["cad_rev"], cad_date=vr["date"], cad_summary=vr["summary"], motor_status=A.MOTOR_STATUS,
        length_mm=dims["Overall airframe length"]["cad"], body_od_mm=dims["Body OD (BO-401)"]["cad"],
        fin_span_mm=dims["Fin span tip-to-tip"]["cad"], fin_le_mm=dims["Fin root LE station"]["cad"],
        fin_root_mm=vr["fins"]["root"], fin_tip_mm=max(vr["fins"]["cad_tip_z"]) - min(vr["fins"]["cad_tip_z"]),
        fin_sweep_mm=min(vr["fins"]["cad_tip_z"]) - dims["Fin root LE station"]["cad"],
        fin_semispan_mm=(dims["Fin span tip-to-tip"]["cad"] - dims["Body OD (BO-401)"]["cad"]) / 2, fin_t_mm=A.FIN_T, fin_n=A.FIN_N,
        nose_len_mm=dims["Nose exposed length (tip to shoulder)"]["cad"],
        M0_g=R["M0"], Mb_g=R["Mb"], Me_g=R["Me"], cg0_mm=R["cg0"], cgb_mm=R["cgb"], cge_mm=R["cge"],
        cp_mm=R["bw"]["xcp"], sm0=R["sm0"], smb=R["smb"], sme=R["sme"],
        modules={k: dict(m_g=v["m"], x_mm=v["x"]) for k, v in R["modules"].items()},
        items=[dict(id=i["id"], name=i["name"], m_g=i["m"], x_mm=i["x"], data_class=classify(i)) for i in its],
        mass_by_class=by_class,
        stations=dict(fin_le=A.X["fin_le"], mmt=(A.X["mmt_fwd"], A.X["mmt_aft"]), motor=(A.X["motor_fwd"], A.X["motor_aft"]),
                      rail_buttons=(A.X["rb_fwd"], A.X["rb_aft"]), recovery_bay=A.X["recovery_bay"], payload_bay=(A.X["sh_end"], A.X["av_bh_fwd_outer"]),
                      avionics_bay=(A.X["cpl_fwd"], A.X["cpl_aft"])),
    )
