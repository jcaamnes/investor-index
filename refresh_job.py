"""Daily price-refresh job.

Two modes:
  * HTTP mode (set REFRESH_URL) — POSTs to the running web service's
    /api/refresh endpoint. Use this on Render, where a persistent disk can
    only attach to ONE service, so the cron job can't touch the DB directly.
  * Local mode (no REFRESH_URL) — refreshes the active quarter directly
    against the local database. Handy for a cron on your own machine.

Run:  python refresh_job.py
"""

import os
import sys


def run_http(url):
    import urllib.request
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read().decode("utf-8", "replace")
    print(f"POST {url} -> {resp.status}")
    print(body[:500])


def run_local():
    import db
    import fetch_prices
    q = db.get_active_quarter()
    if not q:
        print("No active quarter — nothing to refresh.")
        return
    # Real-only: if Yahoo is down we keep the previous real closes rather than
    # inventing data.
    report = fetch_prices.refresh_quarter(q["id"])
    real = sum(1 for r in report.values() if r["kind"] == "real")
    miss = sum(1 for r in report.values() if r["kind"] == "failed")
    print(f"Refreshed {q['label']}: {real} live, {miss} unavailable.")
    for sym, r in report.items():
        print(f"  - {r['ticker']:<6} {sym:<10} {r['kind']:<10} {r['points']} pts")


if __name__ == "__main__":
    url = os.environ.get("REFRESH_URL")
    try:
        if url:
            run_http(url)
        else:
            run_local()
    except Exception as exc:
        print("Refresh job failed:", exc)
        sys.exit(1)
