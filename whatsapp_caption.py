"""Short, punchy one-liner generator for the WhatsApp caption.

Distinct from summaries.py's on-site weekly paragraph (a longer narrative
keyed to ISO weeks): this produces a single fun sentence, rebuilt fresh from
the live /api/dashboard payload every time push_gui.py posts an update, so it
always matches the numbers in the attached screenshot. No LLM at runtime —
plain rule-based templates, same spirit as summaries.py.
"""

import random

LEADER_LINES = [
    "{name} leads the pack at {ret:+.1f}% — {ticker} doing the heavy lifting.",
    "Still {name} out front: {ticker} sitting at {ret:+.1f}%.",
    "{name} holds top spot, {ticker} up {ret:+.1f}%.",
    "Pole position: {name}, {ticker} at {ret:+.1f}%.",
]
TIGHT_LINES = [
    "It's tight up top — only {gap:.1f}pp separates 1st and 2nd.",
    "{name2} is breathing down the leader's neck, {gap:.1f}pp behind.",
]
CLIMBER_LINES = [
    "Mover of the moment: {name}, up {jump} place(s) this week.",
    "{name} is climbing fast — {jump} spot(s) gained since last week.",
]
STREAK_LINES = [
    "{name} has now held #1 for {streak} straight trading days.",
    "{streak} days and counting at the top for {name}.",
]
LOSER_LINES = [
    "Spare a thought for {name} — {ticker} is the week's anchor at {ret:+.1f}%.",
    "{name} is having a week to forget, {ticker} down at {ret:+.1f}%.",
]
RISK_LINES = [
    "Wildest ride this week: {name}'s {ticker}, swinging hard both ways.",
    "{name} clearly doesn't believe in boring — {ticker} is all over the place.",
]
FALLBACK_LINE = "Fresh prices are in for Stocks Elite."

# Annualised-volatility threshold (%) above which a "risky" callout is fair —
# tuned by eye against typical single-stock swings in this competition.
_RISK_VOL_THRESHOLD = 30


def build_caption(dashboard, rng=None):
    """Build one fun sentence from an /api/dashboard payload (dict).

    `rng` is injectable for tests; defaults to the `random` module.
    """
    rng = rng or random
    competitors = dashboard.get("competitors") or []
    if not competitors:
        return FALLBACK_LINE

    leader = competitors[0]
    candidates = [rng.choice(LEADER_LINES).format(
        name=leader["name"], ticker=leader["ticker"], ret=leader["return_pct"])]

    if len(competitors) > 1:
        second = competitors[1]
        gap = abs(leader["return_pct"] - second["return_pct"])
        if gap < 3:
            candidates.append(rng.choice(TIGHT_LINES).format(
                name2=second["name"], gap=gap))

    climber = max(competitors, key=lambda c: c.get("rank_change_7d") or 0)
    if (climber.get("rank_change_7d") or 0) >= 2:
        candidates.append(rng.choice(CLIMBER_LINES).format(
            name=climber["name"], jump=climber["rank_change_7d"]))

    if (leader.get("lead_streak") or 0) >= 5:
        candidates.append(rng.choice(STREAK_LINES).format(
            name=leader["name"], streak=leader["lead_streak"]))

    if len(competitors) > 1:
        loser = competitors[-1]
        if loser["return_pct"] < -10:
            candidates.append(rng.choice(LOSER_LINES).format(
                name=loser["name"], ticker=loser["ticker"], ret=loser["return_pct"]))

    awards = dashboard.get("awards") or {}
    riskiest = awards.get("most_risky")
    if riskiest and (riskiest.get("value") or 0) > _RISK_VOL_THRESHOLD:
        candidates.append(rng.choice(RISK_LINES).format(
            name=riskiest["name"], ticker=riskiest["ticker"]))

    return rng.choice(candidates)
