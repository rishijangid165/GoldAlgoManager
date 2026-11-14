"""Read MetaTrader 5 `.hcc` M1 history files (the terminal's own downloaded broker history).

Read-only: files are copied out of the terminal's Bases folder first; the terminal
itself is never touched. Layout as observed on MetaQuotes-Demo XAUUSD (header magic 502):
  * index from byte 228: 18-byte entries (u32 id, u32 update time, u16 ?, u32 chunk size,
    u32 absolute chunk offset), one per trading day
  * each chunk: a u16 header length (129) + header, then N x 60-byte MqlRates records
    (i64 time, 4 x f64 OHLC, i64 tick_volume, i32 spread, i64 real_volume)
  * the first record of a chunk can be a daily summary; it is dropped when it is not
    strictly before the next bar or carries >= 90% of the chunk's tick volume.
Times are broker server wall-clock (MetaQuotes-Demo: ET+7). Adapted from the public decoder
at forge.mql5.io (Ozzman45/Warrior_EA research/hcc.py) and checked against copy_rates output.
"""
from __future__ import annotations

import glob
import os
import struct

import numpy as np

REC = np.dtype([("t", "<i8"), ("o", "<f8"), ("h", "<f8"), ("l", "<f8"), ("c", "<f8"),
                ("tv", "<i8"), ("sp", "<i4"), ("rv", "<i8")])
assert REC.itemsize == 60


def read_hcc(path: str) -> np.ndarray:
    b = open(path, "rb").read()
    chunks = []
    k = 0
    while 228 + 18 * (k + 1) <= len(b):
        _, _, _, size, off = struct.unpack_from("<IIHII", b, 228 + 18 * k)
        if off < 228 or off + size > len(b) or size < 129:
            break
        hdr = struct.unpack_from("<H", b, off)[0]
        body = size - hdr
        if 60 <= hdr <= 400 and body > 0 and body % 60 == 0:
            a = np.frombuffer(b, REC, body // 60, off + hdr).copy()
            if len(a) > 1 and (a["tv"][0] >= 0.9 * a["tv"][1:].sum() or a["t"][0] >= a["t"][1]):
                a = a[1:]
            chunks.append(a)
        k += 1
    if not chunks:
        return np.zeros(0, REC)
    a = np.concatenate(chunks)
    a = a[np.argsort(a["t"], kind="stable")]
    return a[np.concatenate([[True], np.diff(a["t"]) > 0])]


def load_m1(folder: str) -> np.ndarray:
    files = sorted(glob.glob(os.path.join(folder, "*.hcc")))
    a = np.concatenate([read_hcc(f) for f in files])
    a = a[np.argsort(a["t"], kind="stable")]
    return a[np.concatenate([[True], np.diff(a["t"]) > 0])]
