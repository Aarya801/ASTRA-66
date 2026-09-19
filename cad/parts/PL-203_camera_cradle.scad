// ASTRA-66 CAD rev B -- PL-203 Camera cradle (camera mount)
// Holds a camera of CAM_W x CAM_H x CAM_LEN (USER placeholders) with its lens axis tilted CAM_TILT aft,
// concentric with the PL-201 lens hole. Saddle bonded to the tube wall; camera drops in from the axis side
// and is retained by a zip tie through the two end notches.
// PETG, FDM.
include <../lib/astra66_core.scad>

module PL_203_camera_cradle() {
    difference() {
        intersection() {
            cam_frame() translate([-CAM_LEN / 2 - 2, -CAM_W / 2 - 2, -CAM_H / 2]) cube([CAM_LEN + 4, CAM_W + 4, CAM_H / 2 + CAM_LENS_L + 10]);
            translate([0, 0, X_CAM - 60]) cylinder(r = R_ID - 0.1, h = 120);
        }
        cam_frame() {
            translate([-CAM_LEN / 2 - 0.15, -CAM_W / 2 - 0.15, -CAM_H - 1]) cube([CAM_LEN + 0.3, CAM_W + 0.3, CAM_H + 1]);  // body pocket
            translate([0, 0, -1]) cylinder(d = CAM_LENS_HOLE, h = 30);                                                   // lens bore
            for (s = [-1, 1]) translate([s * (CAM_LEN / 2 - 6) - 2, -CAM_W / 2 - 3, -CAM_H / 2 - 1]) cube([4, CAM_W + 6, 3]); // tie notches
        }
    }
}

PL_203_camera_cradle();
