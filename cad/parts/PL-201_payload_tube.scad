// ASTRA-66 CAD rev B -- PL-201 Payload tube (payload bay)
// Cut from 66 mm-class body tube. Holes: 3x nose screws (I-01), camera lens hole, R3 hatch cut-out.
include <../lib/astra66_core.scad>

module PL_201_payload_tube() {
    difference() {
        tube_r(R_OD, R_ID, NC_L, X_PL_END);
        for (a = NC_SCREW_ANG) radial_cyl(CLR_M3, X_NC_SCREW, a, R_ID - 1, R_OD + 1);
        radial_cyl(CAM_LENS_HOLE, X_CAM, CAM_ANG, R_ID - 1, R_OD + 1);
        radial_prism(HATCH_ANG, X_HATCH, HATCH_L, HATCH_W, 3, R_ID - 1, R_OD + 1);
    }
}

PL_201_payload_tube();
