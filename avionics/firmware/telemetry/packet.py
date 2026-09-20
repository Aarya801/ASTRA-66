"""Telemetry packet v2: 41 bytes, little-endian, fixed-point, CRC-16 protected.

v2 (Phase 5) assigns the previously unused flag bits 3-7 to sensor health; the layout is otherwise identical to v1.
The decoder accepts v1 and v2; a v1 packet carries no health information (health fields decode as None).

  offset size field            encoding
  0      2    sync             b"\\xA5\\x66"
  2      1    version          2
  3      1    flags            bit0 SIMULATED, bit1 GPS_VALID, bit2 SEPARATION,
                               bit3 IMU_OK, bit4 BARO_OK, bit5 GNSS_OK, bit6 TEMP_OK, bit7 BATTERY_OK
                               (sensor OK = a valid sample within 3 nominal sample periods)
  4      2    seq              uint16, wraps
  6      4    time             uint32 milliseconds since clock start
  10     1    flight_state     0 PRELAUNCH, 1 ASCENT, 2 COAST, 3 DESCENT, 4 LANDED, 255 unknown
  11     1    gps_fix          uint8 (255 = unknown)
  12     1    gps_satellites   uint8 (255 = unknown)
  13     4    altitude         int32, 0.1 m (barometric, above pad)
  17     2    vertical_vel     int16, 0.01 m/s
  19     2    accel_axial      int16, 0.01 m/s² (specific force, body z)
  21     2    accel_magnitude  int16, 0.01 m/s²
  23     2    temperature      int16, 0.01 °C
  25     4    latitude         int32, 1e-7 deg
  29     4    longitude        int32, 1e-7 deg
  33     4    gps_altitude     int32, 0.1 m (MSL)
  37     2    battery          uint16, mV
  39     2    crc16            CRC-16/CCITT-FALSE of bytes 0..38

Missing values use the most negative value of the signed type (or the maximum of an unsigned one). Values beyond the
encodable range saturate at the limit. The packet carries summaries at 2–5 Hz; full-rate data stay on the SD card.
"""
import struct
from dataclasses import dataclass, fields as dc_fields

from ..crc import crc16

SYNC = b"\xA5\x66"
VERSION = 2
SUPPORTED_VERSIONS = (1, 2)
FMT = "<2sBBHIBBBihhhhiiiH"
BODY_SIZE = struct.calcsize(FMT)
PACKET_SIZE = BODY_SIZE + 2
FLAG_SIMULATED, FLAG_GPS_VALID, FLAG_SEPARATION = 1, 2, 4
HEALTH_BITS = dict(imu_ok=8, baro_ok=16, gnss_ok=32, temp_ok=64, battery_ok=128)
STATES = ["PRELAUNCH", "ASCENT", "COAST", "DESCENT", "LANDED"]
I16, I32 = (-32768, 32767), (-2147483648, 2147483647)


class PacketError(ValueError):
    """Raised for a packet that cannot be trusted (bad length, sync, version or CRC)."""


@dataclass
class TelemetryFrame:
    seq: int
    time_s: float
    simulated: bool
    flight_state: str = None
    altitude_m: float = None
    vertical_velocity_mps: float = None
    accel_axial_mps2: float = None
    accel_magnitude_mps2: float = None
    temperature_c: float = None
    latitude_deg: float = None
    longitude_deg: float = None
    gps_altitude_m: float = None
    gps_fix: int = None
    gps_satellites: int = None
    battery_voltage_v: float = None
    separation: bool = False
    imu_ok: bool = None             # sensor health (v2); None = unknown (v1 packet or not reported)
    baro_ok: bool = None
    gnss_ok: bool = None
    temp_ok: bool = None
    battery_ok: bool = None

    def as_dict(self):
        return {f.name: getattr(self, f.name) for f in dc_fields(self)}


def _enc(v, scale, lim):
    if v is None:
        return lim[0]
    return max(lim[0] + 1, min(lim[1], int(round(v * scale))))


def _dec(n, scale, lim):
    return None if n == lim[0] else n / scale


def encode(frame):
    flags = ((FLAG_SIMULATED if frame.simulated else 0) | (FLAG_SEPARATION if frame.separation else 0)
             | (FLAG_GPS_VALID if frame.latitude_deg is not None and frame.longitude_deg is not None else 0)
             | sum(bit for name, bit in HEALTH_BITS.items() if getattr(frame, name)))
    state = STATES.index(frame.flight_state) if frame.flight_state in STATES else 255
    u8 = lambda v: 255 if v is None else max(0, min(254, int(v)))  # noqa: E731
    batt = 0xFFFF if frame.battery_voltage_v is None else max(0, min(0xFFFE, int(round(frame.battery_voltage_v * 1000))))
    body = struct.pack(FMT, SYNC, VERSION, flags, frame.seq & 0xFFFF, int(round(frame.time_s * 1000)) & 0xFFFFFFFF,
                       state, u8(frame.gps_fix), u8(frame.gps_satellites),
                       _enc(frame.altitude_m, 10, I32), _enc(frame.vertical_velocity_mps, 100, I16),
                       _enc(frame.accel_axial_mps2, 100, I16), _enc(frame.accel_magnitude_mps2, 100, I16),
                       _enc(frame.temperature_c, 100, I16), _enc(frame.latitude_deg, 1e7, I32),
                       _enc(frame.longitude_deg, 1e7, I32), _enc(frame.gps_altitude_m, 10, I32), batt)
    return body + struct.pack("<H", crc16(body))


def decode(data):
    if len(data) != PACKET_SIZE:
        raise PacketError(f"length {len(data)} != {PACKET_SIZE}")
    body, (crc,) = data[:BODY_SIZE], struct.unpack("<H", data[BODY_SIZE:])
    if body[:2] != SYNC:
        raise PacketError("bad sync")
    if crc16(body) != crc:
        raise PacketError("CRC mismatch")
    (_, ver, flags, seq, t_ms, state, fix, sats, alt, vz, ax, am, temp, lat, lon, galt, batt) = struct.unpack(FMT, body)
    if ver not in SUPPORTED_VERSIONS:
        raise PacketError(f"unsupported version {ver}")
    gps_ok = bool(flags & FLAG_GPS_VALID)
    health = {name: (bool(flags & bit) if ver >= 2 else None) for name, bit in HEALTH_BITS.items()}
    return TelemetryFrame(
        seq=seq, time_s=t_ms / 1000.0, simulated=bool(flags & FLAG_SIMULATED),
        flight_state=STATES[state] if state < len(STATES) else None,
        altitude_m=_dec(alt, 10, I32), vertical_velocity_mps=_dec(vz, 100, I16), accel_axial_mps2=_dec(ax, 100, I16),
        accel_magnitude_mps2=_dec(am, 100, I16), temperature_c=_dec(temp, 100, I16),
        latitude_deg=_dec(lat, 1e7, I32) if gps_ok else None, longitude_deg=_dec(lon, 1e7, I32) if gps_ok else None,
        gps_altitude_m=_dec(galt, 10, I32), gps_fix=None if fix == 255 else fix, gps_satellites=None if sats == 255 else sats,
        battery_voltage_v=None if batt == 0xFFFF else batt / 1000.0, separation=bool(flags & FLAG_SEPARATION), **health)
