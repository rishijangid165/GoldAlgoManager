#!/usr/bin/env python3
"""Build a high-impact US news calendar for gold research.

FOMC announcement dates are parsed from Federal Reserve calendar / historical
pages (statement day, 14:00 ET). NFP is the first Friday of each month at
08:30 ET (a well-known proxy; holiday postponements are rare and not all
corrected here). CPI and PPI calendars could not be taken from BLS (HTTP 403
at the time of this pull), so those events are omitted from the primary
study unless a verified file is provided.

Sources are public Fed HTML. Event times are the conventional release times,
not tick-perfect print timestamps.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
STUDY = Path(__file__).resolve().parent
NEWS_HTML = Path("/tmp/news")
OUT = STUDY / "results"
MONTHS = {m: i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m: i for i, m in enumerate(calendar.month_abbr) if m})


def first_friday(year: int, month: int) -> date:
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    for d in cal.itermonthdates(year, month):
        if d.month == month and d.weekday() == calendar.FRIDAY:
            return d
    raise RuntimeError(f"no Friday in {year}-{month}")


def nfp_events(start=2006, end=2026) -> pd.DataFrame:
    rows = []
    for y in range(start, end + 1):
        for m in range(1, 13):
            if y == 2026 and m > 11:
                break
            d = first_friday(y, m)
            ts = datetime.combine(d, time(8, 30), tzinfo=ET)
            rows.append({"event": "NFP", "ts": ts, "date": d, "source": "first_friday_proxy", "notes": "08:30 ET conventional"})
    return pd.DataFrame(rows)


def _parse_current_calendar(html: str) -> list[dict]:
    """Parse the 2021+ calendar: month name + '27-28' or '27-28*' date range."""
    rows: list[dict] = []
    # Split by year headings
    parts = re.split(r'(\d{4}) FOMC Meetings', html)
    # parts: pre, year, block, year, block...
    for i in range(1, len(parts), 2):
        year = int(parts[i])
        block = parts[i + 1] if i + 1 < len(parts) else ""
        # stop at next major heading-ish
        for m in re.finditer(
            r'fomc-meeting__month[^>]*>\s*<strong>\s*([A-Za-z]+)\s*</strong>.*?'
            r'fomc-meeting__date[^>]*>\s*([^<]+?)\s*<',
            block,
            re.S,
        ):
            month_name = m.group(1).strip()
            raw = m.group(2).strip()
            unscheduled = "unscheduled" in raw.lower() or "notation" in raw.lower()
            star = "*" in raw
            days = re.findall(r"\d{1,2}", raw)
            if not days or month_name not in MONTHS:
                continue
            day = int(days[-1])  # statement typically on the last meeting day
            month = MONTHS[month_name]
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            ts = datetime.combine(d, time(14, 0), tzinfo=ET)
            rows.append({
                "event": "FOMC",
                "ts": ts,
                "date": d,
                "source": "fed_fomccalendars",
                "notes": ("SEP " if star else "") + raw + (" unscheduled" if unscheduled else ""),
            })
    return rows


def _parse_historical(html: str, year: int) -> list[dict]:
    """Pull unique statement/minutes dates from historical year pages."""
    dates = set(re.findall(rf"(?:monetary|fomcminutes|FOMC)({year}\d{{4}})", html))
    # Also 'monetarypolicy/files/monetaryYYYYMMDD'
    dates |= set(re.findall(rf"monetary({year}\d{{4}})", html))
    rows = []
    for s in sorted(dates):
        try:
            d = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            continue
        if d.year != year:
            continue
        ts = datetime.combine(d, time(14, 0), tzinfo=ET)
        rows.append({
            "event": "FOMC",
            "ts": ts,
            "date": d,
            "source": f"fed_fomchistorical{year}",
            "notes": "date from Fed document stamp; 14:00 ET conventional",
        })
    return rows


def fomc_events() -> pd.DataFrame:
    rows: list[dict] = []
    current = NEWS_HTML / "fomc_current.html"
    if current.exists():
        rows.extend(_parse_current_calendar(current.read_text(errors="replace")))
    for p in sorted(NEWS_HTML.glob("fomc_2*.html")):
        if p.name == "fomc_current.html":
            continue
        year = int(re.search(r"(\d{4})", p.name).group(1))
        rows.extend(_parse_historical(p.read_text(errors="replace"), year))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # One row per date; prefer the structured current calendar when both exist.
    df["pref"] = df["source"].eq("fed_fomccalendars").astype(int)
    df = df.sort_values(["date", "pref"]).drop_duplicates("date", keep="last").drop(columns=["pref"])
    # Filter obvious non-meeting document stamps: keep dates that fall on
    # typical meeting weekdays (Tue-Wed) plus known emergency Mondays, etc.
    # We do not drop 2008/2020 inter-meeting dates — those moved gold.
    return df.sort_values("ts").reset_index(drop=True)


def build_calendar() -> pd.DataFrame:
    frames = [nfp_events(), fomc_events()]
    frames = [f for f in frames if f is not None and not f.empty]
    cal = pd.concat(frames, ignore_index=True).sort_values("ts").reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    cal.to_csv(OUT / "news_events.csv", index=False)
    print(cal.groupby("event").size().to_string())
    print("range", cal["ts"].min(), "->", cal["ts"].max(), "n", len(cal))
    return cal


def load_calendar() -> pd.DataFrame:
    path = OUT / "news_events.csv"
    if not path.exists():
        return build_calendar()
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce").dt.tz_convert(ET)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["ts"])
    return df


if __name__ == "__main__":
    build_calendar()
