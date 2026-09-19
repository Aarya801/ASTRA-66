// ASTRA-66 CAD rev B -- PL-204 Lens cowl
// Teardrop fairing (about 44 x 20 x 8 mm) over the lens hole, saddle = body OD, window bore along the
// tilted lens axis. ASA or PETG, FDM. Bonded to PL-201 and faired with filler.
include <../lib/astra66_core.scad>

module PL_204_lens_cowl() {
    difference() {
        at_angle(CAM_ANG) hull() {
            translate([R_OD - 2, 0, X_CAM - 15]) sphere(r = 3);
            translate([R_OD - 2, -10, X_CAM + 20]) cube([10, 20, 6]);
        }
        translate([0, 0, X_CAM - 40]) cylinder(r = R_OD, h = 90);
        cam_frame() translate([0, 0, CAM_LENS_L - 3]) cylinder(d = CAM_LENS_HOLE, h = 30);
    }
}

PL_204_lens_cowl();
