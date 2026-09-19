// ASTRA-66 CAD rev B -- NC-103 Nose bulkhead / ballast mount
// Disc inside the NC-102 shoulder, bolted to the 3 lugs (3x M3 x 10), centre hole for the NC-104 M6 rod.
// PETG, FDM, flat, 60 % gyroid.
include <../lib/astra66_core.scad>

module NC_103_nose_bulkhead() {
    translate([0, 0, X_SH_END - NC_BH_T]) difference() {
        cylinder(r = R_SI - 0.1, h = NC_BH_T);
        translate([0, 0, -1]) cylinder(d = CLR_M6, h = NC_BH_T + 2);
        for (a = NC_LUG_ANG) at_angle(a) translate([R_SI - NC_LUG_T / 2, 0, -1]) cylinder(d = CLR_M3, h = NC_BH_T + 2);
    }
}

NC_103_nose_bulkhead();
