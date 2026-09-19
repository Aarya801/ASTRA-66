// ASTRA-66 CAD rev B -- AV-304 Aft bulkhead (removable; recovery attachment I-04a)
// Two 6 mm birch-ply discs laminated. The outer disc seats on the AV-309 face gasket at the coupler aft end;
// 2x M4 rod clearance holes (nylock nuts + washers), centre hole for the M6 forged eyebolt (AV-311, COTS).
// Laser-cut: OUT="2d", SUB="outer"|"inner".
include <../lib/astra66_core.scad>

OUT = "3d";
SUB = "all";

module av304_holes() {
    for (s = [-1, 1]) translate([s * AV_ROD_SP / 2, 0, -1]) cylinder(d = CLR_M4, h = AV_BH_T + 2);
    translate([0, 0, -1]) cylinder(d = CLR_M6, h = AV_BH_T + 2);
}

module AV_304_outer() { translate([0, 0, X_AVB_AFT_OUT]) difference() { cylinder(r = R_CO, h = AV_BH_T); av304_holes(); } }
module AV_304_inner() { translate([0, 0, X_AVB_AFT_OUT - AV_BH_T]) difference() { cylinder(r = R_BH_IN, h = AV_BH_T); av304_holes(); } }
module AV_304_aft_bulkhead() { AV_304_outer(); AV_304_inner(); }

if (OUT == "2d") projection() { if (SUB == "inner") AV_304_inner(); else AV_304_outer(); }
else if (SUB == "outer") AV_304_outer();
else if (SUB == "inner") AV_304_inner();
else AV_304_aft_bulkhead();
