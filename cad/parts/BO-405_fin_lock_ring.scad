// ASTRA-66 CAD rev B -- BO-405 Aft fin lock ring
// Bore RET_CLEAR_D (COTS retainer body OD + 1) so the ring slides off over the installed retainer;
// 4x M3 x 12 into BO-403 inserts at LOCK_SCREW_R. 6 mm birch ply (heat tolerant). Laser-cut: OUT="2d".
include <../lib/astra66_core.scad>

OUT = "3d";

module BO_405_fin_lock_ring() {
    difference() {
        tube_r(R_SH, RET_CLEAR_D / 2, X_END - LOCK_T, X_END);
        for (a = LOCK_SCREW_ANG) at_angle(a) translate([LOCK_SCREW_R, 0, X_END - LOCK_T - 1]) cylinder(d = CLR_M3, h = LOCK_T + 2);
    }
}

if (OUT == "2d") projection() BO_405_fin_lock_ring(); else BO_405_fin_lock_ring();
