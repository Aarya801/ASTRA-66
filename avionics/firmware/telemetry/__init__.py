"""TELEMETRY: packet format and hardware-independent link interface.

SIMULATED TELEMETRY (software link, runs anywhere) is implemented. REAL HARDWARE TELEMETRY is only an interface:
no radio has been selected (COMPONENT TO BE SELECTED), and any radio must use a band and power level legal where it
is operated. Every packet carries a SIMULATED flag so a receiver can never mistake simulated data for flight data.
"""
