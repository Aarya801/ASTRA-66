// ASTRA-66 CAD rev B -- AV-301 Avionics coupler
// Forward half bonded into PL-201 (I-02, the "forward coupler" function); aft half is the friction-fit
// separation joint into BO-401 (I-03, the "aft coupler" function). Switch access hole + 4 static ports.
// Commercial coupler tube, cut to length.
include <../lib/astra66_core.scad>

module AV_301_coupler() {
    difference() {
        tube_r(R_CO, R_CI, X_CPL_FWD, X_CPL_AFT);
        radial_cyl(SW_HOLE_D, X_SW, SW_ANG, R_CI - 1, R_CO + 1);
        for (a = STATIC_PORT_ANG) radial_cyl(STATIC_PORT_D, X_SW, a, R_CI - 1, R_CO + 1);
    }
}

AV_301_coupler();
