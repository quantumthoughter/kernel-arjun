# The Science of a Memory Cell — SLC → QLC

*A teaching note. Numbers are order-of-magnitude; where exactness is impossible,
it says so.*

---

## 1. How many cells in 1 TB? (your "8 trillion")

A bit is a bit. A cell holds *N* bits depending on its type:

| Type | Bits/cell | Levels | 1 TB needs | 1 TiB needs |
|---|---|---|---|---|
| SLC | 1 | 2 | **8.00 trillion** | 8.80 T |
| MLC | 2 | 4 | 4.00 T | 4.40 T |
| TLC | 3 | 8 | 2.67 T | 2.93 T |
| **QLC** | **4** | **16** | **2.00 T** | 2.20 T |

**So "1 TB = 8 trillion cells" is correct — for SLC (1 bit/cell).** The *same
8 trillion cells*, run as QLC, would hold **4 TB**. And a 1 TB QLC drive needs
only **~2 trillion physical cells**.

⚠️ Real drives hold **more** cells than this: ECC, metadata, and over-provisioning
typically add **7–30%**, so a "1 TB" QLC SSD physically has ~2.1–2.6 trillion cells.

**The key lesson:** "how many cells" and "how many bits" are different questions.
Capacity per cell is the whole SLC→QLC story.

---

## 2. Is it a counted number of electrons? — No. It's charge, then a *threshold*.

The cell is a **floating-gate MOSFET** (or charge-trap). It stores **electrons**
on an insulated gate that has nowhere to leak to. Those electrons don't get
counted one by one at read time. Instead:

1. **Write:** a high voltage pushes electrons through a thin oxide onto the
   floating gate (*Fowler–Nordheim tunneling*) — or a current kicks them across
   (*hot-electron injection*) for NOR.
2. **The stored charge shifts the transistor's threshold voltage (Vth).** More
   electrons = higher Vth.
3. **Read:** apply a reference voltage and see whether the transistor conducts.
   The *amount* of charge is inferred from *how much Vth moved*.

So the data is not an electron tally — it is **a voltage level** read against
**references**. That is why more levels require finer voltage discrimination.

### How many electrons? (order of magnitude, honest)

| Type | Electrons stored (approx) | Gap between adjacent levels |
|---|---|---|
| SLC | ~10²–10³ | — (only 2 levels) |
| MLC | ~10²–10³ | ~tens–hundreds |
| TLC | ~10²–10³ | ~tens |
| **QLC** | **~10²–10³ total** | **~a few to a few tens** |

⚠️ I am deliberately giving **ranges**, not a single number: it depends heavily
on node, 2D vs 3D, capacitance, and design. What is *certain* and reported
widely: **QLC distinguishes 16 states with only a handful of electrons between
neighbours.** That is the physical reason QLC is fragile.

*My own first-principles estimate (Q = C·V with fF-scale capacitance) lands in
the hundreds-of-electrons range for total charge — consistent with the table.*

---

## 3. Doping — a density, never a count

You asked: "do they measure the number of electrons?" **No — they measure a
*density* of dopant atoms**, statistically, and it becomes a sea of carriers
(an "electron gas"), not individual counted particles.

Silicon has **~5 × 10²² atoms/cm³**.

| Region | Dopant density | Meaning |
|---|---|---|
| channel (light) | ~10¹⁵ /cm³ | 1 dopant per ~50,000,000 Si atoms |
| well (moderate) | ~10¹⁸ /cm³ | 1 per ~50,000 |
| source/drain (heavy) | ~10²⁰ /cm³ | 1 per ~500 |

Doping creates **free carriers in enormous numbers** — it's a **fraction**, a
concentration in atoms per cubic centimetre, not a hand-counted electron total.
The precision demanded is in the **density and junction placement**, achieved by
ion implantation (dose in ions/cm²) and annealing, not by counting particles.

**So: the "ratio" they must be precise about is a *concentration*, typically to
within a few percent — a statistics-of-millions control, not a single-electron
precision.** (Single-electron precision appears only in the *stored charge* of the
cell, and even there it's read as a voltage, not counted.)

---

## 4. How the charge is written and erased

- **Program (write):** Fowler–Nordheim tunneling (NAND) — a large field (~15–20
  MV/cm) across a ~5–10 nm tunnel oxide lets electrons quantum-tunnel through.
- **Erase:** reverse the field; electrons tunnel back off, in whole **blocks**.
- **NOR** uses **hot-electron injection** (faster, but higher current).
- Manufacturing precision lives in: **tunnel-oxide thickness (atomic-layer
  deposition, ~Ångström control)**, **lithography** (nm-scale cells), and
  **cell geometry** (3D NAND stacks 100+ layers vertically).

The "magic" is the **insulating oxide**: it holds charge for years (retention)
yet lets charge tunnel in/out on command. That contradiction is the whole art.

---

## 5. Why QLC wears out faster than SLC

More levels = smaller margins = more fragility:

| Mechanism | What it is | Hits QLC hardest |
|---|---|---|
| **P/E wear** | each erase damages the oxide | yes — tighter margin, fewer cycles |
| **Retention loss** | charge slowly leaks | tiny margins mean small leaks flip a level |
| **Read disturb** | reads nudge neighbouring charge | yes |
| **RTN (random telegraph noise)** | single-electron trapping/detrapping shifts Vth | at QLC margins, a *few electrons* matter |
| **Cell-to-cell interference** | neighbours' charge affects Vth | finer spacing, worse |

This is the **noise wall**. It is *why* "2GB → 12GB" by "more bits per cell" is
bounded: charge is a continuous quantity, but noise makes the distinguishable
levels finite. QLC (16 levels) is near that practical limit today.

---

## The whole truth in one paragraph

A flash cell stores **electrons** on an insulated gate; the count is read as a
**threshold voltage**, not tallied. More electrons = higher voltage = a level.
SLC uses 2 levels (1 bit), QLC uses 16 (4 bits) — so **the same silicon holds 4×
the data as QLC**, and a 1 TB QLC drive needs ~2 trillion cells. But each extra
level shrinks the margin between states to a **handful of electrons**, and
physical noise (leakage, RTN, disturb, wear) then limits how many levels you can
reliably tell apart. **That noise ceiling — not any lack of cleverness — is why
you cannot create unlimited storage from charge.** The escape from the ceiling is
not in the cell; it is in **compression** — not storing what the model can
predict.

---

*Written for the Kālacakra mission. Sources: standard flash-memory literature
(Fowler–Nordheim, charge-trap/floating-gate NAND, RTN). Ranges flagged where the
literature varies.*
