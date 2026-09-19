// ASTRA-66 CAD rev B -- AV-303 Forward bulkhead (bonded)
// Two 6 mm birch-ply discs laminated: outer disc (CPL_OD) bears on the coupler forward end face, inner disc
// (CPL_ID - 0.2) sits inside the coupler. M4 tee-nuts (flange on the forward face) anchor the AV-305 rods,
// harness hole + grommet, 2 tray-screw holes. Laser-cut: export each disc with OUT="2d", SUB="outer"|"inner".
include <../lib/astra66_core.scad>

OUT = "3d";   // "3d" | "2d"
SUB = "all";  // "all" | "outer" | "inner"

module av303_holes() {
    for (s = [-1, 1]) translate([s * AV_ROD_SP / 2, 0, -1]) cylinder(d = TNUT_BARREL_D, h = AV_BH_T + 2);
    translate([0, HARNESS_Y, -1]) cylinder(d = HARNESS_D, h = AV_BH_T + 2);
    for (s = [-1, 1]) translate([s * TRAY_HOLE_X, TRAY_HOLE_Y, -1]) cylinder(d = CLR_M3, h = AV_BH_T + 2);
}

module AV_303_outer() { translate([0, 0, X_AVB_FWD_OUT]) difference() { cylinder(r = R_CO, h = AV_BH_T); av303_holes(); } }
module AV_303_inner() { translate([0, 0, X_CPL_FWD]) difference() { cylinder(r = R_BH_IN, h = AV_BH_T); av303_holes(); } }
module AV_303_fwd_bulkhead() { AV_303_outer(); AV_303_inner(); }

if (OUT == "2d") projection() { if (SUB == "inner") AV_303_inner(); else AV_303_outer(); }
else if (SUB == "outer") AV_303_outer();
else if (SUB == "inner") AV_303_inner();
else AV_303_fwd_bulkhead();
