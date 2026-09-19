// ASTRA-66 CAD rev B -- AV-302 Switch band
// Body-tube offcut bonded at the centre of AV-301; holes coaxial with the coupler holes.
include <../lib/astra66_core.scad>

module AV_302_switch_band() {
    difference() {
        tube_r(R_OD, R_ID, X_PL_END, X_BAND_END);
        radial_cyl(SW_HOLE_D, X_SW, SW_ANG, R_ID - 1, R_OD + 1);
        for (a = STATIC_PORT_ANG) radial_cyl(STATIC_PORT_D, X_SW, a, R_ID - 1, R_OD + 1);
    }
}

AV_302_switch_band();
