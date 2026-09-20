"""Hardware-independent flight-computer software (reference implementation in Python).

Layers: sensor_interfaces -> flight_state (processing) -> logging / telemetry. The same structure is intended to be
ported to the selected microcontroller once hardware exists; until then everything runs against simulated sensors.
"""
