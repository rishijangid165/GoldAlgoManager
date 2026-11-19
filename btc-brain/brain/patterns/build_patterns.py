#!/usr/bin/env python3
"""Build brain/patterns/situations.csv.gz from 1H/4H candles + Fear & Greed history."""
from __future__ import annotations

import csv
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C


def resolve_candle_paths():
    h1p, h4p = C.local_candle_paths()
    if h1p and h4p:
        return h1p, h4p
    # fallback: unpack gzipped copies from this repo into /tmp
    import gzip as gz
    data = C.BTC_BRAIN / "data" / "advanced"
    tmp = Path("/tmp/btc-brain-patterns")
    tmp.mkdir(parents=True, exist_ok=True)
    for name in ("delta_1h.csv", "delta_4h.csv"):
        src = data / f"{name}.gz"
        if not src.exists():
            raise SystemExit(f"data nahi hai: missing {src} and uncompressed training CSVs")
        dest = tmp / name
        dest.write_bytes(gz.open(src, "rb").read())
    return tmp / "delta_1h.csv", tmp / "delta_4h.csv"


def main():
    h1p, h4p = resolve_candle_paths()
    print(f"loading {h1p} and {h4p}")
    h1 = C.load_candle_csv(h1p)
    h4 = C.load_candle_csv(h4p)
    print(f"1H bars={len(h1)}  4H bars={len(h4)}")
    series = C.compute_series(h1, h4)

    print("fetching Fear & Greed history (api.alternative.me)...")
    fng = C.fetch_fng(limit=0)
    fng_ok = bool(fng)
    if fng_ok:
        C.save_fng_cache(fng)
        print(f"F&G days={len(fng)}  {fng[0]['date']} -> {fng[-1]['date']}")
    else:
        cached = C.load_fng_cache()
        if cached:
            fng = cached
            fng_ok = True
            print(f"F&G live fetch failed; using cache days={len(fng)}")
        else:
            fng = []
            print("F&G: data nahi hai (fetch failed, no cache)")

    rows = []
    skipped = 0
    for j in range(len(h1)):
        feat = C.bar_features(h1, h4, series, j)
        fwd = C.forward_outcomes(h1, j, 24)
        if feat is None or fwd is None:
            skipped += 1
            continue
        # Join F&G by UTC date of the candle close
        utc_date = C.time.strftime("%Y-%m-%d", C.time.gmtime(feat["t_close"]))
        fg = C.fng_on_date(fng, utc_date) if fng else None
        rec = {
            "t": feat["t"],
            "ist": feat["ist"],
            "date_ist": feat["date_ist"],
            "hour_ist": feat["hour_ist"],
            "dow": feat["dow"],
            "regime": feat["regime"],
            "ret_24h": f"{feat['ret_24h']:.6f}",
            "dist_ema50_atr": f"{feat['dist_ema50_atr']:.4f}",
            "atr_pct": f"{feat['atr_pct']:.4f}",
            "vol_ratio": f"{feat['vol_ratio']:.4f}",
            "fng": fg["value"] if fg else "data nahi hai",
            "fng_class": fg["cls"] if fg else "data nahi hai",
            "fwd_ret_4h": f"{fwd['fwd_ret_4h']:.6f}",
            "fwd_ret_24h": f"{fwd['fwd_ret_24h']:.6f}",
            "fwd_max_up_24h": f"{fwd['fwd_max_up_24h']:.6f}",
            "fwd_max_down_24h": f"{fwd['fwd_max_down_24h']:.6f}",
            "close": f"{feat['close']:.2f}",
        }
        rows.append(rec)

    C.SITUATIONS_GZ.parent.mkdir(parents=True, exist_ok=True)
    raw = C.SITUATIONS_GZ.with_suffix("")  # situations.csv
    # with_suffix('') on situations.csv.gz -> situations.csv  ? 
    # Path('situations.csv.gz').with_suffix('') -> 'situations.csv'  YES if suffix is .gz
    # actually .with_suffix('') replaces .gz with empty, leaving situations.csv. Good.
    with open(raw, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=C.SIT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(raw, "rb") as fin, gzip.open(C.SITUATIONS_GZ, "wb", compresslevel=9) as fout:
        fout.write(fin.read())
    raw.unlink(missing_ok=True)

    # regime counts
    from collections import Counter
    rc = Counter(r["regime"] for r in rows)
    fg_n = sum(1 for r in rows if r["fng"] != "data nahi hai")
    print(f"wrote {C.SITUATIONS_GZ}  rows={len(rows)}  skipped={skipped}")
    print("regime counts:", dict(rc))
    print(f"F&G joined on {fg_n}/{len(rows)} rows ({'ok' if fng_ok else 'data nahi hai'})")
    if rows:
        print(f"range {rows[0]['ist']} -> {rows[-1]['ist']} IST")


if __name__ == "__main__":
    main()
