// ASTRA-66 CAD rev B -- NC-102 Nose base + shoulder (forward coupling, interface I-01)
// Ogive STA NC_SPLIT..NC_L, spigot socket (I-00), shoulder dia (BODY_ID - FIT_SH) x NC_SH_L,
// 3 radial M3 insert bosses at X_NC_SCREW, 3 chamfered lugs carrying NC-103.
// PETG, FDM. Print split face down (socket on the bed), chamfers make lugs/bosses support-free.
include <../lib/astra66_core.scad>

SPIGOT_R = ogive_r(NC_SPLIT) - NC_WALL - FIT_SH / 2;
SOCKET_R = SPIGOT_R + FIT_SOCKET / 2;
LUG_Z1   = X_SH_END - NC_BH_T;              // lugs end at the NC-103 forward face
LUG_Z0   = LUG_Z1 - NC_LUG_L;
LUG_R    = R_SI - NC_LUG_T / 2;             // lug insert pitch radius

module nc102_boss(a) {                       // radial M3 insert boss, 45 deg chamfer underneath
    intersection() {
        hull() {
            at_angle(a) translate([R_SI - NC_BOSS_T, -5, X_NC_SCREW - 5]) cube([NC_BOSS_T + 0.5, 10, 10]);
            at_angle(a) translate([R_SI - 0.5, -5, X_NC_SCREW - 5 - NC_BOSS_T]) cube([1, 10, NC_BOSS_T]);
        }
        cylinder(r = R_SI + 0.5, h = X_SH_END);
    }
}

module nc102_lug(a) {                        // axial M3 insert lug, 45 deg chamfer underneath
    intersection() {
        hull() {
            at_angle(a) translate([R_SI - NC_LUG_T, -6, LUG_Z0]) cube([NC_LUG_T + 0.5, 12, NC_LUG_L]);
            at_angle(a) translate([R_SI - 0.5, -6, LUG_Z0 - NC_LUG_T]) cube([1, 12, NC_LUG_T]);
        }
        cylinder(r = R_SI + 0.5, h = X_SH_END);
    }
}

module NC_102_nose_base() {
    difference() {
        union() {
            difference() {
                union() {
                    ogive_solid(NC_SPLIT, NC_L);
                    translate([0, 0, NC_L - EPS]) cylinder(r = R_SH, h = NC_SH_L + EPS);
                }
                ogive_solid(NC_SPLIT - EPS, NC_L - NC_BASE_RING, NC_WALL);
                translate([0, 0, NC_L - NC_BASE_RING - EPS]) cylinder(r = R_SI, h = NC_SH_L + NC_BASE_RING + 1);
            }
            intersection() {                                       // spigot socket collar (I-00)
                tube_r(R_SI, SOCKET_R, NC_SPLIT, NC_SPLIT + NC_SPIGOT_L);
                ogive_solid(NC_SPLIT, NC_SPLIT + NC_SPIGOT_L);
            }
            for (a = NC_SCREW_ANG) nc102_boss(a);
            for (a = NC_LUG_ANG) nc102_lug(a);
        }
        for (a = NC_SCREW_ANG) radial_cyl(INS_M3_D, X_NC_SCREW, a, R_SI - NC_BOSS_T - 1, R_SH + 1);
        for (a = NC_LUG_ANG) at_angle(a) translate([LUG_R, 0, LUG_Z1 - INS_M3_L - 1]) cylinder(d = INS_M3_D, h = INS_M3_L + 1 + EPS);
    }
}

NC_102_nose_base();
