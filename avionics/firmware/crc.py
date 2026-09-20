"""CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no final XOR). Used by log rows and telemetry packets."""


def _table():
    t = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) if c & 0x8000 else (c << 1)
        t.append(c & 0xFFFF)
    return t


_T = _table()


def crc16(data, crc=0xFFFF):
    """Return the CRC of `data` (bytes or str; str is UTF-8 encoded). Check value: crc16(b"123456789") == 0x29B1."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ _T[((crc >> 8) ^ b) & 0xFF]
    return crc
