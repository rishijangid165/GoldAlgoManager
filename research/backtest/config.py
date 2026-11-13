"""Shared parameters for the gold discretionary-style backtests.

Prices are COMEX GC=F futures (typically a few dollars above broker spot).
Sessions follow the COMEX day used in the daily notes: Asia 18:00–03:00 ET,
London 03:00–08:00 ET, New York 08:00–17:00 ET. Daily break 17:00–18:00 ET.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"

TZ = "America/New_York"

# --- costs and risk (dollars per ounce for spread/slippage) ---
SPREAD = 0.25
SLIPPAGE = 0.10  # applied on each fill, in addition to half-spread
RISK_PCT = 0.005
DAILY_LOSS_STOP = 0.02
START_EQUITY = 100_000.0
CONTRACT_OZ = 100.0  # 1.00 lot = 100 oz; $1 move ≈ $100 P&L per lot
MIN_LOT = 0.01
LOT_STEP = 0.01

TP1_R = 1.5
TP2_R = 3.0
TP1_FRACTION = 0.5  # close half at TP1, move stop to breakeven (entry)

# --- indicators ---
ATR_N = 14
RSI_N = 14
SMA_FAST = 50
SMA_SLOW = 200
SWING_N_1H = 3
SWING_N_4H = 2
SWING_N_D = 2

# --- stops / zones ---
SL_BUFFER_ATR = 0.15  # ATR(1h) beyond structure
MIN_SL = 5.0  # dollars; skip tighter stops (noise vs spread)
MAX_SL_ATR_1H = 3.0
ZONE_INSIDE_ATR = 0.40
ZONE_OUTSIDE_ATR = 0.20
REJECTION_BODY_SIDE = 0.40  # close must be in the favourable 40% of the bar
REJECTION_WICK_FRAC = 0.45
MIN_REJECTION_ATR = 0.35
SWEEP_MIN_EXCESS = 0.50  # dollars beyond the swept level
SWEEP_CLOSE_INSIDE = 0.20  # dollars back inside the level

# --- sessions (America/New_York clock, DST-safe) ---
# Asia starts at 18:00 ET the prior calendar day and ends 03:00 ET.
ASIA_START_HOUR = 18
ASIA_END_HOUR = 3
LONDON_START_HOUR = 3
LONDON_END_HOUR = 8
NY_START_HOUR = 8
NY_END_HOUR = 17
# Do not chase Asia breakouts after this ET hour (late-NY noise).
BREAKOUT_ENTRY_UNTIL_HOUR = 13

# First-Friday NFP approximation only (12:30–15:00 ET). Not a full calendar.
NFP_BLACKOUT_START_HOUR = 12
NFP_BLACKOUT_END_HOUR = 15
