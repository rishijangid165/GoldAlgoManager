"""Run the gold setup backtests and write research/backtest/results/."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow `python research/backtest/run_backtest.py` from the repo root.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from research.backtest import config as C
from research.backtest.features import build_exec_frame
from research.backtest.engine import run_engine
from research.backtest.metrics import format_summary_row, slice_table, summarize, trades_frame
from research.backtest.setups import COMBO_ALL, COMBO_CORE, SETUP_NAMES, make_signal_fn


VARIANTS = [
    # (label, setup, trend_filter, nfp_filter, strict)
    *[(f"{name}|no_filter", name, False, False, False) for name in SETUP_NAMES],
    *[(f"{name}|trend_ma", name, True, False, False) for name in SETUP_NAMES],
    *[(f"{name}|trend_strict", name, True, False, True) for name in SETUP_NAMES],
    ("combo_core|trend_ma", "combo_core", True, False, False),
    ("combo_all|trend_ma", "combo_all", True, False, False),
    # Sensitivity: first-Friday NFP blackout on the a-priori core book.
    ("combo_core|trend_ma+nfp", "combo_core", True, True, False),
]


def _warmup_mask(df: pd.DataFrame) -> pd.Series:
    return df["d_sma200"].notna() & df["h4_sma50"].notna() & df["atr_sl"].notna()


def run_variant(df: pd.DataFrame, setup: str, trend_filter: bool, nfp_filter: bool, strict: bool):
    fn = make_signal_fn(setup, trend_filter=trend_filter, strict=strict)
    trades, equity = run_engine(
        df,
        fn,
        trend_filter=trend_filter,
        nfp_filter=nfp_filter,
        daily_loss_stop=True,
        start_equity=C.START_EQUITY,
        setup_name=setup,
    )
    tdf = trades_frame(trades)
    summary = summarize(tdf, equity)
    return tdf, equity, summary


def plot_equity(curves: dict[str, pd.Series], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name, series in curves.items():
        ax.plot(series.index, series.values, label=name, linewidth=1.2)
    ax.axhline(C.START_EQUITY, color="grey", linewidth=0.8, linestyle="--")
    ax.set_title(title)
    ax.set_ylabel("Equity (USD)")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> int:
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    C.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    frames = {}
    meta = {
        "run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start_equity": C.START_EQUITY,
        "risk_pct": C.RISK_PCT,
        "spread": C.SPREAD,
        "slippage": C.SLIPPAGE,
        "tp1_r": C.TP1_R,
        "tp2_r": C.TP2_R,
        "sessions": "Asia 18:00–03:00 ET, London 03:00–08:00 ET, NY 08:00–17:00 ET",
        "data": {},
        "timeframes": {},
    }

    all_summaries = []
    session_rows = []
    direction_rows = []

    for tf in ("1h", "15m"):
        print(f"building {tf} frame...", flush=True)
        df = build_exec_frame(tf)
        ready = df.loc[_warmup_mask(df)].copy()
        frames[tf] = ready
        # Persist a slim processed file for audit (not every helper column).
        keep = [c for c in ready.columns if c in {
            "Open", "High", "Low", "Close", "Volume", "session", "session_date",
            "prior_high", "prior_low", "asia_high", "asia_low", "atr", "rsi",
            "atr_sl", "trend_down_ma", "trend_up_ma", "trend_down_strict",
            "trend_up_strict", "d_sma50", "d_sma200", "h4_sma50", "nfp_blackout",
            "asia_first_close_up", "asia_first_close_down",
        }]
        ready[keep].to_csv(C.PROCESSED_DIR / f"GC=F_{tf}_features.csv")
        meta["timeframes"][tf] = {
            "bars_raw": int(len(df)),
            "bars_ready": int(len(ready)),
            "start": str(ready.index.min()),
            "end": str(ready.index.max()),
        }
        print(
            f"  {tf}: {len(ready)} ready bars  {ready.index.min()} -> {ready.index.max()}",
            flush=True,
        )

        # 15m is a short robustness window: still run every variant, clearly labeled.
        for label, setup, trend_filter, nfp_filter, strict in VARIANTS:
            vlabel = f"{tf}|{label}"
            print(f"  running {vlabel}...", flush=True)
            tdf, equity, summary = run_variant(ready, setup, trend_filter, nfp_filter, strict)
            row = format_summary_row(vlabel, summary)
            row.update({"tf": tf, "setup": setup, "trend_filter": trend_filter,
                        "nfp_filter": nfp_filter, "strict": strict})
            all_summaries.append(row)
            if not tdf.empty:
                tdf.insert(0, "variant", vlabel)
                tdf.to_csv(C.RESULTS_DIR / f"trades_{vlabel.replace('|', '_')}.csv", index=False)
                for rec in slice_table(tdf, "session").to_dict(orient="records"):
                    rec["variant"] = vlabel
                    session_rows.append(rec)
                for rec in slice_table(tdf, "direction").to_dict(orient="records"):
                    rec["variant"] = vlabel
                    direction_rows.append(rec)
            equity.to_csv(C.RESULTS_DIR / f"equity_{vlabel.replace('|', '_')}.csv")
            print(
                f"    n={summary['n']}  wr={summary['win_rate']}  "
                f"avgR={summary['avg_r']}  PF={summary['profit_factor']}  "
                f"net={summary['net_pnl']}  DDpct={summary['max_dd_pct']}",
                flush=True,
            )

    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_csv(C.RESULTS_DIR / "metrics_summary.csv", index=False)
    if session_rows:
        pd.DataFrame(session_rows).to_csv(C.RESULTS_DIR / "metrics_by_session.csv", index=False)
    if direction_rows:
        pd.DataFrame(direction_rows).to_csv(C.RESULTS_DIR / "metrics_by_direction.csv", index=False)

    # Equity plots: 1h main variants (no_filter vs trend_ma per setup) and combos.
    h1 = frames["1h"]
    for setup in SETUP_NAMES:
        curves = {}
        for filt, tag in ((False, "no_filter"), (True, "trend_ma")):
            label = f"1h|{setup}|{tag}"
            path = C.RESULTS_DIR / f"equity_{label.replace('|', '_')}.csv"
            if path.exists():
                eq = pd.read_csv(path, parse_dates=["Datetime"], index_col="Datetime")
                curves[f"{setup} {tag}"] = eq["equity"]
        if curves:
            plot_equity(curves, C.FIGURES_DIR / f"equity_1h_{setup}.png",
                        f"GC=F 1h — {setup} (start ${C.START_EQUITY:,.0f})")
    combo_curves = {}
    for label in ("combo_core|trend_ma", "combo_all|trend_ma", "combo_core|trend_ma+nfp"):
        path = C.RESULTS_DIR / f"equity_1h_{label.replace('|', '_')}.csv"
        if path.exists():
            eq = pd.read_csv(path, parse_dates=["Datetime"], index_col="Datetime")
            combo_curves[label] = eq["equity"]
    if combo_curves:
        plot_equity(combo_curves, C.FIGURES_DIR / "equity_1h_combos.png",
                    "GC=F 1h — combo books")

    (C.RESULTS_DIR / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("wrote", C.RESULTS_DIR / "metrics_summary.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
