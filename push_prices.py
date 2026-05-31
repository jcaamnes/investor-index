"""Local price pusher for the Investor Index.

Yahoo Finance blocks datacenter IPs (Render, AWS, ...), so the deployed server
can't fetch prices itself. This script runs on YOUR machine — where Yahoo works
fine — fetches the closes for the live site's active quarter, and pushes them up
to the server's /api/prices endpoint. The server just stores what it's given.

Usage:

    python push_prices.py --url https://investor-index.onrender.com --password SECRET

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


def main():
    ap = argparse.ArgumentParser(description="Fetch prices locally and push to the live Investor Index.")
    ap.add_argument("--url", default=os.environ.get("PUSH_URL", ""),
                    help="Base URL of the live site, e.g. https://investor-index.onrender.com")
    ap.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", ""),
                    help="Admin password set on the server (ADMIN_PASSWORD).")
    args = ap.parse_args()

    base = args.url.strip().rstrip("/")
    if not base:
        sys.exit("No URL. Pass --url or set PUSH_URL.")

    # 1) Which quarter is active, and over what dates?
    qmeta = _get_json(f"{base}/api/quarters")
    active_id = qmeta.get("active_id")
    quarters = {q["id"]: q for q in qmeta.get("quarters", [])}
    quarter = quarters.get(active_id)
    if not quarter:
        sys.exit("No active quarter on the server. Add/activate one in /admin first.")

    start = quarter["start_date"]
    today = dt.date.today().isoformat()
    end = min(quarter["end_date"], today)

    # 2) Which symbols does it hold?
    positions = _get_json(f"{base}/api/positions?quarter_id={active_id}").get("positions", [])
    symbols = sorted({p["yahoo_symbol"] for p in positions if p.get("yahoo_symbol")})
    if not symbols:
        sys.exit("No positions in the active quarter. Enter buy orders in /admin first.")

    print(f"Quarter {quarter['label']}  ({start} -> {end})  ·  {len(symbols)} symbols")

    # 3) Fetch each symbol locally (Yahoo serves your residential IP).
    prices, ok, fail = {}, [], []
    for sym in symbols:
        rows, reason = fetch_prices.fetch_quotes(sym, start, end)
        if rows:
            prices[sym] = rows
            ok.append(sym)
            print(f"  OK    {sym:<14} {len(rows)} closes")
        else:
            fail.append((sym, reason))
            print(f"  FAIL  {sym:<14} {reason}")

    if not prices:
        sys.exit("\nFetched nothing — not pushing. (Check your symbols / connection.)")

    # 4) Push the closes up to the server.
    result = _post_json(f"{base}/api/prices", {"prices": prices}, args.password)
    stored = result.get("stored", {})
    total = sum(stored.values())
    print(f"\nPushed {len(stored)} symbols ({total} closes) to {base}.")
    if fail:
        print(f"{len(fail)} symbol(s) had no data and were left as-is: "
              + ", ".join(s for s, _ in fail))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        sys.exit(f"HTTP {e.code} from server: {detail}\n"
                 f"(401 means the --password didn't match the server's ADMIN_PASSWORD.)")
    except Exception as exc:
        sys.exit(f"Push failed: {exc}")
