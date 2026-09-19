// =============================================================================
// ASTRA-66 CAD rev B -- MASTER PARAMETRIC ASSEMBLY
// Doc ASTRA-66-CAD-001 Rev B (DRAFT, NOT FLIGHT CERTIFIED)
//
// Parameters: ../astra66_params.scad (generated from analysis.py by build.py) -- body diameter, overall
// length, nose length, walls, fin thickness/span/sweep/chords, coupler, electronics-bay, payload-bay and
// recovery-bay dimensions, rail-button stations/angle, camera and sensor locations. Derived stations:
// ../lib/astra66_core.scad.  Part sources: ../parts/.
//
// MODE = "assembly" | "exploded" | "section" (half-section through the 90/270 deg plane).
// Transparent (%) solids are commercial/purchased ENVELOPES (motor, retainer, rail buttons, eyebolt,
// electronics); their final sizes come from the manufacturers' documentation.
// =============================================================================
include <../lib/astra66_core.scad>
use <../parts/NC-101_nose_tip.scad>
use <../parts/NC-102_nose_base.scad>
use <../parts/NC-103_nose_bulkhead.scad>
use <../parts/PL-201_payload_tube.scad>
use <../parts/PL-202_gps_tray.scad>
use <../parts/PL-203_camera_cradle.scad>
use <../parts/PL-204_lens_cowl.scad>
use <../parts/PL-205_access_hatch.scad>
use <../parts/PL-206_hatch_frame.scad>
use <../parts/AV-301_coupler.scad>
use <../parts/AV-302_switch_band.scad>
use <../parts/AV-303_fwd_bulkhead.scad>
use <../parts/AV-304_aft_bulkhead.scad>
use <../parts/AV-306_electronics_sled.scad>
use <../parts/AV-308_battery_cage.scad>
use <../parts/AV-309_gasket.scad>
use <../parts/AV-312_rod_spacers.scad>
use <../parts/BO-401_booster_tube.scad>
use <../parts/BO-402_motor_mount_tube.scad>
use <../parts/BO-403_fincan_core.scad>
use <../parts/BO-404_fwd_centering_ring.scad>
use <../parts/BO-405_fin_lock_ring.scad>
use <../parts/BO-406_fin.scad>
use <../parts/BO-409_rail_button_boss.scad>
use <../parts/COTS_envelopes.scad>

MODE      = "assembly";
EXPLODE   = 90;       // mm between modules in "exploded"
SHOW_COTS = true;
NOSE_UP   = true;
HORIZONTAL = false;   // true: axis along +X (nose at -X) for wide images

module m100_nose()     { color("WhiteSmoke") { NC_101_nose_tip(); NC_102_nose_base(); } color("DimGray") NC_103_nose_bulkhead(); }
module m200_payload()  { color("Gainsboro", 0.6) PL_201_payload_tube(); color("DimGray") { PL_202_gps_tray(); PL_203_camera_cradle(); PL_206_hatch_frame(); }
                         color("OrangeRed") PL_204_lens_cowl(); color("WhiteSmoke") PL_205_access_hatch(); }
module m300_avionics() { color("Gainsboro", 0.6) { AV_301_coupler(); AV_302_switch_band(); } color("BurlyWood") { AV_303_fwd_bulkhead(); AV_304_aft_bulkhead(); }
                         color("SteelBlue") AV_306_electronics_sled(); color("DimGray") { AV_308_battery_cage(); AV_312_rod_spacers(); } color("Black") AV_309_gasket(); }
module m400_booster()  { color("Gainsboro", 0.6) BO_401_booster_tube(); color("Tan") BO_402_motor_mount_tube(); color("BurlyWood") { BO_404_fwd_centering_ring(); BO_405_fin_lock_ring(); BO_406_fin_set(); }
                         color("DimGray") { BO_403_fincan_core(); BO_409_rail_button_boss(); } }
module m_cots()        { %MT_601_motor_envelope(); %BO_407_retainer_envelope(); %BO_408_rail_buttons(); %AV_311_eyebolt_envelope();
                         color("Silver") { AV_305_rod_hardware(); NC_104_ballast_rod(); } %AV_307_switch_envelope(); %EL_modules(); %EL_battery(); %EL_gps(); %EL_camera(); }

module astra66(e = 0) {
    translate([0, 0, -3 * e]) m100_nose();
    translate([0, 0, -2 * e]) m200_payload();
    translate([0, 0, -e]) m300_avionics();
    m400_booster();
    if (SHOW_COTS && e == 0) m_cots();
}

module oriented() { if (HORIZONTAL) rotate([0, 90, 0]) children(); else if (NOSE_UP) rotate([180, 0, 0]) children(); else children(); }

if (MODE == "exploded") oriented() astra66(EXPLODE);
else if (MODE == "section") oriented() difference() { astra66(0); translate([-200, -200, -400]) cube([200, 400, 2400]); }
else oriented() astra66(0);
