"""Local price pusher for the Investor Index.

Yahoo Finance blocks datacenter IPs (Render, AWS, ...), so the deployed server
can't fetch prices itself. This script runs on YOUR machine — where Yahoo works
fine — fetches the closes for the live site's active quarter, and pushes them up
to the server's /api/prices endpoint. The server just stores what it's given.

Usage:

    python push_prices.py --url https://investor-index.onrender.com --password SECRET

By default it pushes the server's active quarter. To push a specific or every
quarter (e.g. to backfill a past season's prices on the live site):

    python push_prices.py --url ... --password ... --quarter "Q1 2026"
    python push_prices.py --url ... --password ... --quarter-id 3
    python push_prices.py --url ... --password ... --all

Or via environment variables (handy for a cron job):

    PUSH_URL=https://investor-index.onrender.com \
    ADMIN_PASSWORD=SECRET \
    python push_prices.py

Run it whenever you want fresh numbers, or put it in a daily cron on a weekday,
e.g. (macOS/Linux crontab, 18:30 local, Mon–Fri):

    30 18 * * 1-5  cd /path/to/Stocks && /path/to/.venv/bin/python push_prices.py >> push.log 2>&1

It needs yfinance installed locally (it already is, from requirements.txt) and
the same ADMIN_PASSWORD you set on the server.
"""

import argparse
import base64
import datetime as dt
import json
import os
import ssl
import sys
import urllib.request

import fetch_prices  # local Yahoo fetch (works from your residential IP)

# Some Python installs (notably python.org builds on macOS) ship without the
# system CA certificates wired up, so HTTPS verification fails with
# "CERTIFICATE_VERIFY_FAILED". Use certifi's bundle when it's available — it's
# already installed as a yfinance dependency — so verification just works.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()


def _get_json(url):
    with urllib.request.urlopen(url, timeout=60, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url, body, password):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if password:
        # The server checks the password only; any username works.
        token = base64.b64encode(f"admin:{password}".encode()).decode()
        req.add_header("Authorization", "Basic " + token)
    with urllib.request.urlopen(req, timeout=180, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_targets(base, args):
    """Return the list of target quarters (active / one / all) to push.

    Each quarter is pushed over its OWN date range only — we don't fetch beyond
    the quarter's window. The server replaces just that date range per symbol, so
    a shared ticker keeps the closes stored for its other quarters.
    """
    qmeta = _get_json(f"{base}/api/quarters")
    quarters = qmeta.get("quarters", [])
    if not quarters:
        sys.exit("No quarters on the server. Add one in /admin first.")
    by_id = {q["id"]: q for q in quarters}

    if args.all:
        return quarters
    if args.quarter_id is not None:
        q = by_id.get(args.quarter_id)
        if not q:
            sys.exit(f"No quarter with id {args.quarter_id} on the server.")
        return [q]
    if args.quarter:
        match = [q for q in quarters
                 if q["label"].strip().lower() == args.quarter.strip().lower()]
        if not match:
            labels = ", ".join(q["label"] for q in quarters)
            sys.exit(f"No quarter labelled {args.quarter!r}. Known: {labels}")
        return match
    q = by_id.get(qmeta.get("active_id"))
    if not q:
        sys.exit("No active quarter on the server. Add/activate one in /admin first.")
    return [q]


def _push_quarter(base, quarter, password):
    """Fetch one quarter's symbols over its own range and push them. Returns
    (stored_count, fail_count)."""
    today = dt.date.today().isoformat()
    start = quarter["start_date"]
    end = min(quarter["end_date"], today)

    positions = _get_json(
        f"{base}/api/positions?quarter_id={quarter['id']}").get("positions", [])
    symbols = sorted({p["yahoo_symbol"] for p in positions if p.get("yahoo_symbol")})
    if not symbols:
        print(f"Quarter {quarter['label']}  ·  no positions — skipping.")
        return 0, 0

    print(f"Quarter {quarter['label']}  ({start} -> {end})  ·  {len(symbols)} symbols")

    prices, fail = {}, []
    for sym in symbols:
        rows, reason = fetch_prices.fetch_quotes(sym, start, end)
        if rows:
            prices[sym] = rows
            print(f"  OK    {sym:<14} {len(rows)} closes")
        else:
            fail.append((sym, reason))
            print(f"  FAIL  {sym:<14} {reason}")

    if not prices:
        print("  (fetched nothing — not pushing this quarter.)")
        return 0, len(fail)

    result = _post_json(f"{base}/api/prices", {"prices": prices}, password)
    stored = result.get("stored", {})
    total = sum(stored.values())
    print(f"  Pushed {len(stored)} symbols ({total} closes).")
    if fail:
        print("  Left as-is (no data): " + ", ".join(s for s, _ in fail))
    return total, len(fail)


def main():
    ap = argparse.ArgumentParser(description="Fetch prices locally and push to the live Investor Index.")
    ap.add_argument("--url", default=os.environ.get("PUSH_URL", ""),
                    help="Base URL of the live site, e.g. https://investor-index.onrender.com")
    ap.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", ""),
                    help="Admin password set on the server (ADMIN_PASSWORD).")
    ap.add_argument("--all", action="store_true", help="push every quarter")
    ap.add_argument("--quarter", help="push one quarter by its label, e.g. 'Q1 2026'")
    ap.add_argument("--quarter-id", type=int, help="push one quarter by its numeric id")
    args = ap.parse_args()

    base = args.url.strip().rstrip("/")
    if not base:
        sys.exit("No URL. Pass --url or set PUSH_URL.")

    targets = _resolve_targets(base, args)
    grand_total = grand_fail = 0
    for q in targets:
        total, fail = _push_quarter(base, q, args.password)
        grand_total += total
        grand_fail += fail

    if grand_total == 0:
        sys.exit("\nNothing pushed. (Check your symbols / connection.)")
    print(f"\nDone · pushed {grand_total} closes to {base}.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        sys.exit(f"HTTP {e.code} from server: {detail}\n"
                 f"(401 means the --password didn't match the server's ADMIN_PASSWORD.)")
    except Exception as exc:
        sys.exit(f"Push failed: {exc}")
