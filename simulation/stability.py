"""Static-stability analysis: CP (independent Barrowman implementation), CG and static margin.

Barrowman (1967), subsonic, small angle of attack, body lift neglected:
  Nose (tangent ogive):  CNa_N = 2,  X_N = 0.466 L_N
  Fins:  CNa_F = (1 + R/(S+R)) * 4 N (S/d)^2 / (1 + sqrt(1 + (2 L_F/(C_R + C_T))^2)),
         L_F = sqrt(S^2 + (X_R + C_T/2 - C_R/2)^2)
         X_F = X_B + X_R/3 (C_R + 2 C_T)/(C_R + C_T) + [ (C_R + C_T) - C_R C_T/(C_R + C_T) ] / 6
  CP = (CNa_N X_N + CNa_F X_F) / (CNa_N + CNa_F);   static margin SM = (CP - CG) / d   [calibres]

This module deliberately re-implements the equations (instead of calling analysis.barrowman) and feeds them
with the fin/nose geometry MEASURED FROM THE CAD MESHES, so it independently cross-checks the analysis.

Engineering requirement used for evaluation (a design target, NOT a flight approval):
  REQ-STAB-1  1.5 <= SM <= 3.0 cal at rail exit
  REQ-STAB-2  SM >= 1.5 cal throughout powered flight
  REQ-STAB-3  SM <= 3.0 cal at liftoff (limits weathercocking at low rail-exit speed)
"""
import math

SM_MIN, SM_MAX = 1.5, 3.0


def barrowman_cp(d, nose_len, fin_le, cr, ct, s, xr, n):
    R = d / 2
    cn_n, x_n = 2.0, 0.466 * nose_len
    lf = math.sqrt(s ** 2 + (xr + ct / 2 - cr / 2) ** 2)
    cn_f = (1 + R / (s + R)) * (4 * n * (s / d) ** 2) / (1 + math.sqrt(1 + (2 * lf / (cr + ct)) ** 2))
    x_f = fin_le + xr / 3 * (cr + 2 * ct) / (cr + ct) + ((cr + ct) - cr * ct / (cr + ct)) / 6
    cn = cn_n + cn_f
    return dict(cp=(cn_n * x_n + cn_f * x_f) / cn, cn_alpha=cn, cn_nose=cn_n, cn_fins=cn_f, x_nose=x_n, x_fins=x_f)


def cp_from_cad(audit):
    return barrowman_cp(audit["body_od_mm"], audit["nose_len_mm"], audit["fin_le_mm"], audit["fin_root_mm"], audit["fin_tip_mm"],
                        audit["fin_semispan_mm"], audit["fin_sweep_mm"], audit["fin_n"])


def margin(cp, cg, d):
    return (cp - cg) / d


def check(sm_rail, sm_min_powered, sm_liftoff):
    return [
        dict(id="REQ-STAB-1", requirement="1.5 <= SM <= 3.0 cal at rail exit", value=sm_rail, ok=SM_MIN <= sm_rail <= SM_MAX),
        dict(id="REQ-STAB-2", requirement="SM >= 1.5 cal throughout powered flight", value=sm_min_powered, ok=sm_min_powered >= SM_MIN),
        dict(id="REQ-STAB-3", requirement="SM <= 3.0 cal at liftoff", value=sm_liftoff, ok=sm_liftoff <= SM_MAX),
    ]


def ballast_for(sm_target, cg, mass_g, cp, d, x_ballast):
    """Nose ballast (g) at station x_ballast needed to raise the margin to sm_target (0 if already met)."""
    x_t = cp - sm_target * d
    if cg <= x_t:
        return 0.0
    return mass_g * (cg - x_t) / (x_t - x_ballast)
