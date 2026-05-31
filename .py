"""Diagnostic: check whether each competitor's symbol resolves on Yahoo (yfinance).

Run it to see, at a glance, which symbols pull real data and which are wrong:

    python check_symbols.py            # checks the active quarter
    python check_symbols.py "Q2 2026"  # checks a named quarter
    python check_symbols.py AAPL BOUV.OL OSEBX.OL   # ad-hoc symbol check

For each symbol it prints OK + the latest real close, or FAIL + the reason.
Nothing is written to the database — this is read-only.

Tip: run this sparingly. Each run hits Yahoo once per symbol; firing it many
times in a few minutes can trip Yahoo's rate limit (HTTP 429) for a while.
"""

import datetime as dt
import sys

import db
import fetch_prices


def check_one(symbol, start, end):
    rows, reason = fetch_prices.fetch_quotes(symbol, start, end)
    if rows:
        last_date, last_close = rows[-1]
        return True, f"{len(rows)} closes · latest {last_close:.4f} on {last_date}"
    return False, reason


def main():
    args = sys.argv[1:]
    today = dt.date.today().isoformat()

    # Ad-hoc mode: any arg that looks like a symbol (has a dot/caret or is upper).
    adhoc = [a for a in args if a.startswith("^") or "." in a or a.isupper()]
    if adhoc:
        start = (dt.date.today() - dt.timedelta(days=14)).isoformat()
        print(f"Checking {len(adhoc)} symbol(s) over the last 2 weeks:\n")
        for sym in adhoc:
            ok, msg = check_one(sym, start, today)
            print(f"  {'OK  ' if ok else 'FAIL'}  {sym:<14} {msg}")
        return

    # Quarter mode.
    label = " ".join(args).strip()
    quarter = None
    if label:
        for q in db.list_quarters():
            if q["label"] == label:
                quarter = q
                break
        if not quarter:
            print(f"No quarter named {label!r}. Known: "
                  + ", ".join(q["label"] for q in db.list_quarters()))
            return
    else:
        quarter = db.get_active_quarter()
        if not quarter:
            print("No active quarter. Pass a quarter label or symbols to check.")
            return

    start = quarter["start_date"]
    end = min(quarter["end_date"], today)
    positions = db.list_positions(quarter["id"])
    print(f"Quarter {quarter['label']}  ({start} → {end})  ·  {len(positions)} symbols\n")

    live = 0
    for pos in positions:
        ok, msg = check_one(pos["yahoo_symbol"], start, end)
        live += ok
        flag = "OK  " if ok else "FAIL"
        print(f"  {flag}  {pos['ticker']:<8} {pos['yahoo_symbol']:<14} {msg}")

    print(f"\n{live}/{len(positions)} symbols resolve on Yahoo Finance.")
    if live < len(positions):
        print("Fix the FAIL symbols in /admin → Buy Orders, then hit Refresh.")


if __name__ == "__main__":
    main()
