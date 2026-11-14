# Proposals from the 2026-11-15 weekend study (owner decision needed)

None of these is in the playbook yet. Items P1 and P2 change the **live EA's behaviour**: they are input changes only, with no recompile. Under the read-only rule for this study, nothing was changed on the terminal. P3–P5 are research items for the next pre-registered round.

## P1. EA trailing after TP1: switch off, so live matches the tested exit (recommended)

- **Why.** Every adopted setup was tested with "TP1 1.5R half off → stop to entry → runner to TP2 (3R or next level)". GoldAIBridge v1.03.1 instead trails the runner, from the 1.02 inputs: `InpTrailEnabled=true`, M15 swing or 1×ATR, whichever is tighter. On the same trades:

  | Setup | ΔR (OOS 2012–2026) | Note |
  |---|---|---|
  | NY London-range break | −0.051R | one-sided p of harm 0.031 |
  | Donchian-20 long | −0.044R | |
  | Asia + D+4H | −0.022R | |
  | FOMC | +0.104R | not significant after correction |

- **Change.** In the GoldAIBridge inputs/preset, set `InpTrailEnabled = false`. Nothing else changes.
- **Alternative (not tested as a rule, so not recommended yet).** Trail only FOMC trades. That would need a per-setup flag in the EA and a pre-registered test.

## P2. Friday auto-close: keep it on, but accept the cost (information)

- **Keep as-is.** `InpFridayCloseEnabled=true`, `InpFridayNoEntryMinutes=120`.
- **What it does to each setup.** With the Friday close:
  - FOMC improves (PF 2.05, 13/15 green years).
  - Donchian still passes (PF 1.88, DD 2.0%). It re-enters on Sunday only if a fresh signal is there.
  - NY and Asia drop to about 0R in 2012–2023.
- **The trade-off.** Turning it off would raise NY/Asia back to the "M1-managed" numbers, but brings weekend gap risk back. Since NY is now on probation and Asia is qualified, keeping the Friday close is the safer default. Decision for the owner.

## P3. Watchlist candidates for the next pre-registered round (do not trade)

| ID | Idea | Why it is interesting | Why it is not adopted |
|---|---|---|---|
| F10 | Donchian long, skip when D-ATR(14) is above its 80th percentile over 252 sessions | OOS +0.43R, PF 1.87, 11/15 green, 2012–23 +0.22R, backcast +0.42R | Holm: p 0.011 > 0.0036; only 61 trades |
| X3/FOMC | FOMC continuation with a chandelier exit (no partial, no TP, 3×H1 ATR trail after +1R) | +0.29R per trade over baseline, 13/15 green | Holm: p 0.010 > 0.0042; 68 trades |
| X3/Asia | Asia + D+4H with a chandelier exit | Book passes the bar (PF 1.46, 11/15, 2012–23 +0.20R) | Holm: p 0.060; base rule itself fails |
| F5 | First break of the prior-session H/L at 08:00–11:00 ET with D+4H | Passes the bar (PF 1.45) | p 0.083; about 5 trades a year |
| F2 | CPI continuation after 30 minutes | 2012–23 +0.28R | Negative 2024–26 and negative backcast. Likely dead |
| D1 | Asia-session long drift | +0.034% a session, both periods positive | Descriptive only; mostly 2024–26 |

Next round:
- Test these as a **new, small family** (at most 5) on data that arrives after 2026-11-15. Use the forward paper book, plus a second broker's history if one is available.
- **Do not** re-test them on 2012–2026; that would be data-dredging.

## P4. Decision-check routine prompt (text change for the parent to apply)

Replace the NY London-range line in the routine's setup list with:

> NY London-range break (playbook §5) is on **probation** since 2026-11-15: still publish it when its exact rules trigger, label it "probation" in the decision note, and never loosen its filters. FOMC continuation (§6) and Donchian-20 long (§7) remain adopted. Asia breakout (§4) stays qualified. The EA flattens GoldAI trades about 16:15 ET Friday, so do not publish a new zone after 14:15 ET Friday.

## P5. Paper tracker

No change is needed. The four tracked books (`ny_lon_brk_d4h`, `fomc_cont`, `donch20_long`, `asia_brk_trend`) are unchanged.

Optional: add a "Friday-close" variant column, so the forward record reflects the live EA. Not done this weekend, to keep the tracker's history stable.
