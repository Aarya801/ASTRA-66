// =============================================================================
// ASTRA-66 CAD rev B -- core library
// Parameters (generated from analysis.py by build.py), derived stations and helpers.
// Every part file includes this; stations mirror analysis.py X[] exactly.
//
// Frame: rocket axis = +Z, STA 0 = nose tip, stations increase aft.
// Angles: measured about +Z from +X toward +Y.  90 deg = switch / hatch side,
// 270 deg = camera side, 45 deg = rail-button line, fins at 0/90/180/270 deg.
// =============================================================================
include <../astra66_params.scad>

$fn = FN;
EPS = 0.01;
CAD_REV = "B";

// ----------------------------------------------------------------- radii
R_OD    = BODY_OD / 2;                 // body tube outer
R_ID    = BODY_ID / 2;                 // body tube inner
R_SH    = (BODY_ID - FIT_SH) / 2;      // printed shoulder / ring OD radius
R_SI    = R_SH - NC_SH_WALL;           // nose shoulder inner radius
R_CO    = CPL_OD / 2;                  // coupler outer
R_CI    = CPL_ID / 2;                  // coupler inner
R_BH_IN = (CPL_ID - 0.2) / 2;          // inner bulkhead disc (fits in coupler)
R_MO    = MMT_OD / 2;
R_MI    = MMT_ID / 2;
R_RING_BORE = (MMT_OD + FIT_SH) / 2;   // centering-ring / core bore
R_TAB_FLOOR = max(R_MO, RET_CLEAR_D / 2);          // rev B: tab clears the COTS retainer
FIN_TAB_H   = R_OD - R_TAB_FLOOR - FIN_TAB_CLR;

// ----------------------------------------------------------------- stations
X_NC_BASE     = NC_L;
X_SH_END      = NC_L + NC_SH_L;
X_PL_END      = NC_L + PL_L;
X_BAND_END    = X_PL_END + AV_BAND_L;
X_END         = X_BAND_END + BO_L;
L_OVERALL     = X_END;                              // airframe length (excl. COTS retainer)
X_CPL_FWD     = X_PL_END - AV_INS;
X_CPL_AFT     = X_BAND_END + AV_INS;
X_AVB_FWD_OUT = X_CPL_FWD - AV_BH_T;                // AV-303 forward face
X_AVB_AFT_OUT = X_CPL_AFT + GASKET_T;               // AV-304 outer-disc forward face
X_AVB_AFT_END = X_AVB_AFT_OUT + AV_BH_T;            // AV-304 aft face (recovery bay starts)
X_SLED_FWD    = X_CPL_FWD + AV_BH_T + SLED_FWD_GAP;
X_SLED_AFT    = X_SLED_FWD + SLED_L;
X_MMT_AFT     = X_END + MMT_AFT_EXT;
X_MMT_FWD     = X_MMT_AFT - MMT_L;
X_FIN_LE      = X_END - FIN_CR;
X_TAB_FWD     = X_FIN_LE + FIN_TAB_FWD;
X_TAB_AFT     = X_END - LOCK_T;
X_CORE_FWD    = X_TAB_FWD - CORE_RING_T;
X_CORE_AFT    = X_END - LOCK_T;
X_NC_SCREW    = NC_L + NC_SH_L / 2;
X_CAM         = X_SH_END + CAM_OFF;
X_HATCH       = X_SH_END + HATCH_OFF;
X_RB_FWD      = X_MMT_FWD - RB_FWD_OFF;
X_RB_AFT      = X_END - RB_AFT_OFF;
X_TRAY_FWD    = X_AVB_FWD_OUT - TRAY_L;
X_SW          = X_PL_END + AV_BAND_L / 2;
X_MOTOR_FWD   = X_MMT_AFT - MOTOR_L;
X_BAT0        = X_SLED_FWD + 2;
BAT_CAGE_L    = 12 + BAT_L + 0.6;
PAYLOAD_BAY_L  = X_AVB_FWD_OUT - X_SH_END;
RECOVERY_BAY_L = X_MMT_FWD - X_AVB_AFT_END;

FIN_ANGLES      = [for (i = [0 : FIN_N - 1]) i * 360 / FIN_N];
LOCK_SCREW_ANG  = [45, 135, 225, 315];
STATIC_PORT_ANG = [45, 135, 225, 315];

// ----------------------------------------------------------------- geometry helpers
function ogive_rho()  = (R_OD * R_OD + NC_L * NC_L) / (2 * R_OD);
function ogive_r(x)   = sqrt(max(pow(ogive_rho(), 2) - pow(NC_L - x, 2), 0)) + R_OD - ogive_rho();

// Solid of revolution of the tangent ogive between stations x0..x1, radially offset inward by off.
module ogive_solid(x0, x1, off = 0, n = 72) {
    s = (x0 == 0) ? 1 : 0;
    rotate_extrude()
        polygon(concat([[0, x0]],
                       [for (i = [s : n]) let(x = x0 + (x1 - x0) * i / n) [max(ogive_r(x) - off, 0.01), x]],
                       [[0, x1]]));
}

module tube_r(ro, ri, z0, z1) {
    translate([0, 0, z0]) difference() {
        cylinder(r = ro, h = z1 - z0);
        translate([0, 0, -1]) cylinder(r = ri, h = z1 - z0 + 2);
    }
}

module at_angle(a) { rotate([0, 0, a]) children(); }

// Cylinder of diameter d along the radial direction at angle a, from radius r0 to r1, at station z.
module radial_cyl(d, z, a, r0, r1) {
    at_angle(a) translate([r0, 0, z]) rotate([0, 90, 0]) cylinder(d = d, h = r1 - r0);
}

module rounded_rect(l, w, r) { offset(r = r) square([l - 2 * r, w - 2 * r], center = true); }

// Radial prism with a rounded-rectangle footprint (l axial x w tangential) centred at station z.
module radial_prism(a, z, l, w, rr, r0, r1) {
    at_angle(a) translate([r0, 0, z]) rotate([0, 90, 0]) linear_extrude(r1 - r0) rounded_rect(l, w, rr);
}

// Block in the radial frame at angle a: radial r0..r1, tangential +/-hw, stations z0..z1, clipped to radius rc.
module radial_block(a, r0, r1, hw, z0, z1, rc) {
    intersection() {
        at_angle(a) translate([r0, -hw, z0]) cube([r1 - r0, 2 * hw, z1 - z0]);
        translate([0, 0, z0 - 1]) cylinder(r = rc, h = z1 - z0 + 2);
    }
}

// Camera frame: child +Z = lens axis (outward, tilted CAM_TILT aft), origin at the lens face centre.
// Lens-face radius CAM_R0 is the smaller of (a) the tilted barrel rim 0.5 mm inside the bore and
// (b) the tilted camera-body corners 0.5 mm inside the bore -- so any CAM_W/CAM_LEN entered fits.
CAM_SETBACK = CAM_LENS_L * cos(CAM_TILT) + (CAM_LENS_HOLE - 1) / 2 * sin(CAM_TILT) + 0.5;
CAM_R0 = min(R_ID - CAM_SETBACK, sqrt(pow(R_ID - 0.5, 2) - pow(CAM_W / 2, 2)) - CAM_LEN / 2 * sin(CAM_TILT));
module cam_frame() {
    at_angle(CAM_ANG) translate([CAM_R0, 0, X_CAM]) rotate([0, 90 - CAM_TILT, 0]) children();
}

echo(str("ASTRA-66 CAD rev ", CAD_REV, ": L_OVERALL=", L_OVERALL, " payload bay=", PAYLOAD_BAY_L,
         " recovery bay=", RECOVERY_BAY_L, " fin tab depth=", FIN_TAB_H));
