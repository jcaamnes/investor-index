"""Analytics engine for the Stocks Elite.

Given a quarter, reconstructs the full day-by-day performance and ranking
timeline from cached price history and derives every leaderboard number, risk
metric, streak and "fun fact" award the dashboard shows.

Everything is computed on the fly from price_history, so no snapshots need to
be stored: the daily ranking timeline is rebuilt each call.
"""

import datetime as dt
import json
import math
import os
import statistics

import db

TRADING_DAYS = 252

# All-time marathon history extracted from "Stocks maratontabell.xlsx".
# Covers 2017 Q4 → 2026 Q1; the live database carries the seasons after that.
HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "history.json")


def load_history():
    """Return the marathon history dict, or None if the file is missing."""
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _pct(a, b):
    return (a / b - 1.0) * 100.0 if b else 0.0


def _series_map(symbol, start, end):
    rows = db.get_prices(symbol, start, end)
    smap = {r["date"]: r["close"] for r in rows}
    synth = any(r["is_synthetic"] for r in rows)
    real_dates = [r["date"] for r in rows if not r["is_synthetic"]]
    return smap, synth, real_dates


def _forward_fill(date_list, value_by_date):
    """Return list aligned to date_list, carrying last known value forward."""
    out = []
    last = None
    for d in date_list:
        if d in value_by_date:
            last = value_by_date[d]
        out.append(last)
    return out


def _max_drawdown(return_pct_series):
    """Max drawdown on the equity curve implied by a % return series."""
    peak = -math.inf
    mdd = 0.0
    for r in return_pct_series:
        if r is None:
            continue
        equity = 1.0 + r / 100.0
        peak = max(peak, equity)
        if peak > 0:
            dd = (equity - peak) / peak * 100.0
            mdd = min(mdd, dd)
    return mdd  # negative number, e.g. -23.4


def _daily_simple_returns(closes):
    rets = []
    prev = None
    for c in closes:
        if c is not None and prev is not None and prev != 0:
            rets.append((c - prev) / prev)
        prev = c if c is not None else prev
    return rets


def compute_quarter(quarter_id):
    quarter = db.get_quarter(quarter_id)
    if not quarter:
        return None
    start, end = quarter["start_date"], quarter["end_date"]
    today = dt.date.today().isoformat()
    end = min(end, today)

    positions = db.list_positions(quarter_id)
    if not positions:
        return {"quarter": quarter, "investors": [], "dates": [], "has_data": False}

    # Collect every date that appears across all symbols.
    all_dates = set()
    real_date_set = set()
    raw = {}
    any_synth = False
    for p in positions:
        smap, synth, real_dates = _series_map(p["yahoo_symbol"], start, end)
        raw[p["id"]] = smap
        any_synth = any_synth or synth
        all_dates.update(smap.keys())
        real_date_set.update(real_dates)
    dates = sorted(all_dates)
    has_data = len(dates) > 0
    # Latest real (non-synthetic) Yahoo close date — what the dashboard is "as of".
    as_of = max(real_date_set) if real_date_set else None

    # Build per-investor enriched records.
    records = []
    for p in positions:
        closes = _forward_fill(dates, raw[p["id"]]) if dates else []
        buy = p["buy_price"]
        ret_series = [(_pct(c, buy) if c is not None else None) for c in closes]
        valid = [r for r in ret_series if r is not None]
        current = valid[-1] if valid else 0.0

        simple = _daily_simple_returns(closes)
        vol_daily = statistics.pstdev(simple) if len(simple) > 1 else 0.0
        vol_annual = vol_daily * math.sqrt(TRADING_DAYS) * 100.0
        mean_daily = statistics.fmean(simple) if simple else 0.0
        sharpe = (mean_daily / vol_daily * math.sqrt(TRADING_DAYS)) if vol_daily else 0.0
        mdd = _max_drawdown(ret_series)

        best_day = max(simple) * 100.0 if simple else 0.0
        worst_day = min(simple) * 100.0 if simple else 0.0
        peak = max(valid) if valid else 0.0
        trough = min(valid) if valid else 0.0
        comeback = (current - trough) if valid else 0.0  # gain since worst point

        records.append({
            "investor_id": p["investor_id"],
            "position_id": p["id"],
            "name": p["name"],
            "tagline": p["tagline"],
            "photo": p["photo"],
            "color": p["color"],
            "ticker": p["ticker"],
            "yahoo_symbol": p["yahoo_symbol"],
            "buy_price": buy,
            "currency": p["currency"],
            "is_benchmark": p["is_benchmark"],
            "last_close": next((c for c in reversed(closes) if c is not None), None),
            "return_pct": round(current, 2),
            "return_series": [None if r is None else round(r, 2) for r in ret_series],
            "volatility": round(vol_annual, 1),
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(mdd, 1),
            "best_day": round(best_day, 2),
            "worst_day": round(worst_day, 2),
            "peak_return": round(peak, 2),
            "trough_return": round(trough, 2),
            "comeback": round(comeback, 2),
        })

    # ---- Daily ranking timeline (competitors only) ----------------------
    competitors = [r for r in records if not r["is_benchmark"]]
    rank_history = {r["investor_id"]: [] for r in competitors}
    days_at_top = {r["investor_id"]: 0 for r in competitors}
    leader_by_day = []

    for di in range(len(dates)):
        snapshot = []
        for r in competitors:
            val = r["return_series"][di]
            snapshot.append((r["investor_id"], val if val is not None else -math.inf))
        snapshot.sort(key=lambda x: x[1], reverse=True)
        for rank, (iid, _) in enumerate(snapshot, start=1):
            rank_history[iid].append(rank)
        if snapshot:
            top_id = snapshot[0][0]
            days_at_top[top_id] += 1
            leader_by_day.append(top_id)

    # Rank momentum over the trailing 7 trading days.
    for r in competitors:
        hist = rank_history[r["investor_id"]]
        if len(hist) >= 2:
            window = min(7, len(hist) - 1)
            r["rank_change_7d"] = hist[-1 - window] - hist[-1]  # positive = climbed
        else:
            r["rank_change_7d"] = 0
        r["days_at_top"] = days_at_top[r["investor_id"]]
        r["current_rank"] = hist[-1] if hist else None
        # current win streak: consecutive trailing days ranked #1
        streak = 0
        for rk in reversed(hist):
            if rk == 1:
                streak += 1
            else:
                break
        r["lead_streak"] = streak

    # Sort competitors by current return for the leaderboard.
    competitors.sort(key=lambda r: r["return_pct"], reverse=True)
    leader_return = competitors[0]["return_pct"] if competitors else 0.0
    for i, r in enumerate(competitors, start=1):
        r["rank"] = i
        r["gap_to_leader"] = round(r["return_pct"] - leader_return, 2)

    benchmarks = [r for r in records if r["is_benchmark"]]

    awards = _awards(competitors)

    return {
        "quarter": quarter,
        "dates": dates,
        "has_data": has_data,
        "is_synthetic": any_synth,
        "as_of": as_of,
        "competitors": competitors,
        "benchmarks": benchmarks,
        "all_records": competitors + benchmarks,
        "leader_by_day": leader_by_day,
        "awards": awards,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }


def _awards(competitors):
    """Pick the fun-fact title holders. Returns dict of award -> record summary."""
    if not competitors:
        return {}

    def winner(key, reverse=True, label=None):
        pool = [c for c in competitors if c.get(key) is not None]
        if not pool:
            return None
        best = sorted(pool, key=lambda c: c[key], reverse=reverse)[0]
        return {
            "name": best["name"], "photo": best["photo"], "ticker": best["ticker"],
            "color": best["color"], "value": best[key],
        }

    return {
        "leader":        winner("return_pct", reverse=True),
        "biggest_loser": winner("return_pct", reverse=False),
        "most_risky":    winner("volatility", reverse=True),
        "steadiest":     winner("volatility", reverse=False),
        "best_risk_adj": winner("sharpe", reverse=True),
        "deepest_dip":   winner("max_drawdown", reverse=False),
        "best_single_day": winner("best_day", reverse=True),
        "worst_single_day": winner("worst_day", reverse=False),
        "comeback_king": winner("comeback", reverse=True),
        "most_days_at_top": winner("days_at_top", reverse=True),
        "biggest_climber": winner("rank_change_7d", reverse=True),
    }


def _canonical_quarter(label):
    """Normalise a quarter label to 'YYYY QN'. Accepts 'Q2 2026' or '2026 Q2'."""
    if not label:
        return label
    parts = label.replace("·", " ").split()
    year = next((p for p in parts if p.isdigit() and len(p) == 4), None)
    qtr = next((p for p in parts if p.upper().startswith("Q") and p[1:].isdigit()), None)
    return f"{year} {qtr.upper()}" if year and qtr else label


# Some competitors have appeared under more than one name across the years
# (the marathon history uses one, the current competition another). Collapse
# those to a single canonical name so the Hall of Fame counts each person once.
NAME_ALIASES = {
    "Jan": "Jc",
    "Magnus": "Årøen",
    "Jakob": "Jack",
    "Nesstrum": "Ness",
}


def _canon_name(name):
    """Map a competitor name onto its canonical form (see NAME_ALIASES)."""
    return NAME_ALIASES.get(name, name)


def hall_of_fame():
    """Cross-quarter Hall of Fame.

    Built primarily from the all-time marathon history (2017 Q4 → 2026 Q1,
    loaded from data/history.json). Any live quarters in the database whose
    results aren't already recorded in that history are folded in on top, so the
    standings keep growing as new seasons are played.
    """
    history = load_history()

    # ---- Seed standings from the marathon history ----------------------
    standings = {}
    covered_quarters = set()
    if history:
        for h in history.get("standings", []):
            nm = _canon_name(h["name"])
            entries = h.get("entries", 0) or 0
            standings[nm] = {
                "name": nm, "photo": "", "color": "",
                "quarters": entries,
                "wins": h.get("gold", 0),
                "gold": h.get("gold", 0), "silver": h.get("silver", 0),
                "bronze": h.get("bronze", 0),
                "podiums": h.get("podiums", 0),
                "podium_pct": h.get("podium_pct"),
                "neg_quarters": h.get("neg_quarters", 0),
                "tot_return": h.get("tot_return"),
                "reinvest_5k": h.get("reinvest_5k"),
                # running sum of quarter returns (%) so we can extend the average
                "_sum": (h.get("avg_return", 0.0) or 0.0) * entries,
                "best": None, "worst": None,
            }
        covered_quarters = {_canonical_quarter(c["quarter"])
                            for c in history.get("champions", [])}

    top_quarters = [dict(e, name=_canon_name(e.get("name")))
                    for e in history.get("top_quarters", [])] if history else []
    worst_quarters = [dict(e, name=_canon_name(e.get("name")))
                      for e in history.get("worst_quarters", [])] if history else []

    best_quarter = top_quarters[0] if top_quarters else None
    worst_quarter = worst_quarters[0] if worst_quarters else None

    # ---- Fold in live DB quarters not already in the history -----------
    # Only completed quarters count toward the marathon, matching the Excel
    # (an in-progress quarter's standings still move, so it would distort the
    # all-time averages). A quarter is done once its end date has passed.
    today = dt.date.today().isoformat()
    live_extra = []
    for q in db.list_quarters():
        if _canonical_quarter(q["label"]) in covered_quarters:
            continue
        if q["end_date"] >= today:
            continue  # quarter still in progress
        data = compute_quarter(q["id"])
        if not data or not data["competitors"]:
            continue
        for c in data["competitors"]:
            cname = _canon_name(c["name"])
            s = standings.setdefault(cname, {
                "name": cname, "photo": c["photo"], "color": c["color"],
                "quarters": 0, "wins": 0, "gold": 0, "silver": 0, "bronze": 0,
                "podiums": 0, "podium_pct": None, "neg_quarters": 0,
                "tot_return": None, "reinvest_5k": None,
                "_sum": 0.0, "best": None, "worst": None,
            })
            if not s.get("photo") and c.get("photo"):
                s["photo"] = c["photo"]
            if not s.get("color") and c.get("color"):
                s["color"] = c["color"]
            s["quarters"] += 1
            s["_sum"] += c["return_pct"]
            if c["return_pct"] < 0:
                s["neg_quarters"] += 1
            if c["rank"] == 1:
                s["wins"] += 1
                s["gold"] += 1
            elif c["rank"] == 2:
                s["silver"] += 1
            elif c["rank"] == 3:
                s["bronze"] += 1
            if c["rank"] <= 3:
                s["podiums"] += 1
            cur = s["best"]
            s["best"] = c["return_pct"] if cur is None else max(cur, c["return_pct"])
            cur = s["worst"]
            s["worst"] = c["return_pct"] if cur is None else min(cur, c["return_pct"])

            entry = {"name": cname, "ticker": c["ticker"],
                     "quarter": _canonical_quarter(q["label"]),
                     "return_pct": c["return_pct"], "photo": c["photo"]}
            live_extra.append(entry)
            if best_quarter is None or c["return_pct"] > best_quarter["return_pct"]:
                best_quarter = entry
            if worst_quarter is None or c["return_pct"] < worst_quarter["return_pct"]:
                worst_quarter = entry

    # Merge any live records into the top/worst leaderboards and re-rank.
    if live_extra:
        top_quarters = sorted(top_quarters + live_extra,
                              key=lambda e: e["return_pct"], reverse=True)[:10]
        worst_quarters = sorted(worst_quarters + live_extra,
                               key=lambda e: e["return_pct"])[:10]
        for i, e in enumerate(top_quarters, 1):
            e["rank"] = i
        for i, e in enumerate(worst_quarters, 1):
            e["rank"] = i
    else:
        top_quarters = top_quarters[:10]
        worst_quarters = worst_quarters[:10]

    # ---- Backfill photos/colors from the current roster ----------------
    # Standings names seeded from history.json carry no photo, and live photos
    # only attach once a quarter completes. Map any current investor's photo by
    # name so an image added in the admin shows up immediately everywhere.
    roster = {_canon_name(inv["name"]): inv for inv in db.list_investors()}
    for s in standings.values():
        inv = roster.get(s["name"])
        if inv:
            if inv.get("photo"):
                s["photo"] = inv["photo"]
            if inv.get("color"):
                s["color"] = inv["color"]
    for e in top_quarters + worst_quarters:
        inv = roster.get(e.get("name"))
        if inv and inv.get("photo"):
            e["photo"] = inv["photo"]
    for e in (best_quarter, worst_quarter):
        if e:
            inv = roster.get(e.get("name"))
            if inv and inv.get("photo"):
                e["photo"] = inv["photo"]

    # ---- Finalise standings --------------------------------------------
    standings_list = []
    for s in standings.values():
        q = s["quarters"]
        s["avg"] = round(s["_sum"] / q, 2) if q else 0.0
        if s.get("podium_pct") is None and q:
            s["podium_pct"] = round(s["podiums"] / q * 100, 1)
        s["best"] = round(s["best"], 2) if s["best"] is not None else None
        s["worst"] = round(s["worst"], 2) if s["worst"] is not None else None
        s.pop("_sum", None)
        standings_list.append(s)
    # Olympic-style sort: gold, then silver, then bronze, then average return.
    standings_list.sort(
        key=lambda s: (s.get("gold", 0), s.get("silver", 0),
                       s.get("bronze", 0), s.get("avg", 0.0)),
        reverse=True)

    return {
        "best_quarter": best_quarter,
        "worst_quarter": worst_quarter,
        "standings": standings_list,
        "top_quarters": top_quarters,
        "worst_quarters": worst_quarters,
        "coverage": history.get("coverage") if history else None,
    }
