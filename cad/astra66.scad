// =============================================================================
// ASTRA-66 -- compatibility entry point (rev A interface, rev B geometry)
// The master CAD file is cad/assembly/astra66_assembly.scad; part sources are in cad/parts/.
// This file keeps the rev A `PART=` selector used by tools/openscad_render_check.py.
//   PART = "assembly" | "exploded" | "nose_tip" | "nose_base" | "nose_bulkhead" | "camera_cradle"
//        | "lens_cowl" | "hatch" | "hatch_frame" | "gps_tray" | "sled" | "bulkhead_fwd" | "bulkhead_aft"
//        | "fwd_centering_ring" | "fincan_core" | "lock_ring" | "fin" | "rail_boss" | "fin_jig"
// =============================================================================
include <lib/astra66_core.scad>
use <parts/NC-101_nose_tip.scad>
use <parts/NC-102_nose_base.scad>
use <parts/NC-103_nose_bulkhead.scad>
use <parts/PL-202_gps_tray.scad>
use <parts/PL-203_camera_cradle.scad>
use <parts/PL-204_lens_cowl.scad>
use <parts/PL-205_access_hatch.scad>
use <parts/PL-206_hatch_frame.scad>
use <parts/AV-303_fwd_bulkhead.scad>
use <parts/AV-304_aft_bulkhead.scad>
use <parts/AV-306_electronics_sled.scad>
use <parts/BO-403_fincan_core.scad>
use <parts/BO-404_fwd_centering_ring.scad>
use <parts/BO-405_fin_lock_ring.scad>
use <parts/BO-406_fin.scad>
use <parts/BO-409_rail_button_boss.scad>
use <parts/GS-701_fin_jig.scad>
use <assembly/astra66_assembly.scad>

PART    = "assembly";
EXPLODE = 90;

if (PART == "assembly")                oriented() astra66(0);
else if (PART == "exploded")           oriented() astra66(EXPLODE);
else if (PART == "nose_tip")           NC_101_nose_tip();
else if (PART == "nose_base")          NC_102_nose_base();
else if (PART == "nose_bulkhead")      NC_103_nose_bulkhead();
else if (PART == "camera_cradle")      PL_203_camera_cradle();
else if (PART == "lens_cowl")          PL_204_lens_cowl();
else if (PART == "hatch")              PL_205_access_hatch();
else if (PART == "hatch_frame")        PL_206_hatch_frame();
else if (PART == "gps_tray")           PL_202_gps_tray();
else if (PART == "sled")               AV_306_electronics_sled();
else if (PART == "bulkhead_fwd")       AV_303_fwd_bulkhead();
else if (PART == "bulkhead_aft")       AV_304_aft_bulkhead();
else if (PART == "fwd_centering_ring") BO_404_fwd_centering_ring();
else if (PART == "fincan_core")        BO_403_fincan_core();
else if (PART == "lock_ring")          BO_405_fin_lock_ring();
else if (PART == "fin")                BO_406_fin(0);
else if (PART == "rail_boss")          BO_409_rail_button_boss();
else if (PART == "fin_jig")            GS_701_fin_jig();
