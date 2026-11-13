"""Event-driven backtest engine: 0.5% risk, one trade at a time, TP1/BE/TP2.

Look-ahead is avoided by:
- signalling only at a completed bar's close,
- entering at the next bar's open (plus spread and slippage),
- sizing and placing targets from the actual fill,
- using only that bar's OHLC path to manage stops, with a conservative
  same-bar rule (stop before target if both are touched).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from . import config as C

SignalFn = Callable[[pd.Series], "Signal | None"]


@dataclass
class Signal:
    setup: str
    direction: int  # +1 buy, -1 sell
    sl: float  # structural stop, before costs
    reason: str
    next_level: float | None = None  # optional structure target


@dataclass
class Fill:
    time: pd.Timestamp
    price: float
    lots: float
    reason: str


@dataclass
class Trade:
    setup: str
    direction: int
    reason: str
    session: str
    session_date: object
    entry_time: pd.Timestamp
    entry: float
    sl_initial: float
    tp1: float
    tp2: float
    lots: float
    risk_dollars: float
    trend_filter: bool
    trend_down: bool
    trend_up: bool
    sl: float = 0.0
    remaining: float = 0.0
    tp1_done: bool = False
    fills: list[Fill] = field(default_factory=list)
    pnl: float = 0.0
    r_multiple: float = 0.0
    exit_time: pd.Timestamp | None = None
    exit_reason: str = ""
    mae_r: float = 0.0
    mfe_r: float = 0.0
    open: bool = True

    def to_row(self) -> dict:
        return {
            "setup": self.setup,
            "direction": "BUY" if self.direction == 1 else "SELL",
            "reason": self.reason,
            "session": self.session,
            "session_date": str(self.session_date),
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry": round(self.entry, 3),
            "sl_initial": round(self.sl_initial, 3),
            "tp1": round(self.tp1, 3),
            "tp2": round(self.tp2, 3),
            "lots": self.lots,
            "risk_dollars": round(self.risk_dollars, 2),
            "pnl": round(self.pnl, 2),
            "r_multiple": round(self.r_multiple, 4),
            "exit_reason": self.exit_reason,
            "tp1_hit": self.tp1_done,
            "mae_r": round(self.mae_r, 4),
            "mfe_r": round(self.mfe_r, 4),
            "trend_filter": self.trend_filter,
            "trend_down": self.trend_down,
            "trend_up": self.trend_up,
        }


def half_spread() -> float:
    return C.SPREAD / 2.0


def buy_fill(mid: float) -> float:
    return mid + half_spread() + C.SLIPPAGE


def sell_fill(mid: float) -> float:
    return mid - half_spread() - C.SLIPPAGE


def exit_fill(direction: int, mid: float) -> float:
    # Flattening a long is a sell; flattening a short is a buy.
    return sell_fill(mid) if direction == 1 else buy_fill(mid)


def round_lot(lots: float) -> float:
    steps = np.floor(lots / C.LOT_STEP + 1e-12)
    return max(0.0, float(steps * C.LOT_STEP))


def size_lots(equity: float, sl_distance: float) -> float:
    if sl_distance <= 0:
        return 0.0
    risk = equity * C.RISK_PCT
    raw = risk / (sl_distance * C.CONTRACT_OZ)
    lots = round_lot(raw)
    return lots if lots >= C.MIN_LOT else 0.0


def _pnl(direction: int, entry: float, exit_price: float, lots: float) -> float:
    return direction * (exit_price - entry) * lots * C.CONTRACT_OZ


class Engine:
    def __init__(
        self,
        df: pd.DataFrame,
        signal_fn: SignalFn,
        trend_filter: bool = False,
        nfp_filter: bool = False,
        daily_loss_stop: bool = True,
        start_equity: float = C.START_EQUITY,
        setup_name: str = "",
    ):
        self.df = df
        self.signal_fn = signal_fn
        self.trend_filter = trend_filter
        self.nfp_filter = nfp_filter
        self.daily_loss_stop = daily_loss_stop
        self.start_equity = start_equity
        self.setup_name = setup_name

    def run(self) -> tuple[list[Trade], pd.DataFrame]:
        df = self.df
        n = len(df)
        equity = self.start_equity
        trades: list[Trade] = []
        pos: Trade | None = None
        pending: Signal | None = None
        # Per-session realized P&L and start-of-session equity for the 2% stop.
        sess_start_eq = equity
        sess_realized = 0.0
        last_session = None
        eq_times = []
        eq_vals = []

        idx = df.index

        for i in range(n):
            row = df.iloc[i]
            t = idx[i]
            sess = row["session_date"]
            if last_session is None or sess != last_session:
                sess_start_eq = equity
                sess_realized = 0.0
                last_session = sess

            # --- manage existing position through this bar (incl. open gap) ---
            if pos is not None:
                self._manage(pos, row, t, equity)
                if not pos.open:
                    equity += pos.pnl
                    sess_realized += pos.pnl
                    trades.append(pos)
                    pos = None

            # --- enter at this open if a signal was pending from the prior close ---
            if pos is None and pending is not None:
                blocked = False
                if self.nfp_filter and bool(row.get("nfp_blackout", False)):
                    blocked = True
                if self.daily_loss_stop and sess_realized <= -C.DAILY_LOSS_STOP * sess_start_eq:
                    blocked = True
                if str(row.get("session", "")) == "break":
                    blocked = True
                if not blocked:
                    pos = self._try_enter(pending, row, t, equity)
                pending = None
                if pos is not None:
                    # The entry bar can also hit SL/TP.
                    self._manage(pos, row, t, equity, entry_bar=True)
                    if not pos.open:
                        equity += pos.pnl
                        sess_realized += pos.pnl
                        trades.append(pos)
                        pos = None

            # --- mark-to-market equity at close ---
            mtm = equity
            if pos is not None:
                mtm += _pnl(pos.direction, pos.entry, float(row["Close"]), pos.remaining)
                if pos.tp1_done:
                    # already realized half at TP1
                    mtm += pos.pnl
            eq_times.append(t)
            eq_vals.append(mtm)

            # --- signal at close only when flat ---
            if pos is None and pending is None:
                pending = self.signal_fn(row)

        if pos is not None:
            # Force a mid close on the last completed bar (no look-ahead).
            last = df.iloc[-1]
            t = idx[-1]
            px = exit_fill(pos.direction, float(last["Close"]))
            self._close(pos, t, px, pos.remaining, "eod_flat")
            equity += pos.pnl
            trades.append(pos)

        eq = pd.DataFrame({"equity": eq_vals}, index=pd.DatetimeIndex(eq_times, name="Datetime"))
        return trades, eq

    def _try_enter(self, sig: Signal, row: pd.Series, t: pd.Timestamp, equity: float) -> Trade | None:
        mid = float(row["Open"])
        fill = buy_fill(mid) if sig.direction == 1 else sell_fill(mid)
        # Skip if the open already gapped through the stop.
        if sig.direction == 1 and fill <= sig.sl:
            return None
        if sig.direction == -1 and fill >= sig.sl:
            return None
        sl_dist = abs(fill - sig.sl)
        if sl_dist < C.MIN_SL:
            return None
        lots = size_lots(equity, sl_dist)
        if lots <= 0:
            return None
        risk = sl_dist * lots * C.CONTRACT_OZ
        tp1 = fill + sig.direction * C.TP1_R * sl_dist
        tp2 = fill + sig.direction * C.TP2_R * sl_dist
        if sig.next_level is not None and np.isfinite(sig.next_level):
            lvl = float(sig.next_level)
            # Only pull TP2 in if the level is beyond 1.5R and closer than 3R.
            dist = sig.direction * (lvl - fill)
            if C.TP1_R * sl_dist < dist < C.TP2_R * sl_dist:
                tp2 = lvl
        trade = Trade(
            setup=sig.setup or self.setup_name,
            direction=sig.direction,
            reason=sig.reason,
            session=str(row.get("session", "")),
            session_date=row.get("session_date", ""),
            entry_time=t,
            entry=fill,
            sl_initial=sig.sl,
            sl=sig.sl,
            tp1=tp1,
            tp2=tp2,
            lots=lots,
            remaining=lots,
            risk_dollars=risk,
            trend_filter=self.trend_filter,
            trend_down=bool(row.get("trend_down_ma", False)),
            trend_up=bool(row.get("trend_up_ma", False)),
        )
        return trade

    def _manage(self, pos: Trade, row: pd.Series, t: pd.Timestamp, equity: float, entry_bar: bool = False) -> None:
        o, h, l, c = (float(row[k]) for k in ("Open", "High", "Low", "Close"))
        d = pos.direction

        # Gap through levels at the open (not used on the entry bar — fill is the open).
        if not entry_bar:
            hit_sl = (d == 1 and o <= pos.sl) or (d == -1 and o >= pos.sl)
            hit_tp2 = (d == 1 and o >= pos.tp2) or (d == -1 and o <= pos.tp2)
            hit_tp1 = (not pos.tp1_done) and ((d == 1 and o >= pos.tp1) or (d == -1 and o <= pos.tp1))
            if hit_sl:
                self._close(pos, t, exit_fill(d, o), pos.remaining, "sl_gap")
                return
            if hit_tp2:
                if not pos.tp1_done:
                    # Gapped through both targets: split the fill as TP1 then TP2.
                    self._take_tp1(pos, t, exit_fill(d, o))
                self._close(pos, t, exit_fill(d, o), pos.remaining, "tp2_gap")
                return
            if hit_tp1:
                self._take_tp1(pos, t, exit_fill(d, o))
                # After TP1, a gap through BE (now sl) is possible only if open is
                # back on the other side, which cannot hold if we also gapped to TP1.

        # Favourable / adverse extremes from the high/low.
        if d == 1:
            adverse, favourable = l, h
        else:
            adverse, favourable = h, l

        # Track MAE / MFE in R from mid prices (no costs).
        r = pos.risk_dollars / (pos.lots * C.CONTRACT_OZ) if pos.lots else np.nan
        if r and r > 0:
            pos.mae_r = max(pos.mae_r, max(0.0, d * (pos.entry - adverse) / r))
            pos.mfe_r = max(pos.mfe_r, max(0.0, d * (favourable - pos.entry) / r))

        sl_touch = (d == 1 and l <= pos.sl) or (d == -1 and h >= pos.sl)
        tp2_touch = (d == 1 and h >= pos.tp2) or (d == -1 and l <= pos.tp2)
        tp1_touch = (not pos.tp1_done) and ((d == 1 and h >= pos.tp1) or (d == -1 and l <= pos.tp1))

        # Conservative same-bar rule: if the stop and a target are both
        # inside the bar, assume the stop is hit first on the remaining size.
        if sl_touch and (tp1_touch or tp2_touch):
            self._close(pos, t, exit_fill(d, pos.sl), pos.remaining, "sl_samebar")
            return
        if sl_touch and not tp1_touch and not tp2_touch:
            self._close(pos, t, exit_fill(d, pos.sl), pos.remaining, "sl")
            return
        if tp1_touch:
            self._take_tp1(pos, t, exit_fill(d, pos.tp1))
            # Same bar can also finish the runner at TP2, or at BE if we
            # traded back through entry. Conservative: if the adverse extreme
            # touched BE, stop the runner there.
            be = pos.sl  # already moved to entry
            be_touch = (d == 1 and l <= be) or (d == -1 and h >= be)
            if be_touch and tp2_touch:
                self._close(pos, t, exit_fill(d, be), pos.remaining, "be_samebar")
                return
            if be_touch:
                self._close(pos, t, exit_fill(d, be), pos.remaining, "be")
                return
            if tp2_touch:
                self._close(pos, t, exit_fill(d, pos.tp2), pos.remaining, "tp2")
                return
            return
        if tp2_touch:
            # tp1 already done on a prior bar
            self._close(pos, t, exit_fill(d, pos.tp2), pos.remaining, "tp2")

    def _take_tp1(self, pos: Trade, t: pd.Timestamp, price: float) -> None:
        close_lots = round_lot(pos.lots * C.TP1_FRACTION)
        if close_lots <= 0:
            close_lots = C.MIN_LOT
        if close_lots >= pos.remaining:
            close_lots = pos.remaining
        realized = _pnl(pos.direction, pos.entry, price, close_lots)
        pos.pnl += realized
        pos.remaining = round(pos.remaining - close_lots, 8)
        pos.tp1_done = True
        pos.sl = pos.entry  # breakeven, no extra buffer
        pos.fills.append(Fill(t, price, close_lots, "tp1"))
        if pos.remaining <= 1e-8:
            pos.remaining = 0.0
            pos.open = False
            pos.exit_time = t
            pos.exit_reason = "tp1_all"
            pos.r_multiple = pos.pnl / pos.risk_dollars if pos.risk_dollars else 0.0

    def _close(self, pos: Trade, t: pd.Timestamp, price: float, lots: float, reason: str) -> None:
        if lots > 0:
            pos.pnl += _pnl(pos.direction, pos.entry, price, lots)
            pos.fills.append(Fill(t, price, lots, reason))
            pos.remaining = max(0.0, pos.remaining - lots)
        pos.open = False
        pos.exit_time = t
        pos.exit_reason = reason if not pos.tp1_done else f"tp1+{reason}"
        pos.r_multiple = pos.pnl / pos.risk_dollars if pos.risk_dollars else 0.0


def run_engine(df: pd.DataFrame, signal_fn: SignalFn, **kwargs) -> tuple[list[Trade], pd.DataFrame]:
    return Engine(df, signal_fn, **kwargs).run()
