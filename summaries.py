"""Rule-based weekly fun-summary generator.

Turns the day-by-day numbers into a witty paragraph per week: who leads, who's
charging, who's bleeding, plus a one-line zinger. No LLM required at runtime,
so summaries are instant and deterministic. The tone is luxury-sports-banter,
in keeping with the Rolex/Porsche styling.
"""

import datetime as dt
import random

import analytics


def _iso_week(date_str):
    d = dt.date.fromisoformat(date_str)
    y, w, _ = d.isocalendar()
    return y, w


LEADER_LINES = [
    "{name} is wearing the yellow jersey, {ticker} doing the heavy lifting at {ret:+.1f}%.",
    "Top of the pile: {name}. {ticker} just won't quit ({ret:+.1f}%).",
    "{name} leads the pack — {ticker} up {ret:+.1f}% and still cruising.",
    "Pole position belongs to {name}; {ticker} sitting pretty at {ret:+.1f}%.",
]
CLIMBER_LINES = [
    "{name} is the mover of the week, vaulting {jump} place(s) up the board.",
    "Watch out — {name} climbed {jump} spot(s) and smells blood.",
    "{name} found another gear, up {jump} place(s) since last week.",
]
LOSER_LINES = [
    "Spare a thought for {name}: {ticker} is the week's anchor at {ret:+.1f}%.",
    "{name} is having a moment to forget — {ticker} languishing at {ret:+.1f}%.",
    "Someone check on {name}. {ticker} down at {ret:+.1f}% and the grand prize is drifting away.",
]
RISK_LINES = [
    "Volatility crown goes to {name} — {ticker} swinging like a pendulum.",
    "{name} is on the white-knuckle ride this week; {ticker} is anything but boring.",
    "{name} clearly doesn't believe in sleep — {ticker} is the wildest car on the grid.",
]
QUIET_LINES = [
    "A quiet week on the index — the pack is bunched and nobody blinked.",
    "Not much daylight between the contenders; the real fireworks are still ahead.",
    "A holding-pattern week. Fortunes are made in the waiting.",
]


def _standings_at(data, day_index):
    """Return list of (name, ticker, return_pct, color, photo) sorted desc at a day index."""
    out = []
    for c in data["competitors"]:
        series = c["return_series"]
        val = None
        # walk back to last non-null at/under day_index
        for i in range(min(day_index, len(series) - 1), -1, -1):
            if series[i] is not None:
                val = series[i]
                break
        out.append({
            "name": c["name"], "ticker": c["ticker"], "color": c["color"],
            "photo": c["photo"], "ret": val if val is not None else 0.0,
        })
    out.sort(key=lambda x: x["ret"], reverse=True)
    return out


def weekly_summaries(quarter_id):
    data = analytics.compute_quarter(quarter_id)
    if not data or not data["has_data"] or not data["competitors"]:
        return []

    dates = data["dates"]
    # Map each ISO week to the index of its last available trading day.
    week_last_index = {}
    week_dates = {}
    for i, d in enumerate(dates):
        wk = _iso_week(d)
        week_last_index[wk] = i
        week_dates.setdefault(wk, []).append(d)

    ordered_weeks = sorted(week_last_index.keys())
    rng = random.Random(quarter_id * 7919)

    summaries = []
    prev_rank = {}
    for wk in ordered_weeks:
        idx = week_last_index[wk]
        board = _standings_at(data, idx)
        if not board:
            continue
        rank_now = {b["name"]: r for r, b in enumerate(board, start=1)}

        leader = board[0]
        loser = board[-1]
        spread = leader["ret"] - loser["ret"]

        # biggest climber vs previous week
        climber, jump = None, 0
        if prev_rank:
            for b in board:
                if b["name"] in prev_rank:
                    delta = prev_rank[b["name"]] - rank_now[b["name"]]
                    if delta > jump:
                        jump, climber = delta, b

        # riskiest this week = widest intra-week swing
        riskiest, swing = None, 0.0
        start_idx = max(0, idx - len(week_dates[wk]) + 1)
        for c in data["competitors"]:
            seg = [v for v in c["return_series"][start_idx:idx + 1] if v is not None]
            if len(seg) >= 2:
                s = max(seg) - min(seg)
                if s > swing:
                    swing, riskiest = s, c

        parts = []
        parts.append(rng.choice(LEADER_LINES).format(
            name=leader["name"], ticker=leader["ticker"], ret=leader["ret"]))
        if climber and jump >= 1:
            parts.append(rng.choice(CLIMBER_LINES).format(name=climber["name"], jump=jump))
        if spread < 5 and len(board) > 1:
            parts.append(rng.choice(QUIET_LINES))
        if len(board) > 1:
            parts.append(rng.choice(LOSER_LINES).format(
                name=loser["name"], ticker=loser["ticker"], ret=loser["ret"]))
        if riskiest and swing > 8:
            parts.append(rng.choice(RISK_LINES).format(
                name=riskiest["name"], ticker=riskiest["ticker"]))

        days = week_dates[wk]
        label = f"Week {wk[1]}, {wk[0]}"
        summaries.append({
            "week_label": label,
            "date_range": f"{days[0]} → {days[-1]}",
            "narrative": " ".join(parts),
            "leader": leader,
            "loser": loser if len(board) > 1 else None,
            "spread": round(spread, 1),
        })
        prev_rank = rank_now

    summaries.reverse()  # newest first
    return summaries
