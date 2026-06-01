"""Daily price-refresh job for a LOCAL install.

Refreshes quarter closes directly against the local database by fetching from
Yahoo Finance. Real-only: if Yahoo is down or a symbol doesn't resolve, the
previous real closes are kept rather than inventing data.

Run:
    python refresh_job.py                 # the active quarter (default)
    python refresh_job.py --all           # every quarter (e.g. to backfill history)
    python refresh_job.py --quarter "Q1 2026"   # one quarter by label
    python refresh_job.py --quarter-id 3        # one quarter by id

Cron it on your own machine (where Yahoo serves your residential IP), e.g.
weekdays at 18:00 local after the close:

    0 18 * * 1-5  cd /path/to/Stocks && /path/to/.venv/bin/python refresh_job.py

DEPLOYED on Render? Don't use this there — Yahoo blocks Render's datacenter IP,
so a server-side fetch returns nothing. Use push_prices.py instead: it fetches
on your machine and POSTs the closes up to the live site's /api/prices endpoint.
"""

import argparse
import sys
import time

import db
import fetch_prices


def _refresh_one(q):
    report = fetch_prices.refresh_quarter(q["id"])
    if isinstance(report, dict) and report.get("error"):
        print(f"{q['label']}: {report['error']}")
        return
    real = sum(1 for r in report.values() if r["kind"] == "real")
    miss = sum(1 for r in report.values() if r["kind"] == "failed")
    print(f"Refreshed {q['label']}: {real} live, {miss} unavailable.")
    for sym, r in report.items():
        print(f"  - {r['ticker']:<6} {sym:<10} {r['kind']:<10} {r['points']} pts")
        if r["kind"] == "failed":
            print(f"        ↳ {r['reason']}")


def run_local(target="active"):
    if target == "all":
        quarters = db.list_quarters()
        if not quarters:
            print("No quarters defined — nothing to refresh.")
            return
        for i, q in enumerate(quarters):
            _refresh_one(q)
            # Pause between quarters so we don't burst Yahoo and trip a 429.
            if i < len(quarters) - 1:
                time.sleep(2.0)
        return

    if isinstance(target, dict):
        _refresh_one(target)
        return

    q = db.get_active_quarter()
    if not q:
        print("No active quarter — nothing to refresh.")
        return
    _refresh_one(q)


def _resolve_target(args):
    if args.all:
        return "all"
    if args.quarter_id is not None:
        q = db.get_quarter(args.quarter_id)
        if not q:
            sys.exit(f"No quarter with id {args.quarter_id}.")
        return q
    if args.quarter:
        match = [q for q in db.list_quarters()
                 if q["label"].strip().lower() == args.quarter.strip().lower()]
        if not match:
            labels = ", ".join(q["label"] for q in db.list_quarters()) or "(none)"
            sys.exit(f"No quarter labelled {args.quarter!r}. Known: {labels}")
        return match[0]
    return "active"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Refresh Yahoo closes into the local DB.")
    ap.add_argument("--all", action="store_true", help="refresh every quarter")
    ap.add_argument("--quarter", help="refresh one quarter by its label, e.g. 'Q1 2026'")
    ap.add_argument("--quarter-id", type=int, help="refresh one quarter by its numeric id")
    args = ap.parse_args()
    try:
        run_local(_resolve_target(args))
    except Exception as exc:
        print("Refresh job failed:", exc)
        sys.exit(1)
