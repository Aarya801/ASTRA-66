// ASTRA-66 CAD rev B -- BO-404 Forward centering ring (recovery attachment structure I-04b)
// 6 mm birch ply at the MMT forward end; 6 x 3 notch at KEVLAR_NOTCH_ANG for the bonded aramid leader.
// Laser-cut: OUT="2d".
include <../lib/astra66_core.scad>

OUT = "3d";

module BO_404_fwd_centering_ring() {
    difference() {
        tube_r(R_SH, R_RING_BORE, X_MMT_FWD, X_MMT_FWD + CR_T);
        at_angle(KEVLAR_NOTCH_ANG) translate([R_RING_BORE - 0.5, -3, X_MMT_FWD - 1]) cube([3.5, 6, CR_T + 2]);
    }
}

if (OUT == "2d") projection() BO_404_fwd_centering_ring(); else BO_404_fwd_centering_ring();
