#!/usr/bin/env python3
"""MEMORY LAB — from a capacitor to a flash cell, simulated honestly.

Answers, by running the actual numbers:
  I.   a capacitor IS memory (charge = the bit)
  II.  why DRAM leaks and refreshes, why flash doesn't
  III. how a cell is READ as 0/1 — a decision against a reference
  IV.  how a GRID is addressed (one cell out of billions) with row/column wires
  V.   how QLC puts 16 levels in one cell

No magic. Just Q = C·V, a leaky exponential, and a comparator.

    python memory_lab.py
"""
from __future__ import annotations

import math

E = 1.602e-19      # coulomb (elementary charge)


# --------------------------------------------------------------------------- #
# I. a capacitor is memory
# --------------------------------------------------------------------------- #

def capacitor(volts: float, capacitance_ff: float = 20.0) -> dict:
    """A real DRAM cell capacitor is ~5-30 fF. Charge stored = C·V."""
    C = capacitance_ff * 1e-15
    Q = C * volts
    return {
        "volts": volts,
        "capacitance_fF": capacitance_ff,
        "charge_coulombs": Q,
        "electrons": Q / E,
    }


def demo_capacitor() -> None:
    print("=" * 68)
    print("I. A CAPACITOR IS MEMORY  (Q = C·V)")
    print("=" * 68)
    print("  A DRAM bit = 1 transistor + 1 tiny capacitor.")
    print("  Charged = 1, discharged = 0.  The 'bit' is literally charge.\n")
    print(f"  {'volts':>6} {'charge (C)':>14} {'electrons':>12}")
    for v in (0.0, 0.5, 1.0, 1.8):
        r = capacitor(v)
        print(f"  {v:>6.1f} {r['charge_coulombs']:>14.3e} {r['electrons']:>12,.0f}")
    print("\n  ~1 volt on 20 fF is only ~125,000 electrons — a countable-ish crowd,")
    print("  which is why scaling down makes memory fragile.")


# --------------------------------------------------------------------------- #
# II. leak vs insulated
# --------------------------------------------------------------------------- #

def leak(volts0: float, tau_ms: float, t_ms: float) -> float:
    """Charge leaks exponentially: V(t) = V0 · e^(-t/tau)."""
    return volts0 * math.exp(-t_ms / tau_ms)


def demo_leak() -> None:
    print("\n" + "=" * 68)
    print("II. WHY DRAM REFRESHES, WHY FLASH DOESN'T")
    print("=" * 68)
    print("  Capacitor voltage decays: V(t) = V0 · e^(-t/tau)\n")
    print(f"  {'time (ms)':>10} {'DRAM τ=20ms':>14} {'FLASH τ=10yr':>16}")
    for t in (0, 10, 50, 100, 200):
        dram = leak(1.0, 20.0, t)
        # flash tau ~ 10 years in ms
        flash = leak(1.0, 10 * 365 * 24 * 3600 * 1000, t)
        print(f"  {t:>10} {dram:>14.4f} {flash:>16.6f}")
    print("\n  DRAM loses the bit in tens of ms -> must REFRESH ~every 64 ms.")
    print("  FLASH's charge sits on an INSULATED gate (nowhere to go) -> holds")
    print("  for ~10 years. Same physics; only the leakage path differs.")


# --------------------------------------------------------------------------- #
# III. reading is a decision against a reference
# --------------------------------------------------------------------------- #

def read_bit(volts: float, reference: float = 0.5) -> int:
    """'0/1' is not in the cell. It is decided by comparison to a reference."""
    return 1 if volts > reference else 0


def demo_read() -> None:
    print("\n" + "=" * 68)
    print("III. A READ IS A DECISION, NOT A THING")
    print("=" * 68)
    print("  There is no '1' inside the cell — only volts. We compare to a")
    print("  reference and CALL the result 0 or 1.\n")
    print(f"  {'cell volts':>11} {'> 0.5?':>8} {'we call it':>11}")
    for v in (0.1, 0.3, 0.49, 0.51, 0.7, 1.0):
        b = read_bit(v)
        print(f"  {v:>11.2f} {str(v>0.5):>8} {b:>11}")
    print("\n  Move the reference to 0.8 and the SAME voltages read differently.")
    print("  The bit is a convention. The voltage is the reality.")


# --------------------------------------------------------------------------- #
# IV. the grid: addressing one cell with row/column wires
# --------------------------------------------------------------------------- #

class Crossbar:
    """An N×M grid of cells addressed by one row wire + one column wire.

    This is how billions of cells are reached with only ~sqrt(N) wires:
    row line selects the row; column line reads/writes the intersection.
    """

    def __init__(self, rows: int, cols: int):
        self.rows, self.cols = rows, cols
        self.cells = [[0.0] * cols for _ in range(rows)]  # store VOLTS, not bits

    def write(self, r: int, c: int, volts: float) -> None:
        self.cells[r][c] = volts

    def read(self, r: int, c: int, ref: float = 0.5) -> int:
        return 1 if self.cells[r][c] > ref else 0

    def wires(self) -> int:
        return self.rows + self.cols


def demo_grid() -> None:
    print("\n" + "=" * 68)
    print("IV. THE GRID — reaching billions of cells with few wires")
    print("=" * 68)
    gb = Crossbar(4, 4)
    for r in range(4):
        for c in range(4):
            gb.write(r, c, 1.0 if (r + c) % 2 == 0 else 0.0)
    print("  a 4x4 crossbar (row+col addressing), 8 wires for 16 cells:\n")
    for r in range(4):
        print("   row", r, ":", " ".join(str(gb.read(r, c)) for c in range(4)))
    print(f"\n  wires for 16 cells: {gb.wires()}  (not 16!)")
    print("  Scale up: a 32768×32768 grid holds ~1 billion cells on")
    print("  65,536 wires — because each cell shares its row and column line.")
    print("  'Which wire connects where' is FIXED at fabrication (a mask),")
    print("  and selection is done by ENERGIZING one row + one column.")

    # how many cells a modern NAND chip addresses
    for name, (r, c) in {"NAND die (illustrative)": (32768, 32768)}.items():
        cells = r * c
        print(f"\n  {name}: {r}×{c} = {cells/1e9:.2f} billion cells, "
              f"{r+c:,} wires")


# --------------------------------------------------------------------------- #
# V. QLC: sixteen levels in one cell
# --------------------------------------------------------------------------- #

def demo_qlc() -> None:
    print("\n" + "=" * 68)
    print("V. QLC — SIXTEEN LEVELS IN ONE CELL")
    print("=" * 68)
    print("  SLC: 2 levels (1 bit). QLC: 16 levels (4 bits). Same cell!\n")
    levels = 16
    vmax = 4.0
    step = vmax / levels
    print(f"  {levels} levels across 0..{vmax} V  ->  {step:.3f} V per level")
    print(f"  {'level':>5} {'volts':>8} {'4-bit code':>12} {'electrons offset':>18}")
    for i in range(levels):
        v = (i + 0.5) * step
        # approximate electrons per level on a ~1000e full window
        e_off = i * (1000 / levels)
        print(f"  {i:>5} {v:>8.3f} {format(i, '04b'):>12} {e_off:>18.0f}")
    print(f"\n  Adjacent levels are only ~{1000/levels:.0f} electrons apart (approx).")
    print("  Noise that moves a few electrons can flip a level — why QLC is fragile.")
    print("  But 16 levels double the capacity of TLC and 4x SLC. That is the trade.")


def main() -> None:
    print("\n" + "#" * 68)
    print("#  MEMORY LAB — capacitor -> DRAM -> flash -> QLC -> grid")
    print("#" * 68)
    demo_capacitor()
    demo_leak()
    demo_read()
    demo_grid()
    demo_qlc()
    print("\n" + "#" * 68)
    print("#  The bit is a decision. The charge is the reality. The grid is")
    print("#  a fixed map of wires. Complexity is not magic — it is REPETITION")
    print("#  of one simple cell, addressed cleverly, verified against a reference.")
    print("#" * 68 + "\n")


if __name__ == "__main__":
    main()
