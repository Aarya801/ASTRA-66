// ASTRA-66 CAD rev B -- NC-101 Nose tip section
// Tangent ogive STA 0..NC_SPLIT, wall NC_WALL, solid tip NC_TIP_SOLID, split web + spigot (I-00).
// PETG, FDM. Print standing on the spigot end, tip up (no supports).
include <../lib/astra66_core.scad>

SPIGOT_R = ogive_r(NC_SPLIT) - NC_WALL - FIT_SH / 2;   // spigot outer radius

module NC_101_nose_tip() {
    difference() {
        union() {
            ogive_solid(0, NC_SPLIT);
            translate([0, 0, NC_SPLIT - NC_SPLIT_WEB]) cylinder(r = SPIGOT_R, h = NC_SPLIT_WEB + NC_SPIGOT_L);
        }
        ogive_solid(NC_TIP_SOLID, NC_SPLIT - NC_SPLIT_WEB, NC_WALL);                     // shell cavity
        translate([0, 0, NC_SPLIT - NC_SPLIT_WEB - 1])
            cylinder(r = SPIGOT_R - NC_SPIGOT_WALL, h = NC_SPLIT_WEB + NC_SPIGOT_L + 2);  // spigot bore
    }
}

NC_101_nose_tip();
