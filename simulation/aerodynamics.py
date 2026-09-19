"""Zero-lift drag build-up for ASTRA-66 (subsonic, M < 0.6), referenced to the body cross-section.

Method (simplified component build-up after Barrowman 1967 / OpenRocket technical documentation):
  Skin friction   Cf = max(0.074 Re^-0.2 [turbulent flat plate], 0.032 (eps/L)^0.2 [roughness limit])
                  Cd_f = Cf [ (1 + 1/(2 fB)) S_body + (1 + 2 t/c) S_fins ] / A_ref        fB = L/D
  Base drag       Cd_b = (0.12 + 0.13 M^2) * A_base/A_ref ; during thrust the MMT bore is taken as filled
                  by exhaust (A_base = A_ref - A_mmt)
  Fin pressure    rounded LE: (1 - M^2)^-0.417 - 1 ; rounded TE: half of base-drag coefficient,
                  applied to the fins' frontal area N t s
  Nose pressure   0 for a tangent ogive at M < 0.6 (ASSUMPTION)
  Protuberances   +PARASITIC fraction of the above for rail buttons, lens cowl, band steps (ASSUMPTION)
Every coefficient is an ASSUMPTION to be replaced by OpenRocket/RASAero cross-checks and flight data.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "analysis"))
import analysis as A  # noqa: E402
import config  # noqa: E402

_SC = config.load_sim_config()
D = A.BODY_OD / 1000.0
A_REF = math.pi * D ** 2 / 4
L = A.X["end"] / 1000.0
FINENESS = L / D
ROUGHNESS = _SC["aerodynamics"]["surface_roughness_m"]         # ASSUMPTION (sim_config.json)
PARASITIC = _SC["aerodynamics"]["protuberance_fraction"]       # ASSUMPTION (sim_config.json)
A_MMT = math.pi * (A.MMT_ID / 2000.0) ** 2   # burn-phase base-drag relief; MMT_ID comes from motor_config.json (PLACEHOLDER while unverified)


def _nose_wetted_area(n=400):
    s = 0.0
    for i in range(n):
        x0, x1 = A.NC_L * i / n, A.NC_L * (i + 1) / n
        r0, r1 = A.ogive_r(x0), A.ogive_r(x1)
        s += math.pi * (r0 + r1) * math.hypot(x1 - x0, r1 - r0)
    return s / 1e6


S_NOSE = _nose_wetted_area()
S_BODY = S_NOSE + math.pi * D * (L - A.NC_L / 1000.0)
_fin_area, _ = A.fin_geom()
S_FINS = 2 * A.FIN_N * _fin_area / 1e6
T_OVER_C = A.FIN_T / ((A.FIN_CR + A.FIN_CT) / 2)
FIN_FRONTAL = A.FIN_N * (A.FIN_T / 1000.0) * (A.FIN_S / 1000.0)


def skin_friction(re):
    re = max(re, 1e4)
    return max(0.074 * re ** -0.2, 0.032 * (ROUGHNESS / L) ** 0.2)


def drag_coefficient(mach, re, thrusting):
    mach = min(mach, 0.6)
    cf = skin_friction(re)
    friction = cf * ((1 + 1 / (2 * FINENESS)) * S_BODY + (1 + 2 * T_OVER_C) * S_FINS) / A_REF
    base_coef = 0.12 + 0.13 * mach ** 2
    base = base_coef * ((A_REF - A_MMT) if thrusting else A_REF) / A_REF
    fin_pressure = FIN_FRONTAL / A_REF * (((1 - mach ** 2) ** -0.417 - 1) + base_coef / 2)
    sub = friction + base + fin_pressure
    return dict(friction=friction, base=base, fin_pressure=fin_pressure, nose_pressure=0.0, parasitic=PARASITIC * sub,
                total=sub * (1 + PARASITIC), cf=cf)


def geometry():
    return dict(A_ref_m2=A_REF, length_m=L, fineness=FINENESS, S_body_wet_m2=S_BODY, S_nose_wet_m2=S_NOSE, S_fins_wet_m2=S_FINS,
                fin_t_over_c=T_OVER_C, roughness_m=ROUGHNESS, parasitic_fraction=PARASITIC)
