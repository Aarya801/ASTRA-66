"""International Standard Atmosphere (ISO 2533 / ICAO Doc 7488), geopotential altitude 0-20 km.

Troposphere (0-11 km):  T = T0 - L*h,  p = p0 * (T/T0)^(g0/(R*L))
Tropopause (11-20 km):  T = 216.65 K,   p = p11 * exp(-g0*(h - 11000)/(R*T))
rho = p/(R*T), a = sqrt(gamma*R*T), mu (Sutherland) = 1.458e-6*T^1.5/(T + 110.4), nu = mu/rho.

Off-standard days use an ISA temperature offset dT at unchanged pressure (common engineering practice).
"""
import math

G0 = 9.80665          # m/s^2, standard gravity
R_AIR = 287.05287     # J/(kg K)
GAMMA = 1.4
T0 = 288.15           # K
P0 = 101325.0         # Pa
LAPSE = 0.0065        # K/m
P11 = 22632.06        # Pa at 11 km


def isa(h_msl, dT=0.0):
    """Atmospheric state at geopotential altitude h_msl (m) with temperature offset dT (K)."""
    h = max(0.0, min(h_msl, 20000.0))
    if h <= 11000.0:
        t_std = T0 - LAPSE * h
        p = P0 * (t_std / T0) ** (G0 / (R_AIR * LAPSE))
    else:
        t_std = 216.65
        p = P11 * math.exp(-G0 * (h - 11000.0) / (R_AIR * t_std))
    T = t_std + dT
    rho = p / (R_AIR * T)
    mu = 1.458e-6 * T ** 1.5 / (T + 110.4)
    return dict(T=T, p=p, rho=rho, a=math.sqrt(GAMMA * R_AIR * T), mu=mu, nu=mu / rho)


if __name__ == "__main__":
    for h in (0, 500, 1000, 1500, 11000):
        s = isa(h)
        print(f"{h:>6} m  T {s['T']:.2f} K  p {s['p']:.0f} Pa  rho {s['rho']:.4f} kg/m3  a {s['a']:.1f} m/s")
