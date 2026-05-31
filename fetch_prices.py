"""Price fetching for the Investor Index — Yahoo Finance via yfinance.

This mirrors the simple, proven approach from the original 2025_Q4_stocks.py:

    data = yf.download(ticker, start=..., end=...)
    closes = data["Close"]

That's all Yahoo needs. We deliberately do NOT do cookie/crumb priming or hit
the raw chart endpoint — that complexity caused more problems than it solved.

The one operational rule: don't hammer Yahoo. Nine symbols once a day is a
trivial load it never minds, but firing dozens of refreshes in a few minutes
trips a per-IP rate limit (HTTP 429) that makes *every* request fail for a
while. So refresh sparingly (ideally a once-a-day scheduled job), and the DB is
the source of truth between refreshes.

Prices are real-only. If a symbol can't be fetched we store nothing and keep
the last known real close — we never fabricate data.

Deploying behind a blocked IP: Yahoo refuses datacenter IPs (Render, AWS, ...),
so a server fetch returns empty for every symbol. The fix is push_prices.py —
run it on your own machine (where Yahoo works) to fetch the closes and push them
up to the live site's /api/prices endpoint.
"""

import datetime as dt
import math
import time

import db

# Be polite between symbols so a 9-stock refresh doesn't burst all at once.
_INTER_CALL_SLEEP_S = 0.6


def fetch_quotes(symbol, start, end):
    """Fetch daily closes for one symbol from Yahoo via yfinance.

    Returns (rows, reason) where rows is a list of (date, close) on success or
    None on failure, and reason is a short human-readable string for diagnostics.

    Uses raw (unadjusted) Close so the dashboard matches the headline closing
    price people see quoted — auto_adjust=False keeps "Close" un-back-adjusted.
    """
    try:
        import yfinance as yf
    except Exception:
        return None, "yfinance not installed — run: pip install yfinance"

    # yfinance's `end` is exclusive, so add a day to include the final session.
    try:
        end_plus = (dt.date.fromisoformat(end) + dt.timedelta(days=1)).isoformat()
    except ValueError:
        end_plus = end

    try:
        data = yf.download(
            symbol, start=start, end=end_plus,
            progress=False, auto_adjust=False, threads=False,
        )
    except Exception as e:
        msg = str(e)
        if "429" in msg or "Too Many Requests" in msg:
            return None, "Yahoo HTTP 429 (rate-limited — wait a few minutes, then refresh once)"
        data = None
        download_err = f"yfinance error: {type(e).__name__}: {msg[:120]}"
    else:
        download_err = None

    out = _closes_from_frame(data)

    # Fallback: some symbols (notably a few Oslo .OL tickers) 404 on download()'s
    # quoteSummary/timezone prefetch but resolve fine via the Ticker.history()
    # chart endpoint. Still Yahoo, still one source — just a different path.
    if not out:
        try:
            hist = yf.Ticker(symbol).history(
                start=start, end=end_plus, auto_adjust=False,
            )
            out = _closes_from_frame(hist)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Too Many Requests" in msg:
                return None, "Yahoo HTTP 429 (rate-limited — wait a few minutes, then refresh once)"

    if not out:
        return None, download_err or "no data returned (check the symbol / date range)"
    out.sort(key=lambda r: r[0])
    return out, "ok"


def _closes_from_frame(data):
    """Pull [(date, close)] rows out of a yfinance DataFrame, skipping NaNs.

    Returns [] for an empty/None frame or one without a usable Close column.
    """
    if data is None or len(data) == 0:
        return []
    if "Close" not in data:
        return []
    closes = data["Close"]
    if hasattr(closes, "columns"):
        closes = closes.iloc[:, 0]

    out = []
    for idx, val in closes.items():
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if math.isnan(v):
            continue
        d = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
        out.append((d, v))
    return out


# Backwards-compatible aliases for older callers / scripts.
fetch_yahoo = fetch_quotes


def refresh_symbol(symbol, start, end):
    """Fetch one symbol from Yahoo and store its real closes.

    Returns (kind, n, reason) where kind is:
      "real"   - live data fetched and stored,
      "failed" - Yahoo returned nothing; the previous real close is kept.

    We never fabricate data, and a failed fetch never wipes good stored prices.
    """
    real, reason = fetch_quotes(symbol, start, end)
    if real:
        db.clear_prices(symbol)
        db.store_prices(symbol, real)
        return "real", len(real), "ok"
    return "failed", 0, reason


def refresh_quarter(quarter_id):
    """Refresh every position's symbol for a quarter, real-only.

    Returns a per-symbol report dict. A failed fetch is reported honestly as
    "failed" and never replaced with fabricated numbers.
    """
    quarter = db.get_quarter(quarter_id)
    if not quarter:
        return {"error": "quarter not found"}
    start = quarter["start_date"]
    today = dt.date.today().isoformat()
    end = min(quarter["end_date"], today)

    report = {}
    positions = db.list_positions(quarter_id)
    for i, pos in enumerate(positions):
        kind, n, reason = refresh_symbol(pos["yahoo_symbol"], start, end)
        report[pos["yahoo_symbol"]] = {
            "kind": kind, "points": n, "ticker": pos["ticker"], "reason": reason,
        }
        # Small gap between symbols so we never burst all 9 at once.
        if i < len(positions) - 1:
            time.sleep(_INTER_CALL_SLEEP_S)
    return report
