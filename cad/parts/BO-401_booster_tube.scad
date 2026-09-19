// ASTRA-66 CAD rev B -- BO-401 Booster tube (recovery bay + fin can shell)
// 4 fin slots (FIN_T + FIN_SLOT_CLR) from the tab front to the tail, open aft (rev B: slot starts at
// X_TAB_FWD, so the fin root ahead of the tab sits on the tube surface). 2 rail-button holes on the RB_ANG line.
include <../lib/astra66_core.scad>

module BO_401_booster_tube() {
    difference() {
        tube_r(R_OD, R_ID, X_BAND_END, X_END);
        for (a = FIN_ANGLES) at_angle(a) translate([R_ID - 1, -(FIN_T + FIN_SLOT_CLR) / 2, X_TAB_FWD]) cube([R_OD - R_ID + 2, FIN_T + FIN_SLOT_CLR, X_END - X_TAB_FWD + 1]);
        for (z = [X_RB_FWD, X_RB_AFT]) radial_cyl(CLR_M4, z, RB_ANG, R_ID - 1, R_OD + 1);
    }
}

BO_401_booster_tube();
