# Investor Index — Architecture & How It Works

A friendly-but-thorough tour of what's under the hood. Read this top to bottom
to understand the whole system, or jump to a section. No prior knowledge of the
codebase assumed.

---

## 1. The one-paragraph mental model

Stock prices flow **in** from Yahoo Finance → a small local **database**
remembers them → an **analytics engine** turns raw prices into rankings,
stats and awards → a JSON **API** hands that to the browser → a single rich
**web page** draws the competition. Everything is computed fresh from stored
prices on each request, so there are no stale "snapshots" to keep in sync.

```
 Yahoo Finance
      │  (fetched on a real machine — see §6)
      ▼
 price_history  ──┐
 investors        │   db.py (SQLite)
 quarters         │
 positions  ──────┘
      │
      ▼
 analytics.py + summaries.py   ← the "brain": rankings, vol, awards, Hall of Fame
      │
      ▼
 app.py  (Flask)  ── /api/dashboard, /admin, ...
      │  JSON
      ▼
 templates/index.html  ← the "face": chart, leaderboard, dispatch, hall of fame
```

The project is deliberately low-dependency: plain Flask, plain `sqlite3`, and
a self-contained HTML page. The database is a single portable file
(`data/competition.db`).

---

## 2. The three layers

### The face — `templates/index.html`
This single file *is* the entire visible website: the CSS styling, the HTML
layout, and the JavaScript that fetches data and draws everything (leaderboard,
performance chart, superlatives, Weekly Dispatch, Hall of Fame, the daily-tip
epigraph, and the Strategy & Reflections section).

Two important design choices live here:

- **Custom canvas chart, no chart library.** The performance line chart is
  drawn by hand on an HTML `<canvas>` (`drawChart()`), including axes,
  gridlines and the hover tooltip. That keeps the page dependency-free and fast.
- **Offline fallback.** The page prefers live data from the server, but if the
  server is unreachable it falls back to a baked-in copy of the all-time
  marathon history (the large `HISTORY` constant) and a synthetic demo
  (`buildDummy()`). This is why most render code has *two* paths — a "live API"
  path and an "offline" path — and why changes must work in both.

### The brain — `app.py`, `analytics.py`, `summaries.py`
- **`app.py`** is the Flask switchboard. It defines the URLs the browser can
  call (the *routes*), serves the pages, and exposes the JSON API. It also holds
  the password-protected `/admin` area for managing investors, quarters and
  picks, plus the photo-upload handling. See §4 for the route list.
- **`analytics.py`** is the real engine. Given a quarter, it reconstructs the
  full day-by-day performance and ranking timeline from cached prices and
  derives every number the dashboard shows. See §5 for the details.
- **`summaries.py`** is a rule-based ("no AI at runtime") generator that turns
  the weekly numbers into a witty paragraph each week — who leads, who's
  charging, who's bleeding. It's deterministic, so the same week always reads
  the same way.

### The memory — `db.py` + `data/`
- **`db.py`** is the data layer. It owns the SQLite schema and all the
  read/write helpers (`list_positions`, `upsert_position`, `store_prices`, …).
  Everything is plain `sqlite3` — no ORM.
- **`data/competition.db`** is the live database file.
- **`data/history.json`** holds the all-time marathon record imported from the
  original spreadsheet (`Stocks maratontabell.xlsx`), covering 2017 Q4 →
  2026 Q1. The analytics fold live quarters on top of this history so the
  all-time standings keep growing each season.

---

## 3. The data model (SQLite schema)

Four tables, defined in `db.py`:

| Table | What it stores | Key columns |
|-------|----------------|-------------|
| `investors` | the competitors (and benchmark indices) | `name`, `tagline`, `photo`, `color`, `is_benchmark` |
| `quarters` | a competition period | `label` (e.g. "Q2 2026"), `start_date`, `end_date`, `is_active` |
| `positions` | **one buy per investor per quarter** | `ticker`, `yahoo_symbol`, `buy_price`, `buy_date`, `currency` |
| `price_history` | cached daily close prices | `yahoo_symbol`, `date`, `close`, `is_synthetic` |

Notable details:

- A `position` is uniquely keyed by `(investor_id, quarter_id)` — you get exactly
  one pick per person per quarter, which is what the game requires.
- `ticker` vs `yahoo_symbol`: the display ticker (e.g. `POET`) can differ from
  the symbol Yahoo needs to fetch it (e.g. `POET.OL` for the Oslo exchange).
- `is_benchmark` flags indices like OSEBX so they're charted (dashed line) but
  excluded from the competitive ranking.
- `is_synthetic` marks any non-real close. Prices are **real-only** by policy;
  this flag lets the dashboard report exactly which date it's "as of".
- The database location is overridable via the `INVESTOR_INDEX_DB` environment
  variable (useful if the app folder sits on a synced/network mount that doesn't
  play nicely with SQLite locking).

---

## 4. The API (routes in `app.py`)

**Pages**
- `GET /` — the dashboard (renders `index.html`).
- `GET /admin` — the management UI (password-protected via `ADMIN_PASSWORD`).
- `GET /static/photos/<file>` — serves uploaded investor photos.

**Read API** (what the dashboard fetches)
- `GET /api/quarters` — list of quarters + which one is active.
- `GET /api/investors`, `GET /api/positions` — raw roster / picks.
- `GET /api/dashboard?quarter_id=…` — **the big one.** Returns the fully
  computed quarter (rankings, awards, chart series), the weekly summaries, and
  the all-time Hall of Fame, in one payload.

**Write API** (used by the admin UI, all require the admin password)
- `POST/DELETE /api/investors[/id]` — add / edit / remove competitors.
- `POST/DELETE /api/quarters[/id]`, `POST /api/quarters/<id>/activate` — manage
  competition periods.
- `POST/DELETE /api/positions[/id]` — record / remove a buy.
- `POST /api/prices` — **ingest** closes fetched elsewhere (see §6).
- `POST /api/refresh` — fetch fresh closes for the active quarter (only works
  where Yahoo will serve the request — see §6).

Admin auth is intentionally simple: HTTP Basic with a single shared password
from the `ADMIN_PASSWORD` env var. If unset (local dev), the admin area is open.

---

## 5. The analytics engine (`analytics.py`), a bit deeper

This is where raw prices become a story. For a given quarter:

1. **Assemble the calendar.** Collect every date that appears across all picks'
   price series, then *forward-fill* each series so a missing day carries the
   last known price forward (`_forward_fill`). This aligns everyone to a common
   timeline.
2. **Per-investor return series.** For each pick, compute the cumulative return
   vs the buy price on every date — that's the line you see on the chart.
3. **Risk & "fun fact" metrics.** From the daily returns it derives annualised
   **volatility**, a **Sharpe**-style risk-adjusted ratio, **max drawdown**
   (worst peak-to-trough), best/worst single days, and a "comeback" measure
   (gain since their lowest point).
4. **Daily ranking timeline.** It re-ranks all competitors on *every* day, which
   yields days-spent-at-#1, current win streak, and 7-day rank momentum (the
   "Mover of the Week").
5. **Awards.** `_awards()` picks the title-holders — Biggest Loser, Most Risky,
   Iron Nerves, Comeback King, etc. — that fill the Superlatives panel.

**Hall of Fame** (`hall_of_fame()`) works across quarters. It seeds the
all-time standings from `data/history.json`, then folds in any *completed* live
quarters not already in that history (in-progress quarters are skipped so they
don't distort the all-time averages). It also reconciles people who appear under
different names across the years via a `NAME_ALIASES` map, and backfills photos
from the current roster. Standings are sorted Olympic-style: gold, then silver,
then bronze, then average return.

The Strategy & Reflections section and the expanded Hall of Fame highlights
(Most Podiums, Biggest Loser of All Time) are computed in the page's JavaScript
from these same standings, so they work in both the live and offline paths.

---

## 6. The price pipeline & the "blocked IP" workaround

Yahoo Finance refuses requests from data-center IPs (Render, AWS, …) but happily
serves a normal residential machine. The app is built around this reality:

- **`fetch_prices.py`** — the actual Yahoo fetch, via `yfinance`. Deliberately
  the plain `yf.download()` call, real-only (never fabricates data), and gentle
  on rate limits (a few symbols once a day; firing many refreshes quickly trips
  an HTTP 429 that fails *everything* for a while).
- **`refresh_job.py`** — for a **local** install: fetches and writes straight to
  the local database. Cron this on your own machine after market close.
- **`push_prices.py`** — for a **deployed** install: runs on your machine,
  fetches from Yahoo, then POSTs the closes up to the live site's
  `/api/prices` endpoint. The server itself never calls Yahoo; it just stores
  what's pushed. The `.command` launchers and `push_gui.py` are convenience
  wrappers around this.

So between refreshes, **the database is the source of truth.** The dashboard
always reports the latest *real* close date it has.

---

## 7. Supporting files

- **`seed.py`** — one-time loader for the demo quarter (Q2 2026) plus an initial
  price fetch. Run once on a fresh database.
- **`check_symbols.py`** — sanity-checks that ticker/Yahoo symbols resolve.
- **`tests/test_fetch.py`** — tests around the fetch layer.
- **`requirements.txt`** — Python dependencies.
- **`render.yaml`, `Procfile`, `DEPLOY.md`** — hosting/deployment configuration
  and instructions (the app is set up to deploy on Render).
- **`com.investorindex.pushprices.plist`** — a macOS launch agent to schedule
  the price push automatically.

---

## 8. Running it locally

```bash
pip install -r requirements.txt
python seed.py        # one-time: load the demo quarter + fetch prices
python app.py         # then open http://127.0.0.1:5000
```

To keep prices current on a local install, schedule `refresh_job.py` after the
close (weekdays). For a deployed install, schedule `push_prices.py` on a machine
Yahoo will serve instead.

---

## 9. How to make a change safely

- **Front-end (the page):** edit `templates/index.html`. Remember the two render
  paths — test that a change works both with the live server and with the
  offline `HISTORY`/`buildDummy` fallback.
- **A new computed stat:** add it in `analytics.py` (it'll flow out through
  `/api/dashboard`), then render it in `index.html`.
- **A schema change:** update `SCHEMA` and the helpers in `db.py`.
- **Anything price-related:** respect the real-only rule and the rate-limit
  caution in `fetch_prices.py`.

---

*This document describes how the system works for developers. The app itself is
just for fun — a gentlemen's wager — and nothing here is financial advice.*
