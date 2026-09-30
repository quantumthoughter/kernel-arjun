#!/usr/bin/env python3
"""The compression laboratory.

Honest experiments in shrinking an agent's memory — measuring what actually
works. We do NOT claim to beat Shannon. We measure the real ratios that matter:

  1. entropy & theoretical floor (what is *possible*, from the data itself)
  2. general compressors (zlib / bz2 / lzma) — the honest baseline
  3. dedup + delta (memory repeats itself; store the *surprise*)
  4. neural-latent storage — store meaning (embeddings), not text
  5. "charge levels" analogy — bits per unit, and why it has a ceiling

Run:  python -m arjun.compress <dir-or-file>
"""
from __future__ import annotations

import bz2
import hashlib
import json
import lzma
import math
import zlib
from collections import Counter
from pathlib import Path


# --------------------------------------------------------------------------- #
# 1. entropy — the honest floor
# --------------------------------------------------------------------------- #

def shannon_entropy_bits_per_byte(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def compression_floor(data: bytes) -> dict:
    """The best any lossless compressor could do is ~H bits/byte."""
    h = shannon_entropy_bits_per_byte(data)
    return {
        "size_bytes": len(data),
        "entropy_bits_per_byte": round(h, 4),
        "theoretical_floor_bytes": int(len(data) * h / 8),
        "theoretical_max_ratio": round(8 / h, 3) if h else 0.0,
    }


# --------------------------------------------------------------------------- #
# 2. general compressors
# --------------------------------------------------------------------------- #

def general_compressors(data: bytes) -> dict:
    out = {}
    for name, fn in [
        ("zlib-9", lambda d: zlib.compress(d, 9)),
        ("bz2-9", lambda d: bz2.compress(d, 9)),
        ("lzma-9", lambda d: lzma.compress(d, preset=9 | lzma.PRESET_EXTREME)),
    ]:
        c = fn(data)
        out[name] = {
            "compressed_bytes": len(c),
            "ratio": round(len(data) / len(c), 3),
            "saved_pct": round(100 * (1 - len(c) / len(data)), 1),
        }
    return out


# --------------------------------------------------------------------------- #
# 3. dedup + delta — store the surprise
# --------------------------------------------------------------------------- #

def dedup_delta(texts: list[str]) -> dict:
    """Model memory as a stream of lines. Store each line once (dedup); for
    repeats store a back-reference (delta). This is how memory really shrinks:
    the second telling of a fact costs almost nothing."""
    raw = "\n".join(texts).encode()
    seen: dict[str, int] = {}
    refs = 0
    novel_lines = []
    for line in raw.split(b"\n"):
        h = hashlib.sha1(line).hexdigest()
        if h in seen:
            refs += 1
        else:
            seen[h] = len(novel_lines)
            novel_lines.append(line)
    deduped = b"\n".join(novel_lines)
    # a real encoder would then compress the deduped stream
    deduped_c = lzma.compress(deduped, preset=9)
    return {
        "lines": len(raw.split(b"\n")),
        "duplicate_lines": refs,
        "dedup_ratio": round(len(raw) / max(len(deduped), 1), 3),
        "dedup_then_lzma_bytes": len(deduped_c),
        "dedup_then_lzma_ratio": round(len(raw) / max(len(deduped_c), 1), 3),
    }


# --------------------------------------------------------------------------- #
# 4. neural-latent storage
# --------------------------------------------------------------------------- #

def latent_storage(texts: list[str], embed, dims: int = 768, quant_bits: int = 8) -> dict:
    """Store each memory as a quantized latent vector instead of text.

    Honest caveat: this is LOSSY and often *larger* than text for small corpora —
    the win appears at scale, where you store meaning not prose and reconstruct
    with a decoder. We measure it so we can be truthful about the trade.
    """
    raw = "\n".join(texts).encode()
    total_bits = 0
    for t in texts:
        v = embed(t)
        # quantize each float to `quant_bits`
        total_bits += len(v) * quant_bits
    latent_bytes = total_bits // 8
    return {
        "raw_text_bytes": len(raw),
        "memories": len(texts),
        "dims": dims,
        "quant_bits": quant_bits,
        "latent_bytes": latent_bytes,
        "ratio_vs_text": round(len(raw) / max(latent_bytes, 1), 3),
        "note": "lossy; meaning-only, needs a decoder to reconstruct prose",
    }


# --------------------------------------------------------------------------- #
# 5. the "charge levels" ceiling — why 2GB->12GB is bounded
# --------------------------------------------------------------------------- #

def charge_levels(bits_per_cell: int, cells_gb: float = 2.0) -> dict:
    """The flash-NAND analogy: a cell can hold N distinguishable levels.

    SLC=1 bit, MLC=2, TLC=3, QLC=4. More levels = more bits per cell, but the
    read margin shrinks with noise, so it does not go to infinity.
    """
    capacity_gb = cells_gb * bits_per_cell  # if a 2GB-of-SLC-equivalent area
    return {
        "bits_per_cell": bits_per_cell,
        "levels_per_cell": 2 ** bits_per_cell,
        "effective_gb_for_2gb_slc_area": round(capacity_gb, 1),
        "note": "more levels → smaller read margin; noise-limited, not infinite",
    }


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def collect_text(data_dir: Path) -> list[str]:
    files = sorted(data_dir.rglob("*.md")) if data_dir.is_dir() else [data_dir]
    return [f.read_text(errors="ignore") for f in files]


def report(path: str | Path, embed=None) -> dict:
    p = Path(path).expanduser()
    texts = collect_text(p) if p.is_dir() else [p.read_text(errors="ignore")]
    raw = "\n".join(texts).encode()
    result = {
        "source": str(p),
        "files": len(texts),
        "raw_bytes": len(raw),
        "raw_human": f"{len(raw)/1024:.1f} KB",
    }
    result["floor"] = compression_floor(raw)
    result["compressors"] = general_compressors(raw)
    result["dedup_delta"] = dedup_delta(texts)
    if embed is not None:
        result["latent"] = latent_storage(texts, embed)
    result["charge_levels"] = {str(b): charge_levels(b) for b in (1, 2, 3, 4)}
    return result


def print_report(r: dict) -> None:
    print("=" * 66)
    print(f"COMPRESSION LAB — {r['source']}")
    print(f"  {r['files']} files · {r['raw_human']} ({r['raw_bytes']:,} bytes)")
    print("=" * 66)
    f = r["floor"]
    print("\n[1] ENTROPY FLOOR (what is possible from the data itself)")
    print(f"    entropy            : {f['entropy_bits_per_byte']} bits/byte")
    print(f"    theoretical floor  : {f['theoretical_floor_bytes']:,} bytes")
    print(f"    max possible ratio : {f['theoretical_max_ratio']}:1")
    print("\n[2] GENERAL COMPRESSORS (honest baseline)")
    for name, s in r["compressors"].items():
        print(f"    {name:8s}: {s['compressed_bytes']:>8,} B  ratio {s['ratio']:>5}:1  saved {s['saved_pct']}%")
    print("\n[3] DEDUP + DELTA (store the surprise, not the repeat)")
    d = r["dedup_delta"]
    print(f"    duplicate lines    : {d['duplicate_lines']} / {d['lines']}")
    print(f"    dedup ratio        : {d['dedup_ratio']}:1")
    print(f"    dedup+lzma ratio   : {d['dedup_then_lzma_ratio']}:1")
    if "latent" in r:
        print("\n[4] NEURAL-LATENT STORAGE (meaning, not prose)")
        la = r["latent"]
        print(f"    {la['memories']} memories × {la['dims']}d × {la['quant_bits']}-bit")
        print(f"    latent bytes       : {la['latent_bytes']:,}")
        print(f"    ratio vs text      : {la['ratio_vs_text']}:1  (lossy)")
        print(f"    note                : {la['note']}")
    print("\n[5] CHARGE LEVELS (the flash-NAND analogy)")
    for b, c in r["charge_levels"].items():
        print(f"    {b} bit/cell ({c['levels_per_cell']:>2} levels): "
              f"a 2GB area → {c['effective_gb_for_2gb_slc_area']} GB")
    print("\n" + "=" * 66)


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print_report(report(target))
