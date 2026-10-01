#!/usr/bin/env python3
"""CD LAB — how an optical disc "remembers" without holding any charge.

A flash cell stores CHARGE. A CD stores TOPOGRAPHY (physical pits). Yet both
end the same way: a continuous physical signal, compared to a reference, becomes
a bit. Same māyā, different body.

    python cd_lab.py
"""
from __future__ import annotations

import math


# The laser travels INSIDE polycarbonate (n ≈ 1.55), so the light's wavelength
# in the medium is shorter: lambda_medium = lambda_vacuum / n.
POLYCARBONATE_N = 1.55


def reflectance(pit: bool, depth_nm: float = 125.0, wavelength_nm: float = 780.0,
                n: float = POLYCARBONATE_N) -> float:
    """A CD is a mirror with pits. The laser reflects off land, and off the pit.

    Destructive interference happens when the round-trip path difference
    (2·depth, seen inside the plastic) equals half a wavelength:
        2·d = lambda_medium / 2   ->   d = lambda_medium / 4 = lambda/(4n)

    For a 780 nm IR laser in polycarbonate (n≈1.55): 780/(4·1.55) ≈ 126 nm.
    That is exactly why real CD pits are ~110-130 nm deep.
    """
    if not pit:
        return 1.0  # flat land: full reflection
    lam_medium = wavelength_nm / n
    phase = 4 * math.pi * depth_nm / lam_medium  # round-trip path difference
    # interference of the land-reflected and pit-reflected beams -> 0..1
    return (1 + math.cos(phase)) / 2


def read_track(pits: list[bool]) -> list[int]:
    """The reader samples reflected light and DECIDES 0/1 against a threshold.

    On a CD, the information is not the pit itself — it is the TRANSITION
    between pit and land. A change of reflectance = a 1; no change = 0.
    """
    refl = [reflectance(p) for p in pits]
    bits = []
    for i in range(1, len(refl)):
        change = abs(refl[i] - refl[i - 1])
        bits.append(1 if change > 0.5 else 0)
    return bits


def main() -> None:
    print("=" * 68)
    print("CD LAB — topography, not charge")
    print("=" * 68)

    print("\n[1] How a pit becomes a 'dark' spot (destructive interference)")
    print(f"    (laser inside plastic n=1.55 -> lambda_medium = 780/1.55 = "
          f"{780/POLYCARBONATE_N:.0f} nm)")
    print(f"    {'depth (nm)':>11} {'reflectance':>12}  {'looks':>8}")
    for d in (0, 63, 126, 189, 252):
        r = reflectance(True, depth_nm=d)
        print(f"    {d:>11} {r:>12.3f}  {'land' if r>0.75 else 'PIT' if r<0.25 else 'mid':>8}")
    print(f"    ~126 nm ≈ lambda/(4n)  ->  pit reflection cancels -> reads dark.")
    print("    Real CDs use ~110-130 nm pits, matching this prediction.")
    print("    (a CD is a mirror; the data is tiny dark pits a quarter-wave deep)")

    print("\n[2] Reading: it is the CHANGE (edge) that carries the bit")
    pits = [False, False, True, True, False, True, False, False, True, True, True, False]
    drawn = "".join("█" if p else "·" for p in pits)
    print(f"    surface : {drawn}")
    print(f"               (█ = land/mirror, · = pit/dark)")
    print(f"    bits    : {read_track(pits)}")
    print("    A 1 is where the surface CHANGES; a 0 is where it stays. The CD")
    print("    stores TRANSITIONS, not 'on/off' bits directly — this is EFM coding.")

    print("\n[3] Compared with flash — same ending, different body")
    print(f"    {'':16} {'stores':>14} {'read as':>18} {'volatile?':>12}")
    print(f"    {'DRAM':16} {'charge':>14} {'voltage vs ref':>18} {'yes (refresh)':>12}")
    print(f"    {'Flash':16} {'charge (sealed)':>14} {'Vth vs ref':>18} {'no (~10 yr)':>12}")
    print(f"    {'CD/DVD':16} {'pits & lands':>14} {'reflection vs ref':>18} {'no (forever)':>12}")
    print("\n    All three: a continuous physical quantity, a threshold, a decision.")
    print("    None of them holds a '0' or a '1'. We cast the spells each time.")

    print("\n[4] Why a CD holds 'forever' — no charge to leak")
    print("    Flash can lose charge (retention). A CD's pits are physical shape.")
    print("    Nothing decays in years; only scratches and sunlight harm it.")
    print("    That is why optical media is an ARCHIVAL tier: shape outlasts charge.")


if __name__ == "__main__":
    main()
