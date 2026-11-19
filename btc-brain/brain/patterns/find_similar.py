#!/usr/bin/env python3
"""Find the 10 most similar past 1H situations to the current (live) market.

This is history, not a prediction. Always read the sample size.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C


def current_features_or_error():
    feat, tick, err = C.live_features()
    if err:
        return None, tick, err
    fg = C.fng_latest(C.load_fng_cache())
    if fg:
        feat["fng"] = fg["value"]
        feat["fng_class"] = fg["cls"]
    else:
        feat["fng"] = None
        feat["fng_class"] = "data nahi hai"
    return feat, tick, None


def run(k=10):
    lines = []
    feat, tick, err = current_features_or_error()
    if err:
        lines.append(f"Live features: {err}")
        lines.append("Ye history hai, prediction nahi. Similar search skipped.")
        return lines, None
    px = tick["price"] if tick else feat.get("close")
    fg = feat.get("fng")
    fg_s = f"{fg} {feat.get('fng_class')}" if fg is not None else "data nahi hai"
    lines.append(
        f"Now (last completed 1H {feat['ist']} IST close {feat['close']:.1f}; "
        f"ticker {px if px else 'data nahi hai'}): "
        f"regime={feat['regime']} F&G={fg_s} ret24h={feat['ret_24h']*100:+.2f}% "
        f"distEMA50={feat['dist_ema50_atr']:+.2f}ATR ATRpct={feat['atr_pct']*100:.0f} "
        f"vol={feat['vol_ratio']:.2f}x hour={feat['hour_ist']} dow={feat['dow']}"
    )
    situations = C.load_situations()
    top, meta = C.similar_to(feat, situations, k=k)
    lines.extend(C.summarize_similar(top, meta))
    return lines, feat


def main():
    lines, _ = run()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
