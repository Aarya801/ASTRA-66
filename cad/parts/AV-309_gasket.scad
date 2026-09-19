// ASTRA-66 CAD rev B -- AV-309 Aft bulkhead face gasket
// Annulus matching the coupler aft end face (CPL_OD / CPL_ID), 1.5 mm EVA foam, modelled compressed at GASKET_T.
// Die/knife cut: OUT="2d".
include <../lib/astra66_core.scad>

OUT = "3d";

module AV_309_gasket() { tube_r(R_CO, R_CI, X_CPL_AFT, X_CPL_AFT + GASKET_T); }

if (OUT == "2d") projection() AV_309_gasket(); else AV_309_gasket();
