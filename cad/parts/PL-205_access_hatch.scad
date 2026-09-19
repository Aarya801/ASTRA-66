// ASTRA-66 CAD rev B -- PL-205 Access hatch (service feature)
// Curved panel = body-tube wall section, HATCH_GAP smaller than the cut-out all round, 2x M2.5 button-head
// screws into PL-206 ledge inserts at X_HATCH +/- HATCH_SCREW_OFF. PETG, FDM.
include <../lib/astra66_core.scad>

module PL_205_access_hatch() {
    difference() {
        intersection() {
            tube_r(R_OD, R_ID, X_HATCH - HATCH_L, X_HATCH + HATCH_L);
            radial_prism(HATCH_ANG, X_HATCH, HATCH_L - 2 * HATCH_GAP, HATCH_W - 2 * HATCH_GAP, 3 - HATCH_GAP, R_ID - 1, R_OD + 1);
        }
        for (s = [-1, 1]) radial_cyl(CLR_M25, X_HATCH + s * HATCH_SCREW_OFF, HATCH_ANG, R_ID - 1, R_OD + 1);
    }
}

PL_205_access_hatch();
