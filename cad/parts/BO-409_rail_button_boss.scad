// ASTRA-66 CAD rev B -- BO-409 Forward rail-button boss (rail-button mounting structure)
// 20 wide x 16 long x 8 deep saddle bonded to the booster wall against the BO-404 forward face, on RB_ANG;
// M4 heat-set insert installed from the saddle face before bonding. PETG, FDM.
include <../lib/astra66_core.scad>

module BO_409_rail_button_boss() {
    difference() {
        radial_block(RB_ANG, R_ID - 8, R_ID + 1, 10, X_MMT_FWD - 16, X_MMT_FWD, R_ID - 0.1);
        radial_cyl(INS_M4_D, X_RB_FWD, RB_ANG, R_ID - 0.1 - INS_M4_L - 1, R_ID + 1);
    }
}

BO_409_rail_button_boss();
