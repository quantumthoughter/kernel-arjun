#!/usr/bin/env python3
"""TRANSFORMER ON DISK — how a neural network is stored, dissected live.

Reads a real GGUF model from your Ollama store and shows:
  I.   the container: magic, version, a metadata table, a tensor index
  II.  what a tensor IS: a big 2-D grid of numbers (weights)
  III. the SAME māyā as the flash cell: numbers are stored as bytes,
       bytes are voltages, and 4-bit "Q4_0" packs them tighter
  IV.  where the intelligence lives: the numbers, not the code

    python transformer_disk.py [path-to-gguf]
"""
from __future__ import annotations

import glob
import os
import struct
import sys

GGML = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 8: "Q8_0", 14: "Q6_K",
        12: "Q4_K", 13: "Q5_K", 15: "Q8_K"}
TYPE_BITS = {"F32": 32, "F16": 16, "Q8_0": 8.5, "Q6_K": 6.5625,
             "Q5_K": 5.5, "Q4_K": 4.5, "Q4_0": 4.5, "Q4_1": 5.0}


def find_gguf(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    for b in sorted(glob.glob(os.path.expanduser("~/.ollama/models/blobs/sha256-*"))):
        try:
            if open(b, "rb").read(4) == b"GGUF":
                return b
        except OSError:
            continue
    return None


class Reader:
    def __init__(self, f):
        self.f = f

    def u32(self):
        return struct.unpack("<I", self.f.read(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.f.read(8))[0]

    def string(self):
        n = self.u64()
        return self.f.read(n).decode("utf-8", "replace")

    def value(self, t):
        simple = {8: self.string, 4: self.u32,
                  10: self.u64,
                  6: lambda: struct.unpack("<f", self.f.read(4))[0],
                  7: lambda: bool(self.f.read(1)[0]),
                  0: lambda: struct.unpack("<B", self.f.read(1))[0],
                  1: lambda: struct.unpack("<b", self.f.read(1))[0]}
        if t in simple:
            return simple[t]()
        if t == 9:  # array
            at = self.u32()
            ln = self.u64()
            if at == 8:
                return [self.string() for _ in range(ln)]
            sz = {4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 0: 1, 1: 1}.get(at, 4)
            self.f.read(sz * ln)
            return f"[{ln} values]"
        raise ValueError(f"unknown kv type {t}")


def dissect(path: str) -> dict:
    r = Reader(open(path, "rb"))
    magic = r.f.read(4).decode()
    version = r.u32()
    n_tensors = r.u64()
    n_kv = r.u64()
    kv = {}
    for _ in range(n_kv):
        k = r.string()
        t = r.u32()
        kv[k] = r.value(t)
    tensors = []
    for _ in range(n_tensors):
        name = r.string()
        nd = r.u32()
        dims = [r.u64() for _ in range(nd)]
        tt = r.u32()
        off = r.u64()
        tensors.append((name, dims, GGML.get(tt, str(tt))))
    return {"magic": magic, "version": version, "n_tensors": n_tensors,
            "n_kv": n_kv, "metadata": kv, "tensors": tensors,
            "size_bytes": os.path.getsize(path), "path": path}


def n_params(dims):
    n = 1
    for d in dims:
        n *= d
    return n


def report(info: dict) -> None:
    print("=" * 74)
    print(f"TRANSFORMER ON DISK — {os.path.basename(info['path'])}")
    print(f"  {info['size_bytes']/1e9:.2f} GB · {info['n_tensors']} tensors · "
          f"{info['n_kv']} metadata keys · GGUF v{info['version']}")
    print("=" * 74)

    print("\n[I] THE CONTAINER — magic, metadata table, tensor index")
    print(f"    magic: {info['magic']} (a self-describing format, like VĀK)")
    for k in ("general.architecture", "general.name", "general.file_type"):
        if k in info["metadata"]:
            print(f"    {k:34s} = {info['metadata'][k]}")

    # total parameters
    total = sum(n_params(d) for _, d, _ in info["tensors"])
    print(f"\n    total parameters: {total:,}  (≈ {total/1e9:.2f} B)")

    print("\n[II] WHAT A TENSOR IS — one row of the index")
    print(f"    {'name':46s} {'shape':>16s} {'type':>6s} {'#numbers':>14s}")
    for name, dims, tt in info["tensors"][:8]:
        print(f"    {name:46s} {str(dims):>16s} {tt:>6s} {n_params(dims):>14,}")

    # quantisation summary
    print("\n[III] THE SAME MĀYĀ — numbers stored as bytes (quantized)")
    from collections import Counter
    by_type = Counter(tt for _, _, tt in info["tensors"])
    print(f"    {'type':>6s} {'count':>6s} {'bits/number':>12s}  meaning")
    meaning = {
        "F32": "32-bit float — full precision",
        "F16": "16-bit float — half precision",
        "Q8_0": "8-bit — good quality",
        "Q6_K": "6-bit — very good",
        "Q4_0": "4-bit — compact, slight loss",
        "Q4_K": "4-bit (K-quant) — best small quality",
    }
    for tt, c in by_type.most_common():
        print(f"    {tt:>6s} {c:>6} {TYPE_BITS.get(tt,'?'):>12}  {meaning.get(tt,'')}")

    # demonstrate a real 2x2 slice from the embedding table (the actual numbers)
    print("\n[IV] THE ACTUAL NUMBERS — a slice of the token embedding (Q4_0)")
    # find the embedding tensor's file offset by re-parsing quickly
    _show_embedding_slice(info["path"])

    print("\n" + "=" * 74)
    print("  A transformer on disk is: a big table of NUMBERS (weights) + a tiny")
    print("  schema. The 'intelligence' is the numbers. They are stored as bytes,")
    print("  bytes as voltages — the SAME māyā as the flash cell. Quantization")
    print("  (Q4_0) stores each number in ~4.5 bits instead of 32 — that is how a")
    print("  37 GB model becomes 4 GB: we round the weights and agree to forget.")
    print("=" * 74)


def _show_embedding_slice(path: str) -> None:
    """Find the first non-empty Q4_0 block in the embedding table and decode it."""
    # Q4_0: each block = 1 fp16 scale (delta) + 16 bytes (32 nibbles = 32 values)
    data_start = _tensor_data_offset(path, "token_embd.weight")
    with open(path, "rb") as f:
        f.seek(data_start)
        buf = f.read(18 * 4000)  # scan the first 4000 blocks (72 KB)
    chosen = None
    for b in range(len(buf) // 18):
        blk = buf[b * 18:(b + 1) * 18]
        delta = struct.unpack("<e", blk[:2])[0]
        if abs(delta) > 1e-6:            # skip zero padding rows
            chosen = (b, delta, blk[2:])
            break
    if not chosen:
        print("    (all-zero head of the table — empty rows)")
        return
    b, delta, qs = chosen
    vals = []
    for i in range(8):
        vals.append((qs[i] & 0x0F) - 8)
        vals.append((qs[i] >> 4) - 8)
    weights = [round(v * delta, 6) for v in vals]
    print(f"    first non-empty block : #{b}")
    print(f"    block scale (fp16)    : {delta:.6f}")
    print(f"    4-bit codes (nibbles) : {[qs[i] & 0xF for i in range(8)]}")
    print(f"    decoded weights       : {weights}")
    print("    each 4-bit nibble is one weight: (nibble - 8) × scale")
    print("    32 weights packed into 18 bytes (2 scale + 16 data).")
    print("    A raw F32 version of these same 32 numbers would take 128 bytes.")


def _tensor_data_offset(path: str, want: str) -> int:
    r = Reader(open(path, "rb"))
    r.f.read(4)
    r.u32()
    n_tensors = r.u64()
    n_kv = r.u64()
    for _ in range(n_kv):
        r.string()
        t = r.u32()
        r.value(t)
    # after the index comes the alignment padding; find where data begins
    entries = []
    for _ in range(n_tensors):
        name = r.string()
        nd = r.u32()
        dims = [r.u64() for _ in range(nd)]
        tt = r.u32()
        off = r.u64()
        entries.append((name, off))
    # GGUF aligns tensor data to 32 bytes typically
    header_end = r.f.tell()
    align = 32
    data_start = (header_end + align - 1) // align * align
    offs = dict(entries)
    return data_start + offs[want]


def main() -> None:
    path = find_gguf(sys.argv[1] if len(sys.argv) > 1 else None)
    if not path:
        print("no GGUF model found (is Ollama installed with a model?)")
        return
    report(dissect(path))


if __name__ == "__main__":
    main()
