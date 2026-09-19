// ASTRA-66 CAD rev B -- BO-402 Motor mount tube (external propulsion interface I-05)
// MMT_ID, MMT_L and MMT_AFT_EXT are COMMERCIAL SPEC placeholders: take final values from the certified
// motor system's and retainer's current documentation. Nothing here specifies a motor.
include <../lib/astra66_core.scad>

module BO_402_motor_mount_tube() { tube_r(R_MO, R_MI, X_MMT_FWD, X_MMT_AFT); }

BO_402_motor_mount_tube();
