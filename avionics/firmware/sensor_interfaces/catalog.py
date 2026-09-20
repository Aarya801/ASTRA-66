"""Sensor catalogue: what each sensor must measure, and why.

These are REQUIREMENTS for component selection, not manufacturer specifications. No component has been selected, so
every entry is COMPONENT TO BE SELECTED. `candidate_class` repeats the example classes already listed in
`avionics/electronics.csv`; their datasheets have NOT been checked here, and none of their figures is used.

Where a range is derived from the simulation it uses the PLACEHOLDER propulsion input, so it must be re-derived once a
certified motor has been selected (e.g. placeholder peak axial acceleration 7.4 g -> required range >= 16 g, a 2x margin).
"""
from dataclasses import dataclass

from .base import COMPONENT_TO_BE_SELECTED


@dataclass(frozen=True)
class SensorSpec:
    key: str
    sensor: str
    measurement: str
    fields: tuple
    unit: str
    required_range: str
    sampling_rate_hz: float
    rate_note: str
    interface: str
    purpose: str
    failure_considerations: tuple
    candidate_class: str
    component: str = COMPONENT_TO_BE_SELECTED
    basis: str = "requirement (assumption, class C)"


SENSOR_SPECS = (
    SensorSpec(
        key="imu", sensor="Inertial measurement unit (IMU)",
        measurement="Specific force (3 axes) and angular rate (3 axes), body frame (+z toward the nose)",
        fields=("imu_accel_x", "imu_accel_y", "imu_accel_z", "gyro_x", "gyro_y", "gyro_z"),
        unit="m/s² (specific force); deg/s (angular rate)",
        required_range="accel >= ±16 g (2x the 7.4 g PLACEHOLDER peak; re-derive with the certified motor); "
                       "gyro >= ±1000 deg/s (roll rate is not simulated by the 1-DOF model; assumption)",
        sampling_rate_hz=100.0, rate_note=">= 100 Hz to SD (engineering package §8); logged example decimated to 50 Hz",
        interface="I²C or SPI (SPI preferred for rate)",
        purpose="Liftoff and burnout detection, acceleration record, attitude-rate record, estimator input",
        failure_considerations=("saturation above the selected full-scale range", "bias shift with temperature",
                                "vibration aliasing (needs anti-alias filter / ODR choice)", "mounting misalignment",
                                "bus lock-up -> stale samples", "orientation unknown under parachute"),
        candidate_class="6-axis ±32 g class breakout (see avionics/electronics.csv; datasheet not verified)"),
    SensorSpec(
        key="baro", sensor="Barometric pressure sensor",
        measurement="Static pressure (converted on board to altitude above the pad, ISA)",
        fields=("barometric_pressure", "altitude"),
        unit="Pa (pressure); m (altitude above pad)",
        required_range="30 000–110 000 Pa (covers the pad to several km; planned apogee is a few hundred metres, PLACEHOLDER)",
        sampling_rate_hz=50.0, rate_note="50 Hz nominal; >= 20 Hz needed for apogee timing",
        interface="I²C or SPI",
        purpose="Altitude, apogee detection, landing detection, estimator measurement",
        failure_considerations=("static-port placement errors (4 ports at 45°, STATIC_PORT_D)", "light and draughts on the die",
                                "temperature drift", "pressure transients at separation", "stale samples"),
        candidate_class="BMP390 / MS5611 class breakout (see avionics/electronics.csv; datasheet not verified)"),
    SensorSpec(
        key="gnss", sensor="GPS / GNSS receiver",
        measurement="Latitude, longitude, altitude above mean sea level, fix type, satellites used",
        fields=("latitude", "longitude", "gps_altitude", "gps_fix", "gps_satellites"),
        unit="deg (WGS84); m (MSL); fix 0/2/3; count",
        required_range="Position for recovery; must keep or regain fix at the placeholder flight dynamics",
        sampling_rate_hz=1.0, rate_note="1 Hz minimum; higher if the selected module supports it",
        interface="UART (NMEA or binary protocol)",
        purpose="Recovery location, ground track, cross-check of barometric altitude",
        failure_considerations=("no fix on the pad (cold start)", "loss of lock during boost", "antenna shadowing by the airframe",
                                "RF interference from the telemetry radio", "altitude noise much larger than barometric"),
        candidate_class="u-blox M8/M9/M10 class module + patch antenna (see avionics/electronics.csv; datasheet not verified)"),
    SensorSpec(
        key="temperature", sensor="Temperature sensor",
        measurement="Avionics-bay air temperature",
        fields=("temperature",),
        unit="°C",
        required_range="-20 to +60 °C (assumed operating environment)",
        sampling_rate_hz=1.0, rate_note="1 Hz (slow quantity)",
        interface="I²C (or the barometer's internal temperature channel)",
        purpose="Environmental record, barometer and battery context",
        failure_considerations=("self-heating from nearby electronics", "reads board temperature, not air", "stale samples"),
        candidate_class="TMP117 class breakout or barometer internal sensor (see avionics/electronics.csv; datasheet not verified)"),
    SensorSpec(
        key="battery", sensor="Battery monitor",
        measurement="Battery terminal voltage",
        fields=("battery_voltage",),
        unit="V",
        required_range="0–5 V at the ADC input after a divider (1S LiPo, nominal 3.0–4.2 V)",
        sampling_rate_hz=1.0, rate_note="1 Hz",
        interface="ADC via resistor divider",
        purpose="Pad-hold endurance, brown-out diagnosis, go/no-go display on the ground station",
        failure_considerations=("divider tolerance -> calibration needed", "voltage sag under radio transmit load",
                                "ADC reference drift"),
        candidate_class="MCU ADC + divider (values to be chosen with the MCU)"),
    SensorSpec(
        key="separation", sensor="Separation sense (breakwire)",
        measurement="Continuity of a breakwire loop across joint I-03",
        fields=("separation_detected",),
        unit="0/1",
        required_range="Digital input",
        sampling_rate_hz=50.0, rate_note="50 Hz (sampled every logged frame)",
        interface="GPIO input with pull-up (input only)",
        purpose="Logs when the airframe separated; independent confirmation of the recovery event (logging only)",
        failure_considerations=("wire broken during handling (pre-flight continuity check)", "connector bounce"),
        candidate_class="Thin enamel wire + 2-pin connector (see avionics/electronics.csv)"),
)


def spec(key):
    for s in SENSOR_SPECS:
        if s.key == key:
            return s
    raise KeyError(key)
