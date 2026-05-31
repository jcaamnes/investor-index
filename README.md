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
python seed.py        # loads the Q2 2026 line-up + fetches real closes from Yahoo
python app.py         # open http://127.0.0.1:5000
```

Prices are **real-only**. `seed.py` and the refresh job fetch actual closing
prices from Yahoo Finance via `yfinance`; nothing is ever fabricated. If a symbol
can't be fetched it's reported honestly as unavailable and the last known real
close is kept — the app never invents data to fill a gap.

## Using it

- **Dashboard** (`/`) — leader spotlight, performance chart (click legend chips
  to toggle lines), the standings with sparklines, superlative award cards,
  the weekly dispatch, and the Hall of Fame. Top-right: quarter switcher,
  Manage, and the theme toggle.
- **Manage** (`/admin`) — add competitors (with a photo upload + accent colour),
  create quarters and set the active one, and enter each competitor's buy order
  for the quarter. **Refresh prices** pulls the latest closes (works locally;
  see below for how prices reach a deployed site).

## How a competitor is scored

Return = `last_close / buy_price − 1`. Whoever has the highest return at quarter
end wins the grand prize. The chart plots each pick's cumulative % return.

Because the return compares a close to the buy price, **both must be in the same
currency**. Each position stores its own currency, so a holding priced in SEK
(e.g. `MORROW.ST`) needs a SEK buy price, not a NOK one. In `seed.py` a holding
can set `buy_price = None` to anchor its basis to the first real close of the
quarter — handy after a listing/currency change (see the Morrow note in
`seed.py`).

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

Oslo Børs tickers on Yahoo usually end in `.OL` (e.g. `NAS.OL`); Nasdaq
Stockholm uses `.ST` (e.g. `MORROW.ST`); Xetra uses `.DE`. The display ticker and
the Yahoo symbol are separate fields, so you can show `POET` while querying
`POET.OL`. Use `check_symbols.py` to see which symbols resolve:

```bash
python check_symbols.py            # checks the active quarter
python check_symbols.py "Q2 2026"  # checks a named quarter
python check_symbols.py MORROW.ST BOUV.OL OSEBX.OL   # ad-hoc check
```

## Keeping prices fresh

**Local install** — cron `refresh_job.py` on your own machine (where Yahoo serves
your residential IP), weekdays after the close:

```bash
0 18 * * 1-5  cd /path/to/Stocks && .venv/bin/python refresh_job.py
```

**Deployed site** — Yahoo blocks datacenter IPs, so the server can't fetch its
own prices. Instead `push_prices.py` runs on your machine, fetches the active
quarter's closes, and POSTs them to the live site's `/api/prices` endpoint. See
`DEPLOY.md`.

## Tests

```bash
python -m pytest tests/test_fetch.py -q   # or: python tests/test_fetch.py
```

These mock `yfinance` and never touch the network.

## Files

```
app.py            Flask server + JSON API (incl. /api/prices ingest endpoint)
db.py             SQLite schema + queries (data/competition.db)
fetch_prices.py   Yahoo Finance fetch (real-only) via yfinance
analytics.py      returns, rankings timeline, risk metrics, awards, hall of fame
summaries.py      weekly dispatch generator
seed.py           loads the Q2 2026 line-up
refresh_job.py    local cron: refresh the local DB from Yahoo
push_prices.py    local cron: fetch locally, push closes to a deployed site
check_symbols.py  read-only diagnostic: which Yahoo symbols resolve
templates/        index.html (dashboard), admin.html (control room)
static/           css/style.css, js/app.js, js/admin.js, photos/ (uploads)
render.yaml       Render Blueprint (web service + persistent disk)
Procfile          production server command (gunicorn)
```
