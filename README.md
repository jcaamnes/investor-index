# Investor Index

A luxury, dynamic web app for running a stock-picking competition between friends.
Each quarter every competitor buys one ticker; the app tracks day-by-day
performance, ranks a live leaderboard, hands out fun "superlative" awards, writes
a witty weekly dispatch, and keeps a cross-quarter Hall of Fame. Dark + light
themes, inspired by Rolex green / Porsche graphite / gold.

## Quick start

```bash
cd "<this folder>"
python3 -m venv .venv && source .venv/bin/activate      # optional but recommended
pip install -r requirements.txt
python seed.py        # loads the Q2 2026 demo (from the original screenshot) + fetches prices
python app.py         # open http://127.0.0.1:5000
```

`seed.py` tries Yahoo Finance first. If you're offline (or a ticker doesn't
resolve) it falls back to a **synthetic demo series** tuned to match the
screenshot's final returns, so the dashboard is never empty. A small banner on
the chart says "demo prices" until you click **Refresh** with a live connection
and real closes come in.

## Using it

- **Dashboard** (`/`) — leader spotlight, performance chart (click legend chips
  to toggle lines), the standings with sparklines, superlative award cards,
  the weekly dispatch, and the Hall of Fame. Top-right: quarter switcher,
  Refresh, Manage, and the theme toggle.
- **Manage** (`/admin`) — add competitors (with a photo upload + accent colour),
  create quarters and set the active one, and enter each competitor's buy order
  for the quarter. Hit **Refresh prices** to pull the latest closes.

## How a competitor is scored

Return = `last_close / buy_price − 1`. Whoever has the highest return at quarter
end wins the grand prize. The chart plots each pick's cumulative % return.

## The fun metrics

| Award | Meaning |
|---|---|
| Best Investor | Highest current return (the leader) |
| Biggest Loser | Lowest current return |
| Most Risky | Highest annualised volatility of daily returns |
| Iron Nerves | Lowest volatility |
| Smartest Money | Best Sharpe-style return-per-risk |
| Deepest Dip | Largest peak-to-trough drawdown |
| Comeback King | Biggest rise from their lowest point |
| Best / Worst Single Day | Biggest one-day pop / drop |
| Most Days at #1 | Longest time owning the top of the board |
| Mover of the Week | Biggest 7-trading-day rank jump |

The **Hall of Fame** aggregates every quarter: wins, podiums, best/worst quarter
ever, and average return per competitor.

## Symbols

Oslo Børs tickers on Yahoo usually end in `.OL` (e.g. `NAS.OL`); indices start
with `^` (e.g. `^OSEBX`). The seeded `.OL` guesses may need correcting — edit the
**Yahoo symbol** field per competitor in Manage, then Refresh. The display
ticker and the Yahoo symbol are separate fields, so you can show `POET` while
querying `POET.OL`.

## Keeping it fresh automatically (optional)

Run a refresh on a schedule, e.g. a daily cron on a trading day:

```bash
0 18 * * 1-5  cd /path/to/Stocks && .venv/bin/python -c "import db,fetch_prices; fetch_prices.refresh_quarter(db.get_active_quarter()['id'])"
```

## Files

```
app.py            Flask server + JSON API
db.py             SQLite schema + queries (data/competition.db)
fetch_prices.py   Yahoo Finance fetch + synthetic fallback
analytics.py      returns, rankings timeline, risk metrics, awards, hall of fame
summaries.py      weekly dispatch generator
seed.py           loads the Q2 2026 demo
templates/        index.html (dashboard), admin.html (control room)
static/           css/style.css, js/app.js, js/admin.js, photos/ (uploads)
```
