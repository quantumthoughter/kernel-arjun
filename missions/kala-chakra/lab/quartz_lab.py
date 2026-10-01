#!/usr/bin/env python3
"""QUARTZ LAB — does a crystal hold memory? Three real mechanisms, honestly.

Quartz (SiO₂) is memory in THREE established ways — and none of them is magic:

  I.   PIEZOELECTRIC CLOCK — quartz vibrates at a fixed frequency; a clock
       counts the vibrations. Memory of *time*, measured.
  II.  GEOLOGICAL RECORD — fluid inclusions, growth zoning, isotopes and
       radiation damage trap the conditions of formation for billions of years.
       Memory of *history*, written literally into the lattice.
  III. 5D OPTICAL STORAGE — fused silica written with a femtosecond laser
       stores ~360 TB, stable for aeons. Memory of *data*, by design.

And ONE esoteric claim we will be honest about: "crystals hold millions of
years of *information* like a hard disk." Reality: they hold physical traces,
not encoded messages — UNLESS we encode them (III).

    python quartz_lab.py
"""
from __future__ import annotations

import math


# --------------------------------------------------------------------------- #
# I. the piezo clock — why quartz keeps time
# --------------------------------------------------------------------------- #

def tuning_fork_frequency(nominal_hz: float = 32768.0, temp_c: float = 25.0,
                          parabolic_ppm: float = -0.035) -> float:
    """A quartz tuning fork drifts with temperature (parabolic, ~ -0.035 ppm/°C²).

    32768 Hz = 2^15 is chosen so a binary counter divides it cleanly to 1 Hz.
    """
    dt = temp_c - 25.0
    ppm = parabolic_ppm * dt * dt
    return nominal_hz * (1 + ppm * 1e-6)


def demo_clock() -> None:
    print("=" * 70)
    print("I. THE PIEZO CLOCK — quartz as memory of TIME")
    print("=" * 70)
    print("  Quartz is PIEZOELECTRIC: squeeze it -> voltage; apply voltage -> it")
    print("  flexes. Cut right, it RINGS at a precise frequency. A counter counts")
    print("  the rings. That count is the time.\n")
    print(f"  {'temp (C)':>9} {'freq (Hz)':>14} {'drift (ppm)':>13}  {'error/day':>12}")
    for t in (0, 25, 40, 60):
        f = tuning_fork_frequency(temp_c=t)
        drift = (f / 32768 - 1) * 1e6
        err_s = abs(drift) * 1e-6 * 86400
        print(f"  {t:>9} {f:>14.4f} {drift:>13.3f}  {err_s:>10.2f} s")
    print("\n  32768 = 2^15 -> a 15-stage binary divider turns it into exactly 1 Hz.")
    print("  The crystal does not store the time; it gives a RHYTHM, and we")
    print("  count. Memory of time = a rhythm + a counter. Same as our Heart's")
    print("  'one clock, true pace'.")


# --------------------------------------------------------------------------- #
# II. geological memory — the lattice as a ledger
# --------------------------------------------------------------------------- #

def half_lives_survived(parent_fraction: float | None = None,
                        years: float = 0, half_life: float = 1.0) -> dict:
    """Radiometric decay N(t) = N0 * (1/2)^(t/t12). The crystal counts its own age."""
    remaining = 0.5 ** (years / half_life) if half_life else 0
    return {"years": years, "half_life": half_life, "parent_remaining": remaining}


def demo_geology() -> None:
    print("\n" + "=" * 70)
    print("II. GEOLOGICAL MEMORY — the lattice as a LEDGER of deep time")
    print("=" * 70)
    print("  A growing crystal does not reset. It ACCUMULATES:")
    print("    - fluid inclusions: droplets of the water/air it grew in, sealed")
    print("    - growth zoning: rings like tree rings, each a chemical epoch")
    print("    - isotope ratios: a clock set at birth, ticking by decay")
    print("    - radiation damage: self-inflicted tracks, countable\n")
    print("  A radiometric clock is just a half-life ledger:")
    print(f"  {'material':22s} {'half-life':>14s} {'age recorded':>16s}")
    rows = [
        ("Carbon-14", "5,730 yr", "up to ~50,000 yr"),
        ("Uranium-238", "4.47 Byr", "billions of yr"),
        ("Rubidium-87", "48.8 Byr", "billions of yr"),
        ("Zircon (U-Pb)", "—", "4.4 Byr (Jack Hills)"),
    ]
    for m, h, a in rows:
        print(f"  {m:22s} {h:>14s} {a:>16s}")
    # show decay over a billion years
    print("\n  Example — fraction of a parent isotope left after t:")
    t12 = 4.47e9  # U-238
    print(f"  {'years':>14} {'parent left':>13}")
    for y in (0, 1e9, 2.2e9, 4.47e9, 1e10):
        r = half_lives_survived(years=y, half_life=t12)
        print(f"  {y:>14.2e} {r['parent_remaining']:>13.4f}")
    print("\n  So a zircon grain is a PHYSICAL LEDGER: it records when it formed,")
    print("  at what temperature, in what fluid — for 4.4 BILLION years. That is")
    print("  real memory of Earth's history. Not encoded speech — recorded state.")


# --------------------------------------------------------------------------- #
# III. 5D optical storage — writing data into glass itself
# --------------------------------------------------------------------------- #

def optical_5d_capacity(disc_layers: int = 1) -> dict:
    """Fused-silica 5D: femtosecond laser writes nanoscale voxels.

    Reported ~360 TB on a single 5-inch disc (Univ. of Southampton, 2016).
    """
    tb = 360 * disc_layers
    return {"terabyte": tb, "raw_bytes": int(tb * 1e12)}


def arrhenius_lifetime(temp_c: float, ref_temp_c: float = 25.0,
                       ref_years: float = 3e20, activation_ev: float = 1.0) -> float:
    """Extrapolate storage lifetime with an Arrhenius model (illustrative).

    Higher temperature -> faster decay. The 5D-optical claim: at room temp the
    written structure is stable for aeons (reported 'billions of years').
    """
    k_b = 8.617e-5  # eV/K
    T = temp_c + 273.15
    Tr = ref_temp_c + 273.15
    # rate ratio ~ exp(Ea/k (1/Tr - 1/T))
    ratio = math.exp((activation_ev / k_b) * (1 / Tr - 1 / T))
    return ref_years / ratio


def demo_optical() -> None:
    print("\n" + "=" * 70)
    print("III. 5D OPTICAL STORAGE — writing DATA into glass itself")
    print("=" * 70)
    print("  A femtosecond laser fires into fused silica. Each pulse changes the")
    print("  glass at the nanoscale, encoding FIVE dimensions per voxel:")
    print("    (x, y, z) + the slow-axis ORIENTATION of birefringence + its")
    print("    RETARDANCE (strength). Light is read back through a microscope.\n")
    cap = optical_5d_capacity()
    print(f"  Reported capacity : {cap['terabyte']} TB on one 5-inch disc")
    print(f"  Written element   : ~nanoscale voxels, 3 layers of 'time + space'")
    print(f"\n  Lifespan (Arrhenius extrapolation, illustrative):")
    print(f"  {'storage temp':>14} {'half-life (years)':>20}")
    for tc in (25, 100, 200, 500, 1000):
        life = arrhenius_lifetime(tc)
        print(f"  {tc:>12} C {life:>20.2e}")
    print("\n  Read plainly: at room temperature the written structure is")
    print("  essentially permanent on human timescales. That is why it is called")
    print("  the 'Superman memory crystal' — a message that outlives civilizations.")
    print("  This is the ONE sense in which 'a crystal holds data for millions of")
    print("  years' is literally TRUE — because we WROTE it there on purpose.")


# --------------------------------------------------------------------------- #
# IV. the honesty ledger
# --------------------------------------------------------------------------- #

def demo_honesty() -> None:
    print("\n" + "=" * 70)
    print("IV. THE HONESTY LEDGER — what is true, what is poetry")
    print("=" * 70)
    claims = [
        ("[E]", "Quartz is piezoelectric and keeps time to seconds/day", True),
        ("[E]", "Crystals trap fluids, isotopes & damage for billions of years", True),
        ("[E]", "5D optical storage puts ~360 TB in glass, stable for aeons", True),
        ("[I]", "A crystal 'records' geological history (state, not speech)", True),
        ("[S]", "Crystals hold 'millions of years of data' like a hard disk", False),
        ("[S]", "Crystals carry messages/awareness (Akashic 'records')", False),
    ]
    for tag, claim, established in claims:
        mark = "✓ established" if established else "✗ not established"
        print(f"  {tag}  {claim:58s} {mark}")
    print("\n  A crystal stores PHYSICAL STATE — which is real memory (I & II), and")
    print("  can hold ENCODED DATA if we write it (III). It does not hold language,")
    print("  thought, or history-as-story unless something put it there.")
    print("\n  The esoteric intuition is not foolish — it is IMPRECISE. The crystal")
    print("  truly is a witness of deep time. It simply does not 'speak' unless a")
    print("  reader (a laser, a mass spectrometer, or a mind) decides to read it.")
    print("  Which is the whole lesson: memory is not in the thing. It is in the")
    print("  READER and the REFERENCE. The crystal is the substrate; we are the māyā.")


def main() -> None:
    print("\n" + "#" * 70)
    print("#  QUARTZ LAB — does a crystal hold memory?")
    print("#" * 70)
    demo_clock()
    demo_geology()
    demo_optical()
    demo_honesty()
    print("\n" + "#" * 70)
    print("#  A crystal is not magic. It is a SUBSTRATE — and substrates are the")
    print("#  only place memory has ever lived. The magic was always the reader.")
    print("#" * 70 + "\n")


if __name__ == "__main__":
    main()
