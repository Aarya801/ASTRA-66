"""
ASTRA-66 modular student rocket airframe -- parameter set and non-propulsion analysis.

Single source of truth: every number used by the drawings, the BOM, the OpenSCAD
parameter file and the HTML engineering package comes from this module.

Units: mm, g, N, s, m/s unless stated.

Provenance tags (required by the project brief):
  CALC  = CALCULATED VALUE          (derived here from other values)
  ASM   = ASSUMPTION                (engineering estimate -> must be verified / measured)
  USER  = USER-SUPPLIED VALUE       (you must provide it: measured part, range data ...)
  COTS  = COMMERCIAL COMPONENT SPECIFICATION (take from the manufacturer's current documents)

Nothing about propulsion is designed or optimised here. The motor is an EXTERNAL,
commercially certified component; the motor numbers below are PLACEHOLDERS that only
exist so the CG can be computed, and must be replaced with the selected motor's
published certification data.
"""
import json
import math
import os

CALC, ASM, USER, COTS = "CALC", "ASM", "USER", "COTS"
G0 = 9.81

P = {}
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ----------------------------------------------------------------------------- external motor system data
# The certified motor and its commercial retainer are EXTERNAL components. Their data live in ONE file,
# simulation/motor_config.json. status = "PLACEHOLDER" (planning numbers, not a real product) or
# "MANUFACTURER_DATA" (values copied from the selected certified product's published documentation, with
# source, verifier and date recorded). Nothing here designs or modifies a motor.
MOTOR_CONFIG_FILE = os.path.join(PROJECT_ROOT, "simulation", "motor_config.json")


def _load_motor_config():
    with open(MOTOR_CONFIG_FILE, encoding="utf-8") as fh:
        cfg = json.load(fh)
    status = cfg.get("status")
    if status not in ("PLACEHOLDER", "MANUFACTURER_DATA"):
        raise ValueError("simulation/motor_config.json: status must be PLACEHOLDER or MANUFACTURER_DATA")
    numeric = [("motor", "length_mm"), ("motor", "loaded_mass_g"), ("motor", "burnout_mass_g"), ("retainer", "body_od_mm"),
               ("retainer", "length_aft_of_airframe_mm"), ("retainer", "mass_g"), ("motor_mount", "mmt_id_mm"),
               ("motor_mount", "mmt_length_mm"), ("motor_mount", "mmt_aft_extension_mm")]
    bad = [f"{a}.{b}" for a, b in numeric if not isinstance(cfg.get(a, {}).get(b), (int, float)) or cfg[a][b] <= 0]
    if bad:
        raise ValueError("simulation/motor_config.json: missing or non-positive " + ", ".join(bad))
    if status == "MANUFACTURER_DATA":
        req = [("motor", "designation"), ("motor", "manufacturer"), ("motor", "certification"), ("motor", "data_source"),
               ("retainer", "model"), ("retainer", "data_source"), ("verification", "verified_by"), ("verification", "date")]
        missing = [f"{a}.{b}" for a, b in req if not cfg.get(a, {}).get(b)]
        if missing:
            raise ValueError("simulation/motor_config.json: MANUFACTURER_DATA requires " + ", ".join(missing))
        if cfg["motor"]["burnout_mass_g"] >= cfg["motor"]["loaded_mass_g"]:
            raise ValueError("simulation/motor_config.json: burnout mass must be below loaded mass")
    return cfg


MOTOR_CFG = _load_motor_config()
MOTOR_STATUS = MOTOR_CFG["status"]


def _mnote(section, what):
    if MOTOR_STATUS == "PLACEHOLDER":
        return f"PLACEHOLDER ONLY ({what}). Replace via simulation/motor_config.json with the selected certified product's published data."
    v = MOTOR_CFG["verification"]
    return f"{what}: {MOTOR_CFG[section].get('data_source')} (motor_config.json, verified {v['date']} by {v['verified_by']})."


def p(name, value, unit, tag, note):
    P[name] = dict(name=name, v=value, u=unit, tag=tag, note=note)
    return value


# ----------------------------------------------------------------------------- airframe
BODY_OD = p("BODY_OD", 66.0, "mm", ASM, "Nominal 66 mm-class spiral kraft/phenolic body tube. MEASURE the purchased tube and update.")
BODY_ID = p("BODY_ID", 64.0, "mm", ASM, "Measure purchased tube (3 places, 2 axes). Drives every shoulder, ring and bulkhead fit.")
CPL_OD = p("CPL_OD", 63.8, "mm", ASM, "Matching commercial coupler. Must slip-fit BODY_ID (0.1-0.4 mm diametral clearance).")
CPL_ID = p("CPL_ID", 61.0, "mm", ASM, "Measure purchased coupler.")
TUBE_RHO = p("TUBE_RHO", 1.00, "g/cm3", ASM, "Effective density of paper/phenolic tube. Verify by weighing a known length.")
FIT_SH = p("FIT_SH", 0.30, "mm", ASM, "Diametral clearance, printed shoulder / ring in tube. Tune with a printed test coupon first.")

# ----------------------------------------------------------------------------- nose
NC_L = p("NC_L", 264.0, "mm", ASM, "Exposed nose length, tangent ogive, fineness 4.0 (NC_L / BODY_OD).")
NC_WALL = p("NC_WALL", 1.2, "mm", ASM, "Printed ogive wall = 3 perimeters x 0.4 mm nozzle.")
NC_SH_L = p("NC_SH_L", 60.0, "mm", ASM, "Shoulder length ~0.9 calibre.")
NC_SH_WALL = p("NC_SH_WALL", 1.6, "mm", ASM, "Shoulder wall (4 perimeters); hosts radial heat-set inserts.")
NC_SPLIT = p("NC_SPLIT", 150.0, "mm", ASM, "Print split station so each half fits a 250 mm Z-height printer.")
NC_BH_T = p("NC_BH_T", 6.0, "mm", ASM, "Printed nose bulkhead / ballast mount thickness.")
BALLAST_ROD_L = p("BALLAST_ROD_L", 80.0, "mm", ASM, "M6 A2 threaded rod length forward of NC-103 (rod is cut to BALLAST_ROD_L + NC_BH_T = 86).")
NC_TIP_SOLID = p("NC_TIP_SOLID", 8.0, "mm", ASM, "Solid printed tip before the internal cavity starts (CAD rev B).")
NC_SPIGOT_L = p("NC_SPIGOT_L", 10.0, "mm", ASM, "NC-101 spigot length aft of the print split (engages NC-102 socket).")
NC_SPLIT_WEB = p("NC_SPLIT_WEB", 2.0, "mm", ASM, "Solid annular web closing NC-101 at the split; the spigot grows from it (CAD rev B, printable).")
NC_SPIGOT_WALL = p("NC_SPIGOT_WALL", 1.6, "mm", ASM, "Spigot wall thickness.")
FIT_SOCKET = p("FIT_SOCKET", 0.2, "mm", ASM, "Diametral clearance spigot-to-socket (I-00, slip fit +0.1/+0.3).")
NC_BASE_RING = p("NC_BASE_RING", 1.6, "mm", ASM, "Closing ring between ogive wall and shoulder at the nose base.")
NC_BOSS_T = p("NC_BOSS_T", 4.4, "mm", ASM, "Radial insert boss depth inside the shoulder (wall + boss = 6.0 >= insert + 0.5).")
NC_LUG_L = p("NC_LUG_L", 12.0, "mm", ASM, "NC-103 mounting lug length (lugs end at the bulkhead forward face, CAD rev B).")
NC_LUG_T = p("NC_LUG_T", 6.0, "mm", ASM, "NC-103 mounting lug radial depth.")
NC_SCREW_ANG = p("NC_SCREW_ANG", [90, 210, 330], "deg", ASM, "Angular positions of the 3 radial nose screws (I-01).")
NC_LUG_ANG = p("NC_LUG_ANG", [30, 150, 270], "deg", ASM, "Angular positions of the 3 NC-103 lugs.")

# ----------------------------------------------------------------------------- payload
PL_L = p("PL_L", 250.0, "mm", ASM, "Payload tube length. Clear payload bay = PL_L - NC_SH_L - AV insertion - bulkheads.")
CAM_LENS_HOLE = p("CAM_LENS_HOLE", 14.0, "mm", USER, "Set from the chosen camera's lens barrel diameter + 1 mm.")
CAM_MASS = p("CAM_MASS", 35.0, "g", USER, "Weigh the chosen camera (with its cable). 35 g is a planning placeholder.")
CAM_OFF = p("CAM_OFF", 36.0, "mm", ASM, "Camera lens-hole station aft of the nose shoulder end (STA 360).")
CAM_ANG = p("CAM_ANG", 270, "deg", ASM, "Camera / lens-cowl angular position.")
CAM_TILT = p("CAM_TILT", 15.0, "deg", ASM, "Lens axis tilted aft from radial (matches the PL-204 window).")
CAM_W = p("CAM_W", 26.0, "mm", USER, "Camera body width (PLACEHOLDER: measure your camera). Rev B: 29 -> 26; the rev A 29 x 16 x 45 placeholder interfered with the tube wall at 15 deg tilt.")
CAM_H = p("CAM_H", 14.0, "mm", USER, "Camera body depth along the lens axis (PLACEHOLDER; rev A 16).")
CAM_LEN = p("CAM_LEN", 40.0, "mm", USER, "Camera body length (PLACEHOLDER; rev A 45). The CAD re-seats any size inside the bore; the pipeline then checks tray clearance.")
CAM_LENS_L = p("CAM_LENS_L", 5.0, "mm", USER, "Lens barrel protrusion from the camera face (PLACEHOLDER).")
HATCH_OFF = p("HATCH_OFF", 71.0, "mm", ASM, "Hatch centre station aft of the nose shoulder end (STA 395).")
HATCH_ANG = p("HATCH_ANG", 90, "deg", ASM, "Hatch angular position (over the GPS).")
HATCH_W = p("HATCH_W", 25.0, "mm", ASM, "Hatch cut-out chord width.")
HATCH_L = p("HATCH_L", 40.0, "mm", ASM, "Hatch cut-out axial length.")
HATCH_GAP = p("HATCH_GAP", 0.3, "mm", ASM, "Edge gap between hatch panel and cut-out.")
HATCH_SCREW_OFF = p("HATCH_SCREW_OFF", 17.0, "mm", ASM, "Hatch screws at hatch centre +/- this (on the frame ledges).")
FRAME_L = p("FRAME_L", 54.0, "mm", ASM, "PL-206 doubler frame axial length.")
FRAME_W = p("FRAME_W", 40.0, "mm", ASM, "PL-206 doubler frame chord width.")
FRAME_T = p("FRAME_T", 2.0, "mm", ASM, "PL-206 frame thickness (bosses 4.5).")
TRAY_L = p("TRAY_L", 90.0, "mm", ASM, "PL-202 overall length including the foot.")
TRAY_W = p("TRAY_W", 50.0, "mm", ASM, "PL-202 plate width.")
TRAY_T = p("TRAY_T", 2.5, "mm", ASM, "PL-202 plate thickness.")
TRAY_FOOT_T = p("TRAY_FOOT_T", 8.0, "mm", ASM, "PL-202 foot thickness (bears on AV-303).")
TRAY_HOLE_X = p("TRAY_HOLE_X", 7.0, "mm", ASM, "Tray screw holes at x = +/- this (CAD rev B: clears tee-nut flanges).")
TRAY_HOLE_Y = p("TRAY_HOLE_Y", -14.0, "mm", ASM, "Tray screw holes at y = this (below the sled plane).")

# ----------------------------------------------------------------------------- avionics bay
AV_CPL_L = p("AV_CPL_L", 170.0, "mm", ASM, "Coupler length = 70 insertion + 30 switch band + 70 insertion.")
AV_INS = p("AV_INS", 70.0, "mm", ASM, "Coupler insertion each side (~1.1 calibre; >= 1 calibre is the usual rule of thumb).")
AV_BAND_L = p("AV_BAND_L", 30.0, "mm", ASM, "Switch band length (exposed airframe ring).")
AV_BH_T = p("AV_BH_T", 6.0, "mm", ASM, "Each bulkhead disc thickness (birch ply); 2 discs per bulkhead.")
AV_ROD_SP = p("AV_ROD_SP", 40.0, "mm", ASM, "Threaded-rod spacing (M4) in the sled plane.")
SLED_L = p("SLED_L", 140.0, "mm", ASM, "Electronics sled length.")
SLED_W = p("SLED_W", 52.0, "mm", ASM, "Electronics sled width (fits CPL_ID with rod sleeves).")
SLED_T = p("SLED_T", 3.0, "mm", ASM, "Sled thickness (PETG, 100% infill between rod sleeves).")
SLED_FWD_GAP = p("SLED_FWD_GAP", 7.0, "mm", ASM, "Gap AV-303 to sled = forward AV-312 spacer length.")
GASKET_T = p("GASKET_T", 0.5, "mm", ASM, "AV-309 face gasket compressed thickness (1.5 mm foam free). CAD rev B: moves AV-304 outer disc aft by this.")
SW_ANG = p("SW_ANG", 90, "deg", ASM, "Arming-switch access angle.")
SW_HOLE_D = p("SW_HOLE_D", 8.0, "mm", ASM, "Switch access hole through AV-302 + AV-301.")
SW_TOWER_H = p("SW_TOWER_H", 20.0, "mm", USER, "Switch tower height above sled; set so the switch actuator sits ~1 mm below CPL_ID.")
STATIC_PORT_D = p("STATIC_PORT_D", 2.0, "mm", ASM, "4 static ports at 45/135/225/315 deg (size per sensor maker guidance).")
HARNESS_D = p("HARNESS_D", 8.0, "mm", ASM, "Harness hole through AV-303 (grommet).")
HARNESS_Y = p("HARNESS_Y", 14.0, "mm", ASM, "Harness hole centre offset toward the switch side (+Y).")
BAT_L = p("BAT_L", 55.0, "mm", USER, "Battery length (PLACEHOLDER: set from purchased cell).")
BAT_W = p("BAT_W", 28.0, "mm", USER, "Battery width (PLACEHOLDER; max 28.8 to clear the rod sleeves).")
BAT_H = p("BAT_H", 9.0, "mm", USER, "Battery thickness (PLACEHOLDER).")
ROD_L = p("ROD_L", 190.0, "mm", ASM, "AV-305 M4 rod length (fwd bulkhead face to 1.7 mm past the aft nut).")

# ----------------------------------------------------------------------------- booster
BO_L = p("BO_L", 600.0, "mm", ASM, "Booster tube length (recovery bay + fin can).")
MMT_OD = p("MMT_OD", 31.0, "mm", ASM, "29 mm-class motor mount tube OD. Measure purchased tube.")
MMT_ID = p("MMT_ID", float(MOTOR_CFG["motor_mount"]["mmt_id_mm"]), "mm", COTS, _mnote("motor_mount", "MMT bore for the motor casing"))
MMT_L = p("MMT_L", float(MOTOR_CFG["motor_mount"]["mmt_length_mm"]), "mm", COTS, _mnote("motor_mount", "MMT length >= longest motor + retainer requirement"))
MMT_AFT_EXT = p("MMT_AFT_EXT", float(MOTOR_CFG["motor_mount"]["mmt_aft_extension_mm"]), "mm", COTS, _mnote("motor_mount", "MMT protrusion aft of airframe for the retainer"))
CR_T = p("CR_T", 6.0, "mm", ASM, "Forward centering ring thickness (birch ply, recovery-load anchor ring).")
CORE_RING_T = p("CORE_RING_T", 8.0, "mm", ASM, "Fin-can core ring thickness (ASA print).")
CORE_RAIL_T = p("CORE_RAIL_T", 1.6, "mm", ASM, "Fin guide rail thickness.")
LOCK_T = p("LOCK_T", 6.0, "mm", ASM, "Aft fin lock ring thickness (birch ply: heat tolerant near motor).")
RET_CLEAR_D = p("RET_CLEAR_D", float(MOTOR_CFG["retainer"]["body_od_mm"]) + 1.0, "mm", COTS, "Lock-ring bore = retainer body OD + 1 mm. " + _mnote("retainer", "retainer body OD"))

FIN_N = p("FIN_N", 4, "-", ASM, "Fin count. 4 fins -> symmetric layout for rail buttons, camera and slide-in guides.")
FIN_CR = p("FIN_CR", 150.0, "mm", ASM, "Root chord (exposed).")
FIN_CT = p("FIN_CT", 60.0, "mm", ASM, "Tip chord.")
FIN_S = p("FIN_S", 60.0, "mm", ASM, "Semi-span (exposed, from body surface). Selected by trade study for 2-3 cal margin.")
FIN_XR = p("FIN_XR", 70.0, "mm", ASM, "Leading-edge sweep length (root LE to tip LE, parallel to axis). Tip TE stays 20 mm forward of the tail.")
FIN_T = p("FIN_T", 3.0, "mm", ASM, "Fin thickness: 3 mm aircraft birch ply (baseline) or 3.2 mm G10 (upgrade, heavier).")
FIN_TAB_FWD = p("FIN_TAB_FWD", 10.0, "mm", ASM, "Tab starts this far aft of root LE.")
FIN_SLOT_CLR = p("FIN_SLOT_CLR", 0.3, "mm", ASM, "Tube slot width = FIN_T + FIN_SLOT_CLR.")
FIN_GUIDE_CLR = p("FIN_GUIDE_CLR", 0.2, "mm", ASM, "Printed guide slot width = FIN_T + FIN_GUIDE_CLR.")
FIN_TAB_CLR = p("FIN_TAB_CLR", 0.2, "mm", ASM, "Radial clearance between fin tab root and the BO-403 tab floor.")
LOCK_SCREW_R = p("LOCK_SCREW_R", 26.0, "mm", ASM, "Pitch radius of the 4 lock-ring screws (45/135/225/315 deg).")
RB_FWD_OFF = p("RB_FWD_OFF", 9.0, "mm", ASM, "Forward rail button this far forward of the MMT forward end (on BO-409).")
RB_AFT_OFF = p("RB_AFT_OFF", 29.0, "mm", ASM, "Aft rail button this far forward of the tail (on BO-403 boss).")
RB_ANG = p("RB_ANG", 45, "deg", ASM, "Rail-button line, midway between fins 1 and 2.")
KEVLAR_NOTCH_ANG = p("KEVLAR_NOTCH_ANG", 225, "deg", ASM, "Aramid leader notch in BO-404 (opposite the rail line).")

# ----------------------------------------------------------------------------- hardware & CAD
INS_M3_D = p("INS_M3_D", 4.0, "mm", ASM, "Hole for M3 brass heat-set insert (use the insert maker's value).")
INS_M3_L = p("INS_M3_L", 5.0, "mm", ASM, "M3 insert length (insert maker).")
INS_M25_D = p("INS_M25_D", 3.6, "mm", ASM, "Hole for M2.5 heat-set insert (insert maker).")
INS_M25_L = p("INS_M25_L", 4.0, "mm", ASM, "M2.5 insert length (insert maker).")
INS_M4_D = p("INS_M4_D", 5.6, "mm", ASM, "Hole for M4 heat-set insert in printed bosses (insert maker).")
INS_M4_L = p("INS_M4_L", 6.0, "mm", ASM, "M4 insert length (insert maker).")
CLR_M25 = p("CLR_M25", 2.9, "mm", COTS, "ISO 273 medium clearance hole, M2.5.")
CLR_M3 = p("CLR_M3", 3.4, "mm", COTS, "ISO 273 medium clearance hole, M3.")
CLR_M4 = p("CLR_M4", 4.5, "mm", COTS, "ISO 273 medium clearance hole, M4.")
CLR_M6 = p("CLR_M6", 6.5, "mm", ASM, "Close clearance for the M6 eyebolt / ballast rod.")
TNUT_BARREL_D = p("TNUT_BARREL_D", 5.5, "mm", ASM, "M4 tee-nut barrel hole (confirm with purchased tee-nut).")
TNUT_FLANGE_D = p("TNUT_FLANGE_D", 15.0, "mm", ASM, "M4 tee-nut flange diameter (confirm; used for clearance checks).")
TNUT_FLANGE_T = p("TNUT_FLANGE_T", 1.5, "mm", ASM, "M4 tee-nut flange thickness (confirm).")
NUT_M4_H = p("NUT_M4_H", 5.0, "mm", COTS, "DIN 985 M4 nylock nut height (verify against purchased part).")
WASHER_M4_T = p("WASHER_M4_T", 0.8, "mm", COTS, "ISO 7089 M4 washer thickness.")
SHCS_M3_DK = p("SHCS_M3_DK", 5.5, "mm", COTS, "ISO 4762 M3 socket-head diameter (tool-access checks).")
RB_ENV_D = p("RB_ENV_D", 12.0, "mm", COTS, "Rail-button ENVELOPE placeholder diameter; real size from button maker.")
RB_ENV_H = p("RB_ENV_H", 9.0, "mm", COTS, "Rail-button ENVELOPE placeholder standoff; real size from button maker.")
EYE_ENV_D = p("EYE_ENV_D", 24.0, "mm", COTS, "M6 eyebolt ENVELOPE placeholder (eye OD); from eyebolt maker.")
EYE_ENV_L = p("EYE_ENV_L", 36.0, "mm", COTS, "M6 eyebolt ENVELOPE placeholder length aft of AV-304.")
RET_ENV_L = p("RET_ENV_L", float(MOTOR_CFG["retainer"]["length_aft_of_airframe_mm"]), "mm", COTS, _mnote("retainer", "retainer length aft of airframe"))
FN = p("FN", 96, "-", ASM, "OpenSCAD facets per full circle (CAD resolution only).")

PETG_RHO = p("PETG_RHO", 1.27, "g/cm3", ASM, "Typical PETG filament density (check spool datasheet).")
ASA_RHO = p("ASA_RHO", 1.07, "g/cm3", ASM, "Typical ASA filament density (check spool datasheet).")
PLY_RHO = p("PLY_RHO", 0.68, "g/cm3", ASM, "Aircraft birch plywood, typical. Weigh your sheet.")
STEEL_RHO = p("STEEL_RHO", 7.9, "g/cm3", ASM, "Stainless steel A2.")

# ----------------------------------------------------------------------------- motor (external)
MOTOR_L = p("MOTOR_L", float(MOTOR_CFG["motor"]["length_mm"]), "mm", COTS, _mnote("motor", "motor length"))
MOTOR_M0 = p("MOTOR_M0", float(MOTOR_CFG["motor"]["loaded_mass_g"]), "g", COTS, _mnote("motor", "loaded motor mass"))
MOTOR_MB = p("MOTOR_MB", float(MOTOR_CFG["motor"]["burnout_mass_g"]), "g", COTS, _mnote("motor", "burnout motor mass"))
RET_MASS = p("RET_MASS", float(MOTOR_CFG["retainer"]["mass_g"]), "g", COTS, _mnote("retainer", "retainer mass"))

# ----------------------------------------------------------------------------- recovery / environment
V_DESC = p("V_DESC", 5.0, "m/s", ASM, "Target descent rate under main parachute.")
CHUTE_D = p("CHUTE_D", 1067.0, "mm", ASM, "Selected nominal parachute diameter (42 in class) from the descent-rate calculation.")
CHUTE_CD = p("CHUTE_CD", 0.80, "-", ASM, "Parachute drag coefficient on nominal area. Replace with the chute manufacturer's figure if published.")
RHO_AIR = p("RHO_AIR", 1.225, "kg/m3", ASM, "ISA sea level. Use site altitude/temperature in the simulator (USER).")
SHOCK_K = p("SHOCK_K", 1.8, "-", ASM, "Opening-shock amplification over steady drag (conservative planning value).")
N_AX = p("N_AX", 15.0, "g", ASM, "Design axial load factor. REPLACE with 1.5 x simulated peak acceleration of the chosen motor.")
V_MAX = p("V_MAX", 90.0, "m/s", ASM, "Design velocity limit for this airframe (printed nose, kraft tubes, ply fins).")
ALPHA_GUST = p("ALPHA_GUST", 10.0, "deg", ASM, "Angle of attack for fin side-load check (rail exit in cross-wind).")
TAU_BOND = p("TAU_BOND", 1.0, "MPa", ASM, "Allowable shear on epoxy-to-paper tube bonds (paper delamination governs; very conservative).")
PLY_SIG = p("PLY_SIG", 40.0, "MPa", ASM, "Allowable bending stress, birch ply (conservative vs typical published values).")
PLY_G = p("PLY_G", 0.60, "GPa", ASM, "In-plane shear modulus, 3 mm birch ply (for flutter screening only).")
TUBE_E = p("TUBE_E", 3.0, "GPa", ASM, "Axial modulus of kraft/phenolic tube (vibration order-of-magnitude only).")
A2_70_PROOF = p("A2_70_PROOF", 450.0, "MPa", COTS, "ISO 3506-1 property class A2-70 minimum 0.2% proof stress.")
M4_AS = p("M4_AS", 8.78, "mm2", COTS, "ISO 898 / ISO 724 tensile stress area, M4 coarse.")
RAIL = p("RAIL", "1010", "-", USER, "Launch rail profile offered by YOUR range. Rail buttons must match it.")
RAIL_L = p("RAIL_L", 1.0, "m", USER, "Usable rail length at YOUR range (planning value 1.0 m).")

# ============================================================================ stations
X = {}
X["nc_base"] = NC_L
X["sh_end"] = NC_L + NC_SH_L
X["pl_end"] = NC_L + PL_L
X["band_end"] = X["pl_end"] + AV_BAND_L
X["end"] = X["band_end"] + BO_L
X["cpl_fwd"] = X["pl_end"] - AV_INS
X["cpl_aft"] = X["band_end"] + AV_INS
X["av_bh_fwd_outer"] = X["cpl_fwd"] - AV_BH_T
X["av_bh_aft_outer"] = X["cpl_aft"] + GASKET_T + AV_BH_T
X["sled_fwd"] = X["cpl_fwd"] + AV_BH_T + SLED_FWD_GAP
X["sled_aft"] = X["sled_fwd"] + SLED_L
X["mmt_fwd"] = X["end"] + MMT_AFT_EXT - MMT_L
X["mmt_aft"] = X["end"] + MMT_AFT_EXT
X["fin_le"] = X["end"] - FIN_CR
X["core_fwd"] = X["fin_le"] + FIN_TAB_FWD - CORE_RING_T
X["core_aft"] = X["end"] - LOCK_T
X["tab_fwd"] = X["fin_le"] + FIN_TAB_FWD
X["tab_aft"] = X["end"] - LOCK_T
X["motor_aft"] = X["mmt_aft"]
X["motor_fwd"] = X["motor_aft"] - MOTOR_L
X["rb_fwd"] = X["mmt_fwd"] - RB_FWD_OFF
X["rb_aft"] = X["end"] - RB_AFT_OFF
X["cam"] = X["sh_end"] + CAM_OFF
X["hatch"] = X["sh_end"] + HATCH_OFF
X["nc_screws"] = X["nc_base"] + NC_SH_L / 2
X["tray_fwd"] = X["av_bh_fwd_outer"] - TRAY_L
X["recovery_bay"] = (X["av_bh_aft_outer"], X["mmt_fwd"])

# Tab depth measured from the fin root line (tube OD). CAD rev B: the tab must clear the COTS retainer body
# (RET_CLEAR_D) so a fin can slide out aft with the retainer installed; the tab rests on BO-403 tab floors.
R_TAB_FLOOR = max(MMT_OD / 2, RET_CLEAR_D / 2)
FIN_TAB_H = BODY_OD / 2 - R_TAB_FLOOR - FIN_TAB_CLR
FIN_TAB_L = X["tab_aft"] - X["tab_fwd"]
PAYLOAD_BAY_CLEAR = X["av_bh_fwd_outer"] - X["sh_end"]
RECOVERY_BAY_L = X["mmt_fwd"] - X["av_bh_aft_outer"]


# ============================================================================ geometry helpers
def tube_g(od, idd, L, rho):
    return math.pi / 4 * (od ** 2 - idd ** 2) * L * rho / 1000.0


def disc_g(od, t, rho, idd=0.0):
    return tube_g(od, idd, t, rho)


def ogive_rho(R=BODY_OD / 2, L=NC_L):
    return (R * R + L * L) / (2 * R)


def ogive_r(x, R=BODY_OD / 2, L=NC_L):
    rho = ogive_rho(R, L)
    return math.sqrt(max(rho * rho - (L - x) ** 2, 0.0)) + R - rho


def ogive_shell(x0, x1, wall, rho_g, n=600):
    """Mass (g) and CG station of a thin ogive shell between x0..x1 (area * wall)."""
    A = Ax = 0.0
    dx = (x1 - x0) / n
    for i in range(n):
        xa, xb = x0 + i * dx, x0 + (i + 1) * dx
        ra, rb = ogive_r(xa), ogive_r(xb)
        ds = math.hypot(dx, rb - ra)
        dA = math.pi * (ra + rb) * ds
        A += dA
        Ax += dA * (xa + xb) / 2
    return A * wall * rho_g / 1000.0, Ax / A


def fin_geom(cr=FIN_CR, ct=FIN_CT, s=FIN_S, xr=FIN_XR):
    area = (cr + ct) / 2 * s
    xc = (cr ** 2 + cr * ct + ct ** 2 + xr * (cr + 2 * ct)) / (3 * (cr + ct))  # centroid from root LE
    return area, xc


def fin_mass(cr=FIN_CR, ct=FIN_CT, s=FIN_S, xr=FIN_XR, t=FIN_T, rho=PLY_RHO):
    area, xc = fin_geom(cr, ct, s, xr)
    tab = FIN_TAB_H * FIN_TAB_L
    finish = 1.10  # ASSUMPTION: sealer + primer + paint adds ~10 %
    m = (area + tab) * t * rho / 1000.0 * finish
    x_ext = X["end"] - cr + xc
    x_tab = X["tab_fwd"] + FIN_TAB_L / 2
    xcg = (area * x_ext + tab * x_tab) / (area + tab)
    return m, xcg


# ============================================================================ mass budget
def build_mass_items(fin=None, motor_m=None):
    fin = fin or dict(cr=FIN_CR, ct=FIN_CT, s=FIN_S, xr=FIN_XR)
    items = []

    def add(pid, name, module, m, x, tag, note=""):
        items.append(dict(id=pid, name=name, module=module, m=m, x=x, tag=tag, note=note))

    # --- nose
    m, x = ogive_shell(0.5, NC_SPLIT, NC_WALL, PETG_RHO)
    r_split = ogive_r(NC_SPLIT)
    sp_od = 2 * (r_split - NC_WALL) - FIT_SH
    m += tube_g(sp_od, sp_od - 3.2, 10, PETG_RHO)
    add("NC-101", "Nose tip section (ogive 0-150, spigot)", "100 Nose", m, x, CALC, "PETG shell, area x wall")
    m2, x2 = ogive_shell(NC_SPLIT, NC_L, NC_WALL, PETG_RHO)
    sh_od = BODY_ID - FIT_SH
    msh = tube_g(sh_od, sh_od - 2 * NC_SH_WALL, NC_SH_L, PETG_RHO)
    mb = 4.0  # ASSUMPTION: insert bosses + lugs
    tot = m2 + msh + mb
    xx = (m2 * x2 + msh * (NC_L + NC_SH_L / 2) + mb * X["nc_screws"]) / tot
    add("NC-102", "Nose base + shoulder", "100 Nose", tot, xx, CALC, "incl. 4 g bosses (ASM)")
    add("NC-103", "Nose bulkhead / ballast mount", "100 Nose",
        disc_g(sh_od - 2 * NC_SH_WALL - 0.2, NC_BH_T, PETG_RHO) * 0.6, X["sh_end"] - NC_BH_T / 2, CALC, "60 % effective infill (ASM)")
    rod_l = BALLAST_ROD_L + NC_BH_T                  # rev B: rod runs through NC-103 (86 mm, per BOM)
    rod = 20.1 * rod_l * STEEL_RHO / 1000.0          # 20.1 mm2 = M6 tensile stress area
    add("NC-104", "Ballast rod M6x86 + 2 nylock + 2 washers", "100 Nose", rod + 7.2,
        X["sh_end"] - BALLAST_ROD_L + rod_l / 2, CALC, "no ballast washers in baseline")
    add("NC-105", "Nose fasteners (6x M3 insert, 6x M3 screw)", "100 Nose", 8.0, X["nc_screws"], ASM)

    # --- payload
    add("PL-201", "Payload tube", "200 Payload", tube_g(BODY_OD, BODY_ID, PL_L, TUBE_RHO), NC_L + PL_L / 2, CALC)
    add("PL-202", "GPS / sensor tray + bracket", "200 Payload", 15.0, X["tray_fwd"] + 45, ASM)
    add("PL-203", "Camera cradle", "200 Payload", 10.0, X["cam"], ASM)
    add("PL-204", "Lens cowl", "200 Payload", 4.0, X["cam"], ASM)
    add("PL-205/206", "Access hatch + doubler frame", "200 Payload", 8.0, X["hatch"], ASM)
    add("EL-GPS", "GPS module + patch antenna", "200 Payload", 20.0, X["tray_fwd"] + 30, ASM, "weigh")
    add("EL-CAM", "Mini camera (user-selected)", "200 Payload", CAM_MASS, X["cam"], USER, "weigh")

    # --- avionics bay
    xav = (X["cpl_fwd"] + X["cpl_aft"]) / 2
    add("AV-301", "Coupler tube", "300 Avionics", tube_g(CPL_OD, CPL_ID, AV_CPL_L, TUBE_RHO), xav, CALC)
    add("AV-302", "Switch band", "300 Avionics", tube_g(BODY_OD, BODY_ID, AV_BAND_L, TUBE_RHO), xav, CALC)
    bh = disc_g(CPL_ID - 0.2, AV_BH_T, PLY_RHO) + disc_g(CPL_OD, AV_BH_T, PLY_RHO)
    add("AV-303", "Forward bulkhead (2-ply laminate) + 2 M4 inserts", "300 Avionics", bh + 4.0, X["cpl_fwd"], CALC)
    add("AV-304", "Aft bulkhead (2-ply laminate)", "300 Avionics", bh, X["cpl_aft"], CALC)
    add("AV-311", "M6 forged eyebolt + nut + washers", "300 Avionics", 25.0, X["av_bh_aft_outer"] + 18, ASM, "weigh")
    rods = 2 * M4_AS * 190 * STEEL_RHO / 1000.0 + 6.0
    add("AV-305", "2x M4x190 A2 rods, nuts, washers", "300 Avionics", rods, xav + 5, CALC)
    add("AV-306", "Electronics sled", "300 Avionics", 25.0, (X["sled_fwd"] + X["sled_aft"]) / 2, ASM)
    add("EL-AV", "Avionics set: MCU, IMU, baro, SD, radio, buzzer, wiring", "300 Avionics", 59.0,
        (X["sled_fwd"] + X["sled_aft"]) / 2, ASM, "sum of module estimates -- weigh")
    xbat = X["sled_fwd"] + 2 + (12 + BAT_L + 0.6) / 2
    add("EL-BAT", "1S LiPo battery + strap", "300 Avionics", 27.0, xbat, ASM, "weigh (rev B: cage split out)")
    add("AV-308", "Battery cage", "300 Avionics", 6.0, xbat, ASM, "rev B item")
    add("AV-312", "Rod spacers (2 fwd + 2 aft)", "300 Avionics",
        2 * tube_g(7.5, 4.4, SLED_FWD_GAP + (X["cpl_aft"] + GASKET_T - AV_BH_T - X["sled_aft"]), PETG_RHO), xav, CALC, "rev B item")
    add("AV-309/310", "Gasket, switch, adhesive allowance", "300 Avionics", 12.0, xav, ASM)

    # --- booster
    add("BO-401", "Booster tube (slotted)", "400 Booster", tube_g(BODY_OD, BODY_ID, BO_L, TUBE_RHO) * 0.995,
        X["band_end"] + BO_L / 2, CALC, "minus fin slots")
    add("BO-402", "Motor mount tube", "400 Booster", tube_g(MMT_OD, MMT_ID, MMT_L, TUBE_RHO),
        (X["mmt_fwd"] + X["mmt_aft"]) / 2, CALC)
    add("BO-404", "Forward centering ring", "400 Booster", disc_g(BODY_ID - FIT_SH, CR_T, PLY_RHO, MMT_OD + FIT_SH),
        X["mmt_fwd"] + CR_T / 2, CALC)
    ring = disc_g(BODY_ID - FIT_SH, CORE_RING_T, ASA_RHO, MMT_OD + FIT_SH) * 0.7
    rail_h = (BODY_ID - FIT_SH) / 2 - (MMT_OD + FIT_SH) / 2
    rails = 8 * CORE_RAIL_T * rail_h * (X["core_aft"] - X["core_fwd"] - 2 * CORE_RING_T) * ASA_RHO / 1000.0
    add("BO-403", "Fin-can core (ASA)", "400 Booster", 2 * ring + rails + 3.0, (X["core_fwd"] + X["core_aft"]) / 2, CALC,
        "rings 70 % infill, rails solid (ASM)")
    add("BO-405", "Aft fin lock ring", "400 Booster", disc_g(BODY_ID - FIT_SH, LOCK_T, PLY_RHO, RET_CLEAR_D),
        X["end"] - LOCK_T / 2, CALC)
    fm, fx = fin_mass(fin["cr"], fin["ct"], fin["s"], fin["xr"])
    add("BO-406", f"Fins x{FIN_N} (3 mm birch ply, finished)", "400 Booster", FIN_N * fm, fx, CALC)
    add("BO-407", "Motor retainer (commercial)", "400 Booster", RET_MASS, X["mmt_aft"], COTS, "placeholder")
    add("BO-408/409", "2 rail buttons + fwd boss + screws", "400 Booster", 10.0, (X["rb_fwd"] + X["rb_aft"]) / 2, ASM)
    add("BO-410", "Aramid anchor leader + lock-ring screws", "400 Booster", 14.0, X["mmt_fwd"] + 40, ASM)
    add("BO-ADH", "Epoxy fillets and bonds (booster)", "400 Booster", 20.0, X["fin_le"] + 20, ASM)
    add("PL-PNT", "Primer + paint, forward airframe", "200 Payload", 10.0, 330, ASM)
    add("BO-PNT", "Primer + paint, booster", "400 Booster", 15.0, X["band_end"] + BO_L / 2, ASM)

    # --- recovery
    xr = X["av_bh_aft_outer"] + 120
    add("RC-501", "Parachute (~0.9 m, ripstop)", "500 Recovery", 55.0, xr, ASM, "weigh purchased chute")
    add("RC-502", "Flame-resistant chute protector", "500 Recovery", 20.0, xr + 60, ASM)
    add("RC-503", "Shock cord 4 m", "500 Recovery", 40.0, xr - 20, ASM)
    add("RC-504/505", "3 quick links + swivel", "500 Recovery", 15.0, xr - 60, ASM)

    # --- motor placeholder
    mm = MOTOR_M0 if motor_m is None else motor_m
    add("MT-601", "Certified motor (EXTERNAL, placeholder mass)", "600 Motor", mm,
        (X["motor_fwd"] + X["motor_aft"]) / 2, COTS, "replace with certification data")

    # rev B: replace estimates with CAD-derived masses/CG where the CAD pipeline has produced them
    default_fin = (fin["cr"], fin["ct"], fin["s"], fin["xr"]) == (FIN_CR, FIN_CT, FIN_S, FIN_XR)
    for it in items:
        ov = CAD_MASS.get(it["id"])
        if ov and (it["id"] != "BO-406" or default_fin):
            it.update(m=ov["m"], x=ov["x"], tag=CALC, note="CAD: " + ov["basis"])
    return items


# CAD-derived mass properties written by cad/build_cad.py (absent -> formula estimates are used)
CAD_MASS_FILE = os.path.join(PROJECT_ROOT, "cad", "exports", "cad_mass_properties.json")


def _load_cad_mass():
    try:
        with open(CAD_MASS_FILE, encoding="utf-8") as fh:
            return json.load(fh).get("analysis_overrides", {})
    except FileNotFoundError:
        return {}


CAD_MASS = _load_cad_mass()


def cg_of(items, exclude=()):
    sel = [i for i in items if i["id"] not in exclude]
    M = sum(i["m"] for i in sel)
    return M, sum(i["m"] * i["x"] for i in sel) / M


# ============================================================================ Barrowman CP
def barrowman(cr=FIN_CR, ct=FIN_CT, s=FIN_S, xr=FIN_XR, n=FIN_N):
    d = BODY_OD
    R = d / 2
    cn_nose = 2.0
    x_nose = 0.466 * NC_L                      # tangent ogive
    lf = math.sqrt(s ** 2 + (xr + ct / 2 - cr / 2) ** 2)
    k_fb = 1 + R / (s + R)
    cn_f = k_fb * (4 * n * (s / d) ** 2) / (1 + math.sqrt(1 + (2 * lf / (cr + ct)) ** 2))
    xb = X["end"] - cr
    x_f = xb + xr / 3 * (cr + 2 * ct) / (cr + ct) + (1 / 6) * ((cr + ct) - cr * ct / (cr + ct))
    cn = cn_nose + cn_f
    xcp = (cn_nose * x_nose + cn_f * x_f) / cn
    return dict(cn_nose=cn_nose, x_nose=x_nose, lf=lf, k_fb=k_fb, cn_f=cn_f, x_f=x_f, cn=cn, xcp=xcp)


# ============================================================================ run analysis
def run():
    R = {}
    items = build_mass_items()
    R["items"] = items
    M0, cg0 = cg_of(items)
    Mb, cgb = cg_of([dict(i, m=(MOTOR_MB if i["id"] == "MT-601" else i["m"])) for i in items])
    Me, cge = cg_of(items, exclude=("MT-601",))
    bw = barrowman()
    d = BODY_OD
    R.update(M0=M0, cg0=cg0, Mb=Mb, cgb=cgb, Me=Me, cge=cge, bw=bw,
             sm0=(bw["xcp"] - cg0) / d, smb=(bw["xcp"] - cgb) / d, sme=(bw["xcp"] - cge) / d,
             L=X["end"], LD=X["end"] / d)

    modules = {}
    for i in items:
        mod = modules.setdefault(i["module"], dict(m=0.0, mx=0.0))
        mod["m"] += i["m"]
        mod["mx"] += i["m"] * i["x"]
    R["modules"] = {k: dict(m=v["m"], x=v["mx"] / v["m"]) for k, v in modules.items()}

    # --- stability sensitivity to motor loaded mass (motor CG held at placeholder station)
    sens = []
    for mm in range(40, 321, 10):
        its = build_mass_items(motor_m=mm)
        M, cg = cg_of(its)
        sens.append(dict(motor_m=mm, M=M, cg=cg, sm=(bw["xcp"] - cg) / d))
    R["sens"] = sens
    x_target = bw["xcp"] - 1.5 * d
    x_ballast = X["sh_end"] - BALLAST_ROD_L / 2
    for row in sens:
        row["ballast"] = max(0.0, row["M"] * (row["cg"] - x_target) / (x_target - x_ballast))
    # motor mass at which margin crosses 1.5 cal
    cross = None
    for a, b in zip(sens, sens[1:]):
        if a["sm"] >= 1.5 > b["sm"]:
            cross = a["motor_m"] + (a["sm"] - 1.5) / (a["sm"] - b["sm"]) * (b["motor_m"] - a["motor_m"])
    R["sm_cross_motor"] = cross

    # --- fin sizing trade study
    trade = []
    for label, f in [("A: 4 fins, span 45", dict(cr=150, ct=60, s=45, xr=55)),
                     ("B: 4 fins, span 52", dict(cr=150, ct=60, s=52, xr=62)),
                     ("C: 4 fins, span 60 (selected)", dict(cr=150, ct=60, s=60, xr=70)),
                     ("D: 4 fins, span 70", dict(cr=150, ct=60, s=70, xr=80)),
                     ("E: 3 fins, span 70", dict(cr=150, ct=60, s=70, xr=80, n=3))]:
        n = f.pop("n", 4)
        b2 = barrowman(n=n, **f)
        its = build_mass_items(fin=f)
        if n == 3:
            for i in its:
                if i["id"] == "BO-406":
                    i["m"] *= 3 / 4
        M, cg = cg_of(its)
        Mb2, cgb2 = cg_of([dict(i, m=(MOTOR_MB if i["id"] == "MT-601" else i["m"])) for i in its])
        area, _ = fin_geom(**f)
        trade.append(dict(label=label, n=n, s=f["s"], area=area, cn_f=b2["cn_f"], xcp=b2["xcp"],
                          sm0=(b2["xcp"] - cg) / d, smb=(b2["xcp"] - cgb2) / d, M=M))
    R["trade"] = trade

    # --- nose geometry
    rho = ogive_rho()
    R["nose"] = dict(rho=rho, tip_half_angle=math.degrees(math.acos((rho - d / 2) / rho)),
                     fineness=NC_L / d, r_split=ogive_r(NC_SPLIT))

    # --- recovery
    md = Mb / 1000.0
    A_req = 2 * md * G0 / (RHO_AIR * CHUTE_CD * V_DESC ** 2)
    D_req = math.sqrt(4 * A_req / math.pi)
    chutes = []
    for dn in (762, 914, 1067, 1219):
        A = math.pi * (dn / 1000) ** 2 / 4
        v = math.sqrt(2 * md * G0 / (RHO_AIR * CHUTE_CD * A))
        chutes.append(dict(D=dn, inch=round(dn / 25.4), v=v, ke=0.5 * md * v * v))
    R["recovery"] = dict(md=md, A_req=A_req, D_req=D_req, chutes=chutes,
                         cord_L=math.ceil(3 * X["end"] / 1000))
    v_sel = [c for c in chutes if c["D"] == int(CHUTE_D)][0]["v"]
    drift = []
    for apo in (100, 200, 300):
        t = apo / v_sel
        drift.append(dict(apogee=apo, t=t, w10=t * 10 / 3.6, w20=t * 20 / 3.6))
    R["recovery"]["drift"] = drift
    R["recovery"]["v_sel"] = v_sel

    # --- structural loads
    loads = {}
    m_upper = sum(i["m"] for i in items if i["module"] in ("100 Nose", "200 Payload", "300 Avionics")) / 1000
    loads["m_upper"] = m_upper
    loads["F_joint"] = m_upper * N_AX * G0
    loads["F_thrust"] = M0 / 1000 * N_AX * G0
    bond_area = math.pi * MMT_OD * (CR_T + 2 * CORE_RING_T)
    loads["bond_area"] = bond_area
    loads["bond_cap"] = bond_area * TAU_BOND
    loads["sf_bond"] = loads["bond_cap"] / loads["F_thrust"]
    A_ch = math.pi * (CHUTE_D / 1000) ** 2 / 4
    shock = []
    for v in (10, 20, 30):
        F = 0.5 * RHO_AIR * v * v * CHUTE_CD * A_ch * SHOCK_K
        shock.append(dict(v=v, F=F, req=2 * F))
    loads["shock"] = shock
    F_rec = shock[-1]["F"]
    loads["F_rec_design"] = F_rec
    loads["rod_cap"] = 2 * M4_AS * A2_70_PROOF
    loads["sf_rod"] = loads["rod_cap"] / F_rec
    # aft AV bulkhead: centre load, supported at rods (span = rod spacing), 12 mm ply, width 40 mm
    Mb_ = F_rec * AV_ROD_SP / 4
    Z = 40 * (2 * AV_BH_T) ** 2 / 6
    loads["bh_sigma"] = Mb_ / Z
    loads["sf_bh"] = PLY_SIG / loads["bh_sigma"]
    # coupler end bearing under rod pull on fwd bulkhead
    loads["bear_area"] = math.pi / 4 * (CPL_OD ** 2 - CPL_ID ** 2)
    # fin side load at V_MAX and ALPHA_GUST
    q = 0.5 * RHO_AIR * V_MAX ** 2
    A_ref = math.pi * (d / 2000) ** 2
    cn_one = bw["cn_f"] / FIN_N * 2   # per fin, conservatively doubled for the fin normal to the flow
    F_fin = cn_one * math.radians(ALPHA_GUST) * q * A_ref
    ycp = FIN_S * (FIN_CR + 2 * FIN_CT) / (3 * (FIN_CR + FIN_CT))
    M_root = F_fin * ycp
    Zf = FIN_CR * FIN_T ** 2 / 6
    loads.update(q=q, F_fin=F_fin, ycp=ycp, M_root=M_root, fin_sigma=M_root / Zf, sf_fin=PLY_SIG / (M_root / Zf))
    # flutter screening (NACA TN 4197 simplified form, as popularised for model rockets)
    area, _ = fin_geom()
    AR = FIN_S ** 2 / area
    lam = FIN_CT / FIN_CR
    tc = FIN_T / FIN_CR
    Pa = 101325.0
    denom = 1.337 * AR ** 3 * Pa * (lam + 1) / (2 * (AR + 2) * tc ** 3)
    a_snd = 340.0
    Vf = a_snd * math.sqrt(PLY_G * 1e9 / denom)
    loads.update(AR=AR, lam=lam, tc=tc, Vf=Vf, sf_flutter=Vf / V_MAX)
    # free-free first bending mode, uniform beam (upper bound: ignores joint compliance)
    I = math.pi / 64 * ((d / 1000) ** 4 - (BODY_ID / 1000) ** 4)
    EI = TUBE_E * 1e9 * I
    mL = (M0 / 1000) / (X["end"] / 1000)
    f1 = 22.37 / (2 * math.pi) * math.sqrt(EI / (mL * (X["end"] / 1000) ** 4))
    loads.update(I=I, EI=EI, f1=f1)
    R["loads"] = loads
    return R


if __name__ == "__main__":
    R = run()
    print(f"L={R['L']:.0f} mm  L/D={R['LD']:.1f}")
    print(f"Liftoff mass {R['M0']:.0f} g  CG {R['cg0']:.0f} mm")
    print(f"Burnout mass {R['Mb']:.0f} g  CG {R['cgb']:.0f} mm")
    print(f"Empty   mass {R['Me']:.0f} g  CG {R['cge']:.0f} mm")
    bw = R["bw"]
    print(f"CP {bw['xcp']:.0f} mm  CNf {bw['cn_f']:.2f}  Xf {bw['x_f']:.0f}")
    print(f"SM liftoff {R['sm0']:.2f}  burnout {R['smb']:.2f}  no motor {R['sme']:.2f}")
    print("cross 1.5 cal at motor mass", R["sm_cross_motor"])
    for m, v in R["modules"].items():
        print(f"  {m:14s} {v['m']:7.1f} g @ {v['x']:.0f}")
    for t in R["trade"]:
        print(t)
    print(R["nose"])
    print({k: v for k, v in R["recovery"].items()})
    print(R["loads"])
    print("payload bay clear", PAYLOAD_BAY_CLEAR, "recovery bay", RECOVERY_BAY_L, "tab", FIN_TAB_L, FIN_TAB_H)
    print(X)
