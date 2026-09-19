// ASTRA-66 CAD rev B -- GS-701 Fin alignment jig (ground support; not flight hardware)
// Collar over the tail with FIN_N slots (FIN_T + 0.3) at the fin angles: holds 90 deg spacing and zero
// cant while BO-403 cures. PETG, FDM.
include <../lib/astra66_core.scad>

module GS_701_fin_jig() {
    translate([0, 0, X_END - 40]) difference() {
        cylinder(d = BODY_OD + 16, h = 30);
        translate([0, 0, -1]) cylinder(d = BODY_OD + 0.4, h = 32);
        for (a = FIN_ANGLES) at_angle(a) translate([0, -(FIN_T + 0.3) / 2, -1]) cube([60, FIN_T + 0.3, 32]);
    }
}

GS_701_fin_jig();
