"""Seed the Q2 2026 competition from the original Investor Index screenshot.

Idempotent: running twice won't duplicate (uses fixed labels + upserts).
After inserting investors/positions it triggers a real-only price refresh from
Yahoo Finance. Symbols Yahoo can't serve are reported as "failed" and left
without data — we never fabricate prices in a real competition.
"""

import db
import fetch_prices
from analytics import compute_quarter  # noqa: F401  (import sanity check)

QUARTER = {
    "label": "Q2 2026",
    "start_date": "2026-04-01",
    "end_date": "2026-06-30",
    "is_active": 1,
}

# name, tagline, ticker, yahoo_symbol, buy_price, color, currency
# A buy_price of None means "use the first real close of the quarter as the
# basis" — handy when a holding's price series only starts mid-quarter or after
# a currency switch (see MORROW below).
#
# Yahoo symbols verified May 2026. Notes on the non-obvious ones:
#   POET     -> Nasdaq (USD), NOT Oslo. .OL never resolved.
#   MORROW.ST-> Morrow Bank. The old Oslo line MOBA.OL was delisted 2025-12-30
#               and merged 1-for-1 into Morrow Bank AB on Nasdaq Stockholm,
#               trading as MORROW.ST in SEK from 2026-01-09. Because the listing
#               (and currency) changed, we don't carry over the old NOK buy
#               price — buy_price is None so the seed anchors the basis to the
#               first real SEK close of the quarter, keeping % return valid.
#   DFNC.DE  -> iShares Europe Defence UCITS ETF, Xetra listing (EUR).
#   OSEBX.OL -> Oslo Børs Benchmark Index (Yahoo uses .OL here, not ^OSEBX).
#   KLP      -> KLP AksjeNorge Indeks is a mutual fund; Yahoo lists it under a
#               Morningstar id (0P00001BVT.IR). See note printed by check_symbols.
#   JACK     -> UNCONFIRMED. "JACK" on Nasdaq is Jack in the Box (~$40), which
#               doesn't match the 4.50 buy price — tell me Nichlas's real holding.
COMPETITORS = [
    ("Jan",     "The Oracle of Oslo",        "POET",   "POET",          5.67,    "#a855f7", "NOK"),
    ("Nøkleby", "Slow and steady",           "KLP",    "0P00001BVT.IR", 1621.00, "#22d3ee", "NOK"),
    ("Årøen",   "Mobile-first money",        "MORROW", "MORROW.ST",     None,    "#3b82f6", "SEK"),
    ("Jack",    "Defence never sleeps",      "DFNC",   "DFNC.DE",       5.70,    "#ef4444", "NOK"),
    ("Tord",    "High risk, high… regret",   "NORSE",  "NORSE.OL",      4.24,    "#10b981", "NOK"),
    ("Ness",    "Consultant's instinct",     "BOUV",   "BOUV.OL",       50.20,   "#f59e0b", "NOK"),
    ("Henrik",  "Wings of fortune",          "NAS",    "NAS.OL",        14.84,   "#f472b6", "NOK"),
    ("Nichlas", "All in, always",            "JACK",   "JACK",          4.50,    "#84cc16", "NOK"),
]

BENCHMARK = ("OSEBX", "The market itself", "OSEBX", "OSEBX.OL", 2043.62, "#d946ef", "NOK")


def run():
    db.init_db()

    # Quarter -------------------------------------------------------------
    existing = {q["label"]: q for q in db.list_quarters()}
    if QUARTER["label"] in existing:
        qid = existing[QUARTER["label"]]["id"]
        db.set_active_quarter(qid)
    else:
        qid = db.add_quarter(**QUARTER)

    # Investors + positions ----------------------------------------------
    by_name = {i["name"]: i for i in db.list_investors()}

    def ensure(name, tagline, color, is_benchmark):
        if name in by_name:
            iid = by_name[name]["id"]
            db.update_investor(iid, tagline=tagline, color=color, is_benchmark=is_benchmark)
            return iid
        return db.add_investor(name=name, tagline=tagline, color=color,
                               is_benchmark=is_benchmark)

    # Positions whose buy_price is None need their basis filled in from the
    # first real close once prices are fetched. Until then, park them at 0.0.
    deferred = []  # (yahoo_symbol, position spec) to anchor after the fetch

    for name, tagline, ticker, ysym, buy, color, currency in COMPETITORS:
        iid = ensure(name, tagline, color, 0)
        db.upsert_position(iid, qid, ticker, ysym, buy if buy is not None else 0.0,
                           QUARTER["start_date"], currency)
        if buy is None:
            deferred.append((iid, ticker, ysym, currency))

    name, tagline, ticker, ysym, buy, color, currency = BENCHMARK
    bid = ensure(name, tagline, color, 1)
    db.upsert_position(bid, qid, ticker, ysym, buy if buy is not None else 0.0,
                       QUARTER["start_date"], currency)
    if buy is None:
        deferred.append((bid, ticker, ysym, currency))

    # Prices --------------------------------------------------------------
    # Drop any fabricated rows left over from earlier demo seeds.
    purged = db.clear_synthetic_prices()
    if purged:
        print(f"Purged {purged} legacy synthetic price row(s).")

    print("Fetching prices (Yahoo Finance, real-only)…")
    report = fetch_prices.refresh_quarter(qid)
    real = sum(1 for r in report.values() if r["kind"] == "real")
    failed = sum(1 for r in report.values() if r["kind"] == "failed")
    print(f"  {real} symbol(s) from Yahoo, {failed} unavailable.")
    for sym, r in report.items():
        print(f"   - {r['ticker']:<6} {sym:<10} {r['kind']:<8} {r['points']} pts"
              + ("" if r["kind"] == "real" else f"   ({r['reason']})"))

    # Anchor any deferred buy prices to the first real close of the quarter.
    for iid, ticker, ysym, currency in deferred:
        rows = db.get_prices(ysym, start=QUARTER["start_date"], end=QUARTER["end_date"])
        if rows:
            basis = float(rows[0]["close"])
            db.upsert_position(iid, qid, ticker, ysym, basis,
                               QUARTER["start_date"], currency)
            print(f"   · anchored {ticker} ({ysym}) buy basis to first close "
                  f"{rows[0]['date']} = {basis:.2f} {currency}")
        else:
            print(f"   · WARNING: {ticker} ({ysym}) has no close yet — buy basis "
                  f"left at 0.0; re-run the seed/refresh once Yahoo serves it.")

    print("\nSeed complete. Run:  python app.py   then open http://127.0.0.1:5000")


if __name__ == "__main__":
    run()
