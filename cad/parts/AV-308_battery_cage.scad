// ASTRA-66 CAD rev B -- AV-308 Battery cage
// Open-bottom cage for a BAT_L x BAT_W x BAT_H cell (USER placeholders) under the sled (-Y face).
// End blocks carry 2x M3 x 16 screws up into the AV-306 inserts; the cell is retained by a strap through
// the side-wall slots. PETG, FDM, printed top-plate down.
include <../lib/astra66_core.scad>

CW = BAT_W + 0.6;        // pocket width
CH = BAT_H + 0.4;        // pocket depth
WT = 1.6;                // side wall
TT = 2.0;                // top plate
Y0 = -SLED_T / 2;        // sled bottom face

module AV_308_battery_cage() {
    difference() {
        union() {
            translate([-CW / 2 - WT, Y0 - TT, X_BAT0]) cube([CW + 2 * WT, TT, BAT_CAGE_L]);
            for (s = [-1, 1]) translate([s > 0 ? CW / 2 : -CW / 2 - WT, Y0 - TT - CH, X_BAT0]) cube([WT, CH + EPS, BAT_CAGE_L]);
            for (z = [X_BAT0, X_BAT0 + BAT_CAGE_L - 6]) translate([-CW / 2 - WT, Y0 - TT - CH, z]) cube([CW + 2 * WT, CH + EPS, 6]);
        }
        for (z = [X_BAT0 + 3, X_BAT0 + BAT_CAGE_L - 3]) translate([0, Y0 - TT - CH - 1, z]) rotate([-90, 0, 0]) cylinder(d = CLR_M3, h = CH + TT + 2);
        for (z = [X_BAT0 + 16, X_BAT0 + BAT_CAGE_L - 28]) translate([-CW, Y0 - TT - 6, z]) cube([2 * CW, 4, 12]);
    }
}

AV_308_battery_cage();
