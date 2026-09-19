// ASTRA-66 CAD rev B -- Commercial / purchased components (ENVELOPES, not designs)
// These solids reserve space and are used for interference and access checks only. Every size marked
// COMMERCIAL SPEC or USER in the parameter file must be replaced with the real part's documentation.
// Propulsion is represented only by an inert envelope; nothing here specifies a motor.
include <../lib/astra66_core.scad>

SUB = "all";

// -------- MT-601 certified motor: envelope inside the MMT (MOTOR_L placeholder)
module MT_601_motor_envelope() { translate([0, 0, X_MOTOR_FWD]) cylinder(d = MMT_ID - 0.6, h = MOTOR_L); }
// -------- BO-407 commercial retainer: body around the MMT extension (OD = RET_CLEAR_D - 1)
module BO_407_retainer_envelope() { tube_r(RET_CLEAR_D / 2 - 0.5, R_MO, X_END, X_END + RET_ENV_L); }
// -------- BO-408 rail buttons (1010 class assumed; size placeholder)
module BO_408_rail_buttons() { for (z = [X_RB_FWD, X_RB_AFT]) radial_cyl(RB_ENV_D, z, RB_ANG, R_OD, R_OD + RB_ENV_H); }
// -------- AV-311 forged M6 eyebolt: eye aft of AV-304, nut + fender washer (dia 18 assumed) inside
module AV_311_eyebolt_envelope() {
    translate([0, 0, X_AVB_AFT_END]) cylinder(d = EYE_ENV_D, h = EYE_ENV_L);
    translate([0, 0, X_AVB_AFT_OUT - AV_BH_T - 7.6]) cylinder(d = 18, h = 7.6);
    translate([0, 0, X_AVB_AFT_OUT - AV_BH_T - 1]) cylinder(d = 6, h = 2 * AV_BH_T + 2);
}
// -------- AV-305 M4 rods + tee-nuts + washers + nylock nuts
module AV_305_rod_hardware() {
    for (s = [-1, 1]) translate([s * AV_ROD_SP / 2, 0, 0]) {
        translate([0, 0, X_AVB_FWD_OUT]) cylinder(d = 4, h = ROD_L);
        translate([0, 0, X_AVB_FWD_OUT - TNUT_FLANGE_T]) cylinder(d = TNUT_FLANGE_D, h = TNUT_FLANGE_T);
        translate([0, 0, X_AVB_AFT_END]) cylinder(d = 9, h = WASHER_M4_T);
        translate([0, 0, X_AVB_AFT_END + WASHER_M4_T]) cylinder(d = 8, h = NUT_M4_H, $fn = 6);
    }
}
// -------- NC-104 ballast rod (M6 x (BALLAST_ROD_L + NC_BH_T)) + nylock nuts
module NC_104_ballast_rod() {
    translate([0, 0, X_SH_END - BALLAST_ROD_L]) cylinder(d = 6, h = BALLAST_ROD_L + NC_BH_T);
    translate([0, 0, X_SH_END]) cylinder(d = 11, h = 5, $fn = 6);
    translate([0, 0, X_SH_END - NC_BH_T - 5]) cylinder(d = 11, h = 5, $fn = 6);
}
// -------- AV-307 arming switch (USER size) on the tower, actuator 1 mm below the coupler ID
module AV_307_switch_envelope() {
    y0 = SLED_T / 2 + SW_TOWER_H;
    translate([-6, y0, X_SW - 6]) cube([12, R_CI - 1 - y0, 12]);
}
// -------- electronics module envelopes (USER placeholders, layout check only)
module EL_modules() {
    ys = SLED_T / 2 + 3 + 5;                                        // top of bosses + 5 mm standoffs
    translate([-10.5, ys, X_SLED_FWD + 11]) cube([21, 8.5, 50]);    // MCU
    translate([-24, ys, X_SW - 7]) cube([14, 4, 14]);               // IMU (beside the switch tower)
    translate([10, ys, X_SW - 6.5]) cube([13, 4, 13]);              // barometer
    translate([-10, ys, X_SLED_FWD + 83]) cube([20, 4.5, 26]);      // microSD
    translate([-10, ys, X_SLED_FWD + 111]) cube([20, 7, 28]);       // LoRa radio
}
module EL_battery() { translate([-BAT_W / 2, -SLED_T / 2 - 2 - 0.2 - BAT_H, X_BAT0 + 6.3]) cube([BAT_W, BAT_H, BAT_L]); }
module EL_gps() { translate([-12.5, TRAY_T / 2 + 2.5 + 5, X_TRAY_FWD + 12]) cube([25, 8, 35]); }
module EL_camera() {
    cam_frame() {
        translate([-CAM_LEN / 2, -CAM_W / 2, -CAM_H]) cube([CAM_LEN, CAM_W, CAM_H]);
        cylinder(d = CAM_LENS_HOLE - 1, h = CAM_LENS_L);
    }
}

module COTS_all() {
    MT_601_motor_envelope(); BO_407_retainer_envelope(); BO_408_rail_buttons(); AV_311_eyebolt_envelope();
    AV_305_rod_hardware(); NC_104_ballast_rod(); AV_307_switch_envelope(); EL_modules(); EL_battery(); EL_gps(); EL_camera();
}

if (SUB == "motor") MT_601_motor_envelope();
else if (SUB == "retainer") BO_407_retainer_envelope();
else if (SUB == "rail_buttons") BO_408_rail_buttons();
else if (SUB == "eyebolt") AV_311_eyebolt_envelope();
else if (SUB == "rods") AV_305_rod_hardware();
else if (SUB == "ballast") NC_104_ballast_rod();
else if (SUB == "switch") AV_307_switch_envelope();
else if (SUB == "modules") EL_modules();
else if (SUB == "battery") EL_battery();
else if (SUB == "gps") EL_gps();
else if (SUB == "camera") EL_camera();
else COTS_all();
