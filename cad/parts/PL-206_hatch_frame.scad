// ASTRA-66 CAD rev B -- PL-206 Hatch doubler frame (internal support)
// FRAME_L x FRAME_W saddle, FRAME_T thick, bonded inside PL-201 around the cut-out. The opening is 12 mm
// shorter than the cut-out axially, leaving 6 mm ledges that carry the hatch and two M2.5 insert bosses.
// PETG, FDM.
include <../lib/astra66_core.scad>

R_FRAME = R_ID - 0.05;                 // bonded outer surface

module PL_206_hatch_frame() {
    difference() {
        union() {
            intersection() {
                tube_r(R_FRAME, R_ID - FRAME_T, X_HATCH - FRAME_L / 2, X_HATCH + FRAME_L / 2);
                radial_prism(HATCH_ANG, X_HATCH, FRAME_L, FRAME_W, 3, R_ID - FRAME_T - 1, R_OD);
            }
            for (s = [-1, 1]) intersection() {
                radial_cyl(6, X_HATCH + s * HATCH_SCREW_OFF, HATCH_ANG, R_ID - 4.5, R_ID);
                translate([0, 0, X_HATCH - FRAME_L]) cylinder(r = R_FRAME, h = 2 * FRAME_L);
            }
        }
        radial_prism(HATCH_ANG, X_HATCH, HATCH_L - 12, HATCH_W, 3, R_ID - 6, R_OD + 1);
        for (s = [-1, 1]) radial_cyl(INS_M25_D, X_HATCH + s * HATCH_SCREW_OFF, HATCH_ANG, R_ID - INS_M25_L - 0.05, R_OD);
    }
}

PL_206_hatch_frame();
