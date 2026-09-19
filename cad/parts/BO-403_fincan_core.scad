// ASTRA-66 CAD rev B -- BO-403 Fin-can core (fin alignment / attachment structure)
// Forward ring = fin stop (no slots); aft ring slotted so tabs slide in from aft; 8 guide rails give the
// FIN_T + FIN_GUIDE_CLR guide; rev B tab floors (r <= R_TAB_FLOOR) carry the tabs radially so fins clear the
// COTS retainer when removed. 4 M3 inserts for BO-405, aft rail-button boss with M4 insert on RB_ANG.
// ASA, FDM (aft end down; ring undersides need support).
include <../lib/astra66_core.scad>

G = (FIN_T + FIN_GUIDE_CLR) / 2;       // half guide width

module BO_403_fincan_core() {
    difference() {
        union() {
            tube_r(R_SH, R_RING_BORE, X_CORE_FWD, X_CORE_FWD + CORE_RING_T);
            tube_r(R_SH, R_RING_BORE, X_CORE_AFT - CORE_RING_T, X_CORE_AFT);
            intersection() {
                union() for (a = FIN_ANGLES) at_angle(a) {
                    for (sd = [-1, 1]) translate([R_RING_BORE - EPS, sd > 0 ? G : -G - CORE_RAIL_T, X_CORE_FWD]) cube([R_SH - R_RING_BORE + EPS, CORE_RAIL_T, X_CORE_AFT - X_CORE_FWD]);
                    translate([R_RING_BORE - EPS, -G - EPS, X_CORE_FWD]) cube([R_TAB_FLOOR - R_RING_BORE + EPS, 2 * G + 2 * EPS, X_CORE_AFT - X_CORE_FWD]);  // tab floor
                }
                translate([0, 0, X_CORE_FWD - 1]) cylinder(r = R_SH, h = X_CORE_AFT - X_CORE_FWD + 2);
            }
            radial_block(RB_ANG, R_SH - 7, R_SH + 1, 8, X_RB_AFT - 15, X_CORE_AFT - CORE_RING_T + EPS, R_SH);
        }
        translate([0, 0, X_CORE_FWD - 1]) cylinder(r = R_RING_BORE, h = X_CORE_AFT - X_CORE_FWD + 2);
        for (a = FIN_ANGLES) at_angle(a) translate([R_TAB_FLOOR, -G, X_CORE_AFT - CORE_RING_T - 1]) cube([R_SH - R_TAB_FLOOR + 1, 2 * G, CORE_RING_T + 2]);
        for (a = LOCK_SCREW_ANG) at_angle(a) translate([LOCK_SCREW_R, 0, X_CORE_AFT - 7]) cylinder(d = INS_M3_D, h = 7 + EPS);
        radial_cyl(INS_M4_D, X_RB_AFT, RB_ANG, R_SH - INS_M4_L - 1, R_SH + 1);
    }
}

BO_403_fincan_core();
