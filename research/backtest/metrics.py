"""Trade-level metrics: overall, by session, by direction."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .engine import Trade


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame([t.to_row() for t in trades])
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    return df


def _max_drawdown(equity: pd.Series) -> tuple[float, float]:
    if equity.empty:
        return 0.0, 0.0
    peak = equity.cummax()
    dd = equity - peak
    dd_pct = dd / peak.replace(0, np.nan)
    return float(dd.min()), float(dd_pct.min())


def summarize(trades: list[Trade] | pd.DataFrame, equity: pd.DataFrame | None = None) -> dict:
    df = trades if isinstance(trades, pd.DataFrame) else trades_frame(trades)
    empty = {
        "n": 0,
        "wins": 0,
        "losses": 0,
        "scratches": 0,
        "win_rate": np.nan,
        "avg_r": np.nan,
        "median_r": np.nan,
        "expectancy_r": np.nan,
        "expectancy_usd": np.nan,
        "profit_factor": np.nan,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "net_pnl": 0.0,
        "avg_win_r": np.nan,
        "avg_loss_r": np.nan,
        "tp1_hit_rate": np.nan,
        "tp2_rate": np.nan,
        "max_dd_usd": np.nan,
        "max_dd_pct": np.nan,
        "end_equity": np.nan,
        "avg_hold_hours": np.nan,
    }
    if df is None or df.empty:
        if equity is not None and not equity.empty:
            empty["end_equity"] = float(equity["equity"].iloc[-1])
            dd, dd_pct = _max_drawdown(equity["equity"])
            empty["max_dd_usd"] = round(dd, 2)
            empty["max_dd_pct"] = round(dd_pct * 100, 2)
        return empty

    r = df["r_multiple"].astype(float)
    pnl = df["pnl"].astype(float)
    wins = r > 1e-6
    losses = r < -1e-6
    scratches = ~wins & ~losses
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    hold = pd.NaT
    if "entry_time" in df.columns and "exit_time" in df.columns:
        hold = (df["exit_time"] - df["entry_time"]) / pd.Timedelta(hours=1)

    out = {
        "n": int(len(df)),
        "wins": int(wins.sum()),
        "losses": int(losses.sum()),
        "scratches": int(scratches.sum()),
        "win_rate": round(float(wins.mean()) * 100, 2) if len(df) else np.nan,
        "avg_r": round(float(r.mean()), 4),
        "median_r": round(float(r.median()), 4),
        "expectancy_r": round(float(r.mean()), 4),
        "expectancy_usd": round(float(pnl.mean()), 2),
        "profit_factor": round(gp / gl, 3) if gl > 0 else (np.inf if gp > 0 else np.nan),
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "net_pnl": round(float(pnl.sum()), 2),
        "avg_win_r": round(float(r[wins].mean()), 4) if wins.any() else np.nan,
        "avg_loss_r": round(float(r[losses].mean()), 4) if losses.any() else np.nan,
        "tp1_hit_rate": round(float(df["tp1_hit"].mean()) * 100, 2) if "tp1_hit" in df.columns else np.nan,
        "tp2_rate": round(float(df["exit_reason"].astype(str).str.contains("tp2").mean()) * 100, 2),
        "avg_hold_hours": round(float(hold.mean()), 2) if hold is not pd.NaT else np.nan,
    }
    if equity is not None and not equity.empty:
        dd, dd_pct = _max_drawdown(equity["equity"])
        out["max_dd_usd"] = round(dd, 2)
        out["max_dd_pct"] = round(dd_pct * 100, 2)
        out["end_equity"] = round(float(equity["equity"].iloc[-1]), 2)
    else:
        # Fallback: trade-close equity path only (no open-trade MTM).
        curve = 100_000.0 + pnl.cumsum()
        # This path is less honest; only used if no equity curve is passed.
        peak = curve.cummax()
        dd = float((curve - peak).min())
        out["max_dd_usd"] = round(dd, 2)
        out["max_dd_pct"] = round(float((curve - peak).min() / peak.max() * 100), 2) if len(curve) else np.nan
        out["end_equity"] = round(float(curve.iloc[-1]), 2)
    return out


def slice_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df is None or df.empty or col not in df.columns:
        return pd.DataFrame()
    rows = []
    for key, part in df.groupby(col):
        s = summarize(part)
        s[col] = key
        rows.append(s)
    return pd.DataFrame(rows)


def format_summary_row(label: str, s: dict) -> dict:
    row = {"variant": label}
    row.update(s)
    return row
