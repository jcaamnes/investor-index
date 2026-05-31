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

# name, tagline, ticker, yahoo_symbol, buy_price, color
# Yahoo symbols verified May 2026. Notes on the non-obvious ones:
#   POET   -> Nasdaq (USD), NOT Oslo. .OL never resolved.
#   MOBA.OL-> Morrow Bank ASA (Oslo). Correct symbol, but Yahoo's API
#             intermittently 404s it; the daily job retries until it resolves.
#   DFNC.DE-> iShares Europe Defence UCITS ETF, Xetra listing (EUR).
#   OSEBX.OL-> Oslo Børs Benchmark Index (Yahoo uses .OL here, not ^OSEBX).
#   KLP    -> KLP AksjeNorge Indeks is a mutual fund; Yahoo lists it under a
#             Morningstar id (0P00001BVT.IR). See note printed by check_symbols.
#   JACK   -> UNCONFIRMED. "JACK" on Nasdaq is Jack in the Box (~$40), which
#             doesn't match the 4.50 buy price — tell me Nichlas's real holding.
COMPETITORS = [
    ("Jan",     "The Oracle of Oslo",        "POET",  "POET",          5.67,    "#a855f7"),
    ("Nøkleby", "Slow and steady",           "KLP",   "0P00001BVT.IR", 1621.00, "#22d3ee"),
    ("Årøen",   "Mobile-first money",        "MOBA",  "MOBA.OL",       12.78,   "#3b82f6"),
    ("Jack",    "Defence never sleeps",      "DFNC",  "DFNC.DE",       5.70,    "#ef4444"),
    ("Tord",    "High risk, high… regret",   "NORSE", "NORSE.OL",      4.24,    "#10b981"),
    ("Ness",    "Consultant's instinct",     "BOUV",  "BOUV.OL",       50.20,   "#f59e0b"),
    ("Henrik",  "Wings of fortune",          "NAS",   "NAS.OL",        14.84,   "#f472b6"),
    ("Nichlas", "All in, always",            "JACK",  "JACK",          4.50,    "#84cc16"),
]

BENCHMARK = ("OSEBX", "The market itself", "OSEBX", "OSEBX.OL", 2043.62, "#d946ef")


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

    for name, tagline, ticker, ysym, buy, color in COMPETITORS:
        iid = ensure(name, tagline, color, 0)
        db.upsert_position(iid, qid, ticker, ysym, buy, QUARTER["start_date"], "NOK")

    name, tagline, ticker, ysym, buy, color = BENCHMARK
    bid = ensure(name, tagline, color, 1)
    db.upsert_position(bid, qid, ticker, ysym, buy, QUARTER["start_date"], "NOK")

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
    print("\nSeed complete. Run:  python app.py   then open http://127.0.0.1:5000")


if __name__ == "__main__":
    run()
