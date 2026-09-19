// ASTRA-66 CAD rev B -- AV-312 Rod spacers (internal supports)
// Clamp the sled axially on AV-305: forward pair AV-303 -> sled, aft pair sled -> AV-304 inner disc.
// Tightening the AV-304 nuts pre-loads the stack. PETG, FDM, printed upright. Qty 2 + 2.
include <../lib/astra66_core.scad>

SUB = "all";  // "all" | "fwd" | "aft"

module AV_312_fwd() { for (s = [-1, 1]) translate([s * AV_ROD_SP / 2, 0, 0]) tube_r(3.75, 2.2, X_CPL_FWD + AV_BH_T, X_SLED_FWD); }
module AV_312_aft() { for (s = [-1, 1]) translate([s * AV_ROD_SP / 2, 0, 0]) tube_r(3.75, 2.2, X_SLED_AFT, X_AVB_AFT_OUT - AV_BH_T); }
module AV_312_rod_spacers() { AV_312_fwd(); AV_312_aft(); }

if (SUB == "fwd") AV_312_fwd(); else if (SUB == "aft") AV_312_aft(); else AV_312_rod_spacers();
