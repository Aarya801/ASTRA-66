// ASTRA-66 CAD rev B -- PL-202 GPS / sensor tray (sensor mounting provision)
// Plate in the sled plane (XZ), foot bolted to AV-303 forward face by 2x M3 x 16 from inside the
// avionics bay into heat-set inserts in the foot. Six M2.5 insert bosses (2 x 3 grid, 25 mm pitch).
// Foot is 22 x 26 so it clears the AV-303 tee-nut flanges at x = +/-AV_ROD_SP/2.
// PETG, FDM.
include <../lib/astra66_core.scad>

FOOT_Z0 = X_AVB_FWD_OUT - TRAY_FOOT_T;

module PL_202_gps_tray() {
    difference() {
        union() {
            translate([-TRAY_W / 2, -TRAY_T / 2, X_TRAY_FWD]) cube([TRAY_W, TRAY_T, FOOT_Z0 - X_TRAY_FWD + EPS]);
            translate([-11, -20, FOOT_Z0]) cube([22, 26, TRAY_FOOT_T]);
            for (x = [-10, 10], z = [17, 42, 67])
                translate([x, TRAY_T / 2 - EPS, X_TRAY_FWD + z]) rotate([-90, 0, 0]) cylinder(d = 6, h = 2.5);
        }
        for (s = [-1, 1]) translate([s * TRAY_HOLE_X, TRAY_HOLE_Y, X_AVB_FWD_OUT - INS_M3_L - 1]) cylinder(d = INS_M3_D, h = INS_M3_L + 1 + EPS);
        for (x = [-10, 10], z = [17, 42, 67])
            translate([x, TRAY_T / 2 + 2.5 + EPS, X_TRAY_FWD + z]) rotate([90, 0, 0]) cylinder(d = INS_M25_D, h = INS_M25_L);
    }
}

PL_202_gps_tray();
