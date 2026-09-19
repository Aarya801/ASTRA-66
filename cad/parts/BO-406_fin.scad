// ASTRA-66 CAD rev B -- BO-406 Fin (qty FIN_N + 1 spare) and fin set
// Trapezoidal fin, root FIN_CR, tip FIN_CT, span FIN_S, LE sweep FIN_XR, thickness FIN_T; slide-in tab
// from X_TAB_FWD to X_TAB_AFT, depth FIN_TAB_H (rev B: clears the COTS retainer, rests on BO-403 floors).
// 3 mm aircraft birch ply. Laser-cut: OUT="2d" gives the flat pattern (root on the X axis, LE at origin).
include <../lib/astra66_core.scad>

OUT = "3d";   // "3d" | "2d"
SUB = "one";  // "one" | "set"

// profile in (radius, station) coordinates
function fin_pts() = [[R_OD, X_FIN_LE], [R_OD + FIN_S, X_FIN_LE + FIN_XR], [R_OD + FIN_S, X_FIN_LE + FIN_XR + FIN_CT],
                      [R_OD, X_END], [R_OD, X_TAB_AFT], [R_OD - FIN_TAB_H, X_TAB_AFT], [R_OD - FIN_TAB_H, X_TAB_FWD],
                      [R_OD, X_TAB_FWD]];

module BO_406_fin_2d_rz() { polygon(fin_pts()); }
module BO_406_fin_flat() { polygon([for (p = fin_pts()) [p[1] - X_FIN_LE, p[0] - R_OD]]); }
module BO_406_fin(a = 0) { at_angle(a) rotate([90, 0, 0]) linear_extrude(height = FIN_T, center = true) BO_406_fin_2d_rz(); }
module BO_406_fin_set() { for (a = FIN_ANGLES) BO_406_fin(a); }

if (OUT == "2d") BO_406_fin_flat();
else if (SUB == "set") BO_406_fin_set();
else BO_406_fin(0);
