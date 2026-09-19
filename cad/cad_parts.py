"""ASTRA-66 CAD rev B part registry, design corrections and remaining assumptions.

kind: print (FDM, STL export) | ply (laser-cut plywood, DXF export) | foam (DXF) | tube (cut from
purchased tube stock; manufacturing drawing only).  fill = effective solid fraction of the printed part
(ASSUMPTION, slicer-dependent).  amap = analysis.py mass item that the CAD value replaces.
ang = feature angle shown in the longitudinal section of the part drawing; end_z = station of the end view.
"""
import analysis as A

X = A.X
SW = X["pl_end"] + A.AV_BAND_L / 2

PARTS = [
    dict(id="NC-101", file="NC-101_nose_tip.scad", name="Nose tip section", kind="print", mat="PETG", rho=A.PETG_RHO, fill=1.0, qty=1, pose="rx180", ang=90, end_z=100.0, amap="NC-101", sym="axi"),
    dict(id="NC-102", file="NC-102_nose_base.scad", name="Nose base + shoulder", kind="print", mat="PETG", rho=A.PETG_RHO, fill=1.0, qty=1, pose="id", ang=90, end_z=X["nc_screws"], amap="NC-102", sym="axi3"),
    dict(id="NC-103", file="NC-103_nose_bulkhead.scad", name="Nose bulkhead / ballast mount", kind="print", mat="PETG", rho=A.PETG_RHO, fill=0.6, qty=1, pose="auto", ang=90, end_z=X["sh_end"] - 3, amap="NC-103", sym="axi3"),
    dict(id="PL-201", file="PL-201_payload_tube.scad", name="Payload tube", kind="tube", mat="Kraft/phenolic tube", rho=A.TUBE_RHO, fill=1.0, qty=1, ang=90, end_z=X["hatch"], amap="PL-201", sym=None),
    dict(id="PL-202", file="PL-202_gps_tray.scad", name="GPS / sensor tray", kind="print", mat="PETG", rho=A.PETG_RHO, fill=1.0, qty=1, pose="auto", ang=90, end_z=X["av_bh_fwd_outer"] - 4, amap="PL-202", sym=None),
    dict(id="PL-203", file="PL-203_camera_cradle.scad", name="Camera cradle", kind="print", mat="PETG", rho=A.PETG_RHO, fill=0.9, qty=1, pose="auto", ang=90, end_z=X["cam"], amap="PL-203", sym=None),
    dict(id="PL-204", file="PL-204_lens_cowl.scad", name="Lens cowl", kind="print", mat="ASA", rho=A.ASA_RHO, fill=0.6, qty=1, pose="auto", ang=90, end_z=X["cam"] + 12, amap="PL-204", sym=None),
    dict(id="PL-205", file="PL-205_access_hatch.scad", name="Access hatch", kind="print", mat="PETG", rho=A.PETG_RHO, fill=1.0, qty=1, pose="auto", ang=90, end_z=X["hatch"], amap="PL-205/206", sym=None),
    dict(id="PL-206", file="PL-206_hatch_frame.scad", name="Hatch doubler frame", kind="print", mat="PETG", rho=A.PETG_RHO, fill=1.0, qty=1, pose="auto", ang=90, end_z=X["hatch"] - 17, amap="PL-205/206", sym=None),
    dict(id="AV-301", file="AV-301_coupler.scad", name="Avionics coupler", kind="tube", mat="Kraft/phenolic coupler", rho=A.TUBE_RHO, fill=1.0, qty=1, ang=90, end_z=SW, amap="AV-301", sym=None),
    dict(id="AV-302", file="AV-302_switch_band.scad", name="Switch band", kind="tube", mat="Body-tube offcut", rho=A.TUBE_RHO, fill=1.0, qty=1, ang=90, end_z=SW, amap="AV-302", sym=None),
    dict(id="AV-303", file="AV-303_fwd_bulkhead.scad", name="Forward bulkhead (2 discs)", kind="ply", mat="6 mm birch ply x2", rho=A.PLY_RHO, fill=1.0, qty=1, subs=["outer", "inner"], extra_g=4.0, extra_note="+4.0 g tee-nuts (ASM)", ang=90, end_z=X["cpl_fwd"] + 3, amap="AV-303", sym=None),
    dict(id="AV-304", file="AV-304_aft_bulkhead.scad", name="Aft bulkhead (2 discs)", kind="ply", mat="6 mm birch ply x2", rho=A.PLY_RHO, fill=1.0, qty=1, subs=["outer", "inner"], ang=90, end_z=X["cpl_aft"] - 3, amap="AV-304", sym="axi2"),
    dict(id="AV-306", file="AV-306_electronics_sled.scad", name="Electronics sled", kind="print", mat="PETG", rho=A.PETG_RHO, fill=0.9, qty=1, pose="auto", ang=90, end_z=SW, amap="AV-306", sym=None),
    dict(id="AV-308", file="AV-308_battery_cage.scad", name="Battery cage", kind="print", mat="PETG", rho=A.PETG_RHO, fill=1.0, qty=1, pose="rx-90", ang=90, end_z=X["sled_fwd"] + 30, amap="AV-308", sym=None),
    dict(id="AV-309", file="AV-309_gasket.scad", name="Aft bulkhead face gasket", kind="foam", mat="1.5 mm EVA foam", rho=0.10, fill=1.0, qty=1, ang=90, end_z=X["cpl_aft"] + 0.25, amap=None, sym="axi"),
    dict(id="AV-312", file="AV-312_rod_spacers.scad", name="Rod spacers (2 fwd + 2 aft)", kind="print", mat="PETG", rho=A.PETG_RHO, fill=1.0, qty=1, pose="id", stl_subs=["fwd", "aft"], ang=0, end_z=X["sled_fwd"] - 3, amap="AV-312", sym=None),
    dict(id="BO-401", file="BO-401_booster_tube.scad", name="Booster tube", kind="tube", mat="Kraft/phenolic tube", rho=A.TUBE_RHO, fill=1.0, qty=1, ang=90, end_z=1060.0, amap="BO-401", sym=None),
    dict(id="BO-402", file="BO-402_motor_mount_tube.scad", name="Motor mount tube", kind="tube", mat="29 mm-class MMT", rho=A.TUBE_RHO, fill=1.0, qty=1, ang=90, end_z=1000.0, amap="BO-402", sym="axi"),
    dict(id="BO-403", file="BO-403_fincan_core.scad", name="Fin-can core", kind="print", mat="ASA", rho=A.ASA_RHO, fill=0.85, qty=1, pose="rx180", ang=90, end_z=1060.0, amap="BO-403", sym=None),
    dict(id="BO-404", file="BO-404_fwd_centering_ring.scad", name="Forward centering ring", kind="ply", mat="6 mm birch ply", rho=A.PLY_RHO, fill=1.0, qty=1, ang=45, end_z=X["mmt_fwd"] + 3, amap="BO-404", sym=None),
    dict(id="BO-405", file="BO-405_fin_lock_ring.scad", name="Aft fin lock ring", kind="ply", mat="6 mm birch ply", rho=A.PLY_RHO, fill=1.0, qty=1, ang=45, end_z=X["end"] - 3, amap="BO-405", sym="axi4"),
    dict(id="BO-406", file="BO-406_fin.scad", name="Fin (x4 + 1 spare)", kind="ply", mat="3 mm aircraft birch ply", rho=A.PLY_RHO, fill=1.0, qty=A.FIN_N, finish=1.10, ang=0, end_z=1060.0, amap="BO-406", sym=None),
    dict(id="BO-409", file="BO-409_rail_button_boss.scad", name="Forward rail-button boss", kind="print", mat="PETG", rho=A.PETG_RHO, fill=0.8, qty=1, pose="auto", ang=45, end_z=X["rb_fwd"], amap=None, sym=None),
    dict(id="GS-701", file="GS-701_fin_jig.scad", name="Fin alignment jig (ground support)", kind="print", mat="PETG", rho=A.PETG_RHO, fill=0.3, qty=1, pose="id", ang=0, end_z=X["end"] - 25, amap=None, sym="axi4", flight=False),
]

COTS = [
    dict(id="MT-601", sub="motor", name="Certified motor envelope (EXTERNAL, placeholder length)"),
    dict(id="BO-407", sub="retainer", name="Commercial retainer envelope"),
    dict(id="BO-408", sub="rail_buttons", name="Rail buttons (envelope)"),
    dict(id="AV-311", sub="eyebolt", name="M6 forged eyebolt + nut (envelope)"),
    dict(id="AV-305", sub="rods", name="M4 rods, tee-nuts, washers, nylock nuts"),
    dict(id="NC-104", sub="ballast", name="M6 ballast rod + nuts"),
    dict(id="AV-307", sub="switch", name="Arming switch (USER envelope)"),
    dict(id="EL-MOD", sub="modules", name="MCU / IMU / baro / SD / radio envelopes"),
    dict(id="EL-BAT", sub="battery", name="Battery envelope"),
    dict(id="EL-GPS", sub="gps", name="GPS module envelope"),
    dict(id="EL-CAM", sub="camera", name="Camera envelope"),
]

MODULE_OF = {"NC": "100", "PL": "200", "AV": "300", "BO": "400", "MT": "400", "EL-GPS": "200", "EL-CAM": "200",
             "EL-MOD": "300", "EL-BAT": "300", "NC-104": "100", "GS": "700"}


def module_of(pid):
    return MODULE_OF.get(pid, MODULE_OF.get(pid[:2], "400"))


CORRECTIONS = [
    ("C-01", "Assembly feasibility (fin extraction sweep vs COTS retainer)",
     "Rev A fin tabs reached down to the MMT (tab depth 17.3). With the commercial retainer body (OD = RET_CLEAR_D - 1) epoxied on the MMT, a fin could not slide out aft, so the documented 'replaceable fins' did not work.",
     "Tab root now clears the retainer: FIN_TAB_H = R_OD - max(R_MO, RET_CLEAR_D/2) - FIN_TAB_CLR = 12.8 mm (depends on the real retainer OD). BO-403 gains tab floors that carry the tabs radially.",
     "analysis.py FIN_TAB_H, BO-406/BO-403 masses, OpenRocket tab height, sheets A-004/A-005, BOM"),
    ("C-02", "Interface check NC-102 / NC-103",
     "Rev A lugs occupied STA 312-324, the same space as the bulkhead (318-324), and the rev A bulkhead disc (r 24.95) did not reach the lug screws (r 27.75).",
     "Lugs moved to STA 306-318 (ending at the bulkhead face) with 45 deg chamfers; full-diameter NC-103 (r 30.15); screws on the lug centre radius 27.25.",
     "NC-102, NC-103, sheet A-006"),
    ("C-03", "Printability / geometry validity NC-101",
     "Rev A spigot floated inside the tip cavity near the split and the split face was an unsupported ring.",
     "2 mm split web (NC_SPLIT_WEB); spigot grows from it; NC-102 gets a socket collar giving the documented I-00 slip fit (FIT_SOCKET 0.2). Print poses fixed.",
     "NC-101, NC-102"),
    ("C-04", "Fastener accessibility / hatch",
     "Rev A hatch screws sat at +/-30 deg, outside a 25 mm-wide hatch; a 1 mm panel cannot take a countersunk head.",
     "Screws on the frame's 6 mm axial ledges at X_HATCH +/- 17; frame opening 28 x 25; M2.5 button-head screws.",
     "PL-201, PL-205, PL-206, fastener list"),
    ("C-05", "Symmetry / drawing consistency (static ports)",
     "Rev A SCAD listed one static-port angle twice, and sheets A-003/A-007 drew a port at 270 deg.",
     "Four ports at 45/135/225/315 deg through AV-301 and AV-302 (STATIC_PORT_D); drawings updated.",
     "AV-301, AV-302, sheets A-003/A-007"),
    ("C-06", "Interface check PL-202 / AV-303",
     "Rev A tray-foot holes (x +/-5, y 0) did not match the bulkhead holes (x +/-10, y -14), and a 20 mm foot would have clashed with the tee-nut flanges at x +/-20.",
     "Tray plate stops 8 mm ahead of AV-303; 22 x 26 x 8 foot with M3 inserts at (+/-7, -14); matching AV-303 holes; M3 x 16 from inside the bay.",
     "PL-202, AV-303, sheet A-007, fastener list"),
    ("C-07", "Recovery interface / sealing",
     "The rev A gasket (a disc ahead of the inner bulkhead) sealed nothing.",
     "AV-309 is now a face gasket on the coupler aft end face; the AV-304 stack and eyebolt move aft by GASKET_T = 0.5 mm; recovery bay 274.0 -> 273.5 mm.",
     "analysis.py stations, AV-304, AV-309, sheets A-003/A-007"),
    ("C-08", "Electronics mounting (axial location)",
     "The rev A sled was free to slide 18 mm on the rods.",
     "AV-312 spacers (7 mm fwd, 11.5 mm aft) clamp the sled when the AV-304 nuts are tightened.",
     "New part AV-312 and mass item"),
    ("C-09", "Electronics mounting (battery)",
     "The rev A battery cage had no geometry or fastening.",
     "AV-308 open-bottom cage, 2x M3 x 16 into sled inserts; battery width limited to 28.8 mm by the rod sleeves.",
     "AV-306, AV-308, mass item split"),
    ("C-10", "Interference (camera lens vs tube wall)",
     "With the 15 deg aft tilt, the lens-barrel rim would reach the tube bore.",
     "Lens face set back by CAM_SETBACK = L cos(t) + r sin(t) + 0.5.",
     "lib/astra66_core.scad cam_frame"),
    ("C-11", "Manufacturability (fin slots)",
     "Rev A slots ran the full 150 mm root chord, leaving a 10 mm open slot ahead of each tab.",
     "Slots start at the tab front (140 mm, open aft); the fin root ahead of the tab bears on the tube surface.",
     "BO-401, sheet A-004, BOM"),
    ("C-12", "Mass consistency (ballast rod)",
     "The analysis used an 80 mm rod; the BOM cut length is 86 mm (through NC-103).",
     "Analysis uses BALLAST_ROD_L + NC_BH_T = 86 mm.",
     "analysis.py NC-104"),
    ("C-14", "Interference check (automated): PL-201 x EL-CAM, 31 mm^3",
     "The rev A camera placeholder (29 x 16 x 45 mm) tilted 15 deg aft pushed its body corners through the tube wall. No camera of that size fits beside the GPS tray at that tilt.",
     "cam_frame() now seats the lens face at CAM_R0 = min(barrel-rim limit, body-corner limit), so any entered camera stays inside the bore. The placeholder was reduced to 26 x 14 x 40 mm (still USER); the tray and wall clearance is re-checked on every run.",
     "lib/astra66_core.scad, analysis.py CAM_*, PL-203, PL-204"),
    ("C-15", "Printability check (automated): sled and tray poses",
     "The sled's rod sleeves stand proud of both faces, so no flat pose exists (7 246 mm^2 of support). The tray foot also protrudes on both sides of the plate.",
     "The pipeline now selects the minimum-support pose for both. A 45 deg chamfer under the switch tower was tried, but the interference check showed it entering the MCU envelope (391 mm^3), so it was reverted; the tower underside is supported instead.",
     "AV-306, cad_parts.py poses"),
    ("C-16", "Measurement defect in the validation script",
     "Fin tab depth was measured as the true radius to the tab corner (includes the 1.5 mm half-thickness), giving a false 0.056 mm FAIL. The inner-bulkhead radius probe also found no vertices.",
     "Tab depth is now measured along the fin plane and the bulkhead probe includes its face vertices. Geometry unchanged.",
     "cad/build_cad.py"),
    ("C-13", "Mass properties",
     "Rev A masses of structural parts were hand estimates.",
     "Replaced by CAD volume x density x fill factor (cad/exports/cad_mass_properties.json); see the mass table.",
     "analysis.py mass budget, stability, HTML package"),
]

PRINT_NOTES = {
    "NC-101": "Flagged area is the 1.35 mm split-web ledge; bridges without support.",
    "NC-102": "Flagged area is the 1.55 mm base ledge inside the shoulder and 45 deg chamfers; no support needed in practice.",
    "PL-202": "Plate cantilevers from the foot; use a brim. Residual area is the boss undersides.",
    "PL-203": "Pocket roof over the camera; enable supports inside the pocket.",
    "PL-204": "Small window-bore overhang; support optional.",
    "PL-205": "Thin curved panel on its edge; a 0.25 mm nozzle is recommended (1.0 mm wall).",
    "PL-206": "Insert-boss undersides; support optional.",
    "AV-306": "Printed in the min-support pose; support the switch-tower underside (16 x 20 mm), insert-boss undersides and zip-slot roofs.",
    "AV-308": "Strap-slot roofs (12 mm bridges).",
    "BO-403": "Fin-stop ring and rail boss undersides bridge between the guide rails; use tree supports.",
    "BO-409": "Saddle curvature; print saddle-up with a brim.",
}

REMAINING_ASSUMPTIONS = [
    "Motor envelope (MOTOR_L, masses), MMT_ID, MMT_L, MMT_AFT_EXT, RET_CLEAR_D and RET_ENV_L are placeholders. Replace them with the certified motor's and retainer's published data; FIN_TAB_H follows RET_CLEAR_D automatically.",
    "Camera (CAM_*), battery (BAT_*), switch tower height (SW_TOWER_H) and all electronics envelopes are USER placeholders. Measure the purchased parts, then re-run the pipeline.",
    "Heat-set insert holes, tee-nut barrel and flange, and rail-button, eyebolt and retainer envelopes are ASSUMPTIONS. Confirm them against the purchased hardware before printing.",
    "Tube OD/ID, coupler OD/ID and MMT OD are nominal. Measure the stock and update analysis.py.",
    "Material densities and print fill factors are typical values. Weigh printed parts and override the masses in OpenRocket.",
    "OpenSCAD approximates circles with FN = 96 facets (chord error <= 0.02 mm at r = 33); fits in the model are nominal.",
    "Interference is judged on nominal geometry; any overlap under 1 mm^3 is treated as coincident contact.",
    "Printability uses the 45 deg overhang rule on the chosen pose. Confirm in your slicer (bridging, supports, first-layer area).",
    "Structural adequacy of printed parts is covered by the hand calculations in the package, not FEA. Coupon-test printed inserts and bonds.",
    "Adhesive, paint and wiring masses remain allowances (ASSUMPTION items in the mass budget).",
]
