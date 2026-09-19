// ASTRA-66 CAD rev B -- AV-306 Electronics sled
// SLED_W x SLED_T x SLED_L plate in the XZ plane, 2 rod sleeves (7.5 / 4.4) riding on AV-305.
// +Y face: 10 M2.5 insert bosses (x = +/-12.5, 25 mm pitch) and the switch tower (M2.5 insert on top,
// height SW_TOWER_H: USER). 2 M3 inserts pressed from the -Y face for the AV-308 battery cage screws.
// Zip-tie slots for harness strain relief. PETG, FDM, printed flat (+Y face up).
include <../lib/astra66_core.scad>

GRID_Z  = [15, 40, 65, 90, 115];
CAGE_Z  = [X_BAT0 + 3, X_BAT0 + BAT_CAGE_L - 3];

module AV_306_electronics_sled() {
    difference() {
        union() {
            translate([-SLED_W / 2, -SLED_T / 2, X_SLED_FWD]) cube([SLED_W, SLED_T, SLED_L]);
            for (s = [-1, 1]) translate([s * AV_ROD_SP / 2, 0, X_SLED_FWD]) cylinder(d = 7.5, h = SLED_L);
            for (x = [-12.5, 12.5], z = GRID_Z) translate([x, SLED_T / 2 - EPS, X_SLED_FWD + z]) rotate([-90, 0, 0]) cylinder(d = 6.5, h = 3);
            translate([-8, SLED_T / 2 - EPS, X_SW - 6]) cube([16, SW_TOWER_H, 12]);   // switch tower (no chamfer: it would enter the MCU zone)
            for (z = CAGE_Z) translate([0, SLED_T / 2 - EPS, z]) rotate([-90, 0, 0]) cylinder(d = 7, h = 3);
        }
        for (s = [-1, 1]) translate([s * AV_ROD_SP / 2, 0, X_SLED_FWD - 1]) cylinder(d = 4.4, h = SLED_L + 2);
        for (x = [-12.5, 12.5], z = GRID_Z) translate([x, SLED_T / 2 + 3 + EPS, X_SLED_FWD + z]) rotate([90, 0, 0]) cylinder(d = INS_M25_D, h = INS_M25_L);
        translate([0, SLED_T / 2 + SW_TOWER_H + EPS, X_SW]) rotate([90, 0, 0]) cylinder(d = INS_M25_D, h = INS_M25_L);
        for (z = CAGE_Z) translate([0, -SLED_T / 2 - EPS, z]) rotate([-90, 0, 0]) cylinder(d = INS_M3_D, h = INS_M3_L + EPS);
        for (z = [X_SLED_FWD + 28, X_SLED_FWD + 103], s = [-1, 1]) translate([s * 8 - 2, -5, z]) cube([4, 10, 2.5]);
    }
}

AV_306_electronics_sled();
