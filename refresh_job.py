"""Daily price-refresh job for a LOCAL install.

Refreshes the active quarter's closes directly against the local database by
fetching from Yahoo Finance. Real-only: if Yahoo is down or a symbol doesn't
resolve, the previous real closes are kept rather than inventing data.

Run:  python refresh_job.py

Cron it on your own machine (where Yahoo serves your residential IP), e.g.
weekdays at 18:00 local after the close:

    0 18 * * 1-5  cd /path/to/Stocks && /path/to/.venv/bin/python refresh_job.py

DEPLOYED on Render? Don't use this there — Yahoo blocks Render's datacenter IP,
so a server-side fetch returns nothing. Use push_prices.py instead: it fetches
on your machine and POSTs the closes up to the live site's /api/prices endpoint.
"""

import sys

import db
import fetch_prices


def run_local():
    q = db.get_active_quarter()
    if not q:
        print("No active quarter — nothing to refresh.")
        return
    report = fetch_prices.refresh_quarter(q["id"])
    real = sum(1 for r in report.values() if r["kind"] == "real")
    miss = sum(1 for r in report.values() if r["kind"] == "failed")
    print(f"Refreshed {q['label']}: {real} live, {miss} unavailable.")
    for sym, r in report.items():
        print(f"  - {r['ticker']:<6} {sym:<10} {r['kind']:<10} {r['points']} pts")


if __name__ == "__main__":
    try:
        run_local()
    except Exception as exc:
        print("Refresh job failed:", exc)
        sys.exit(1)
