"""ASTRA-66 avionics and flight-data system (Phase 4): sensing, logging, telemetry, ground display, post-flight analysis.

Safety boundary: this package reads sensors and produces data only. It has no output channel to any igniter,
pyrotechnic, energetic or deployment device, and none may be added to it. Recovery uses the certified motor's own
ejection, prepared by a mentor. The avionics are a draft student design and are NOT flight certified.
"""
