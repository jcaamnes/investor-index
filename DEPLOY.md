# Deploying Investor Index online (Render)

This puts your competition on a real always-on URL, with a password-protected
admin area. Prices are kept fresh by a small script you run from your own
machine (explained below).

## The one thing to understand first

**Yahoo Finance blocks datacenter IPs** (Render, AWS, GCP, …). A fetch from the
server returns *nothing* for every symbol. So the server never calls Yahoo.
Instead:

1. `push_prices.py` runs on **your machine** (residential IP, where Yahoo works),
   fetches the active quarter's closes, and
2. POSTs them to the live site's `/api/prices` endpoint, which just stores them.

The deployed app's job is to display and analyse prices; your laptop's job is to
feed it real ones.

## What's already wired for you

- **`render.yaml`** — a Blueprint that creates the web service with a persistent
  disk so the database + photos survive every redeploy.
- **`Procfile`** — production server command (`gunicorn`).
- **`.python-version`** (`3.11.9`) — pins Python so pandas installs from a
  prebuilt wheel instead of trying (and failing) to compile from source.
- **Admin password** — `/admin` and every save/delete action require a password
  when the `ADMIN_PASSWORD` environment variable is set. The public dashboard
  stays open to everyone. `/api/prices` uses the same password.
- **`push_prices.py`** — the local price feeder (see "Keeping prices fresh").

## One-time setup

### Step 1 — put the code on GitHub
```bash
cd "Stocks"
git init
git add .
git commit -m "Investor Index"
# create an empty repo on github.com, then:
git remote add origin https://github.com/<you>/investor-index.git
git push -u origin main
```
The `.gitignore` keeps your local database and uploaded photos out of the repo
(but `data/history.json`, the Hall of Fame history, is committed).

### Step 2 — create the service on Render
1. Sign up at render.com and connect your GitHub.
2. **New ➜ Blueprint**, pick the repo. Render reads `render.yaml` and proposes a
   **web service** with a persistent disk. Click **Apply**.
3. Under the web service ➜ **Environment**, set **`ADMIN_PASSWORD`** to a
   password you'll share with your friends.
4. First deploy takes a few minutes. You'll get a URL like
   `https://investor-index.onrender.com`.

### Step 3 — load the starting data
Open the **web service ➜ Shell** and run once:
```bash
python seed.py
```
That loads the Q2 2026 line-up. (Or skip it and add everyone in `/admin`.)
Note: seeding on the server won't fetch prices — that's expected; prices arrive
via the push step below.

## Keeping prices fresh

From **your own machine**, run the pusher:

```bash
python push_prices.py --url https://investor-index.onrender.com --password YOUR_ADMIN_PASSWORD
```

Or via environment variables (handy for cron):

```bash
PUSH_URL=https://investor-index.onrender.com \
ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD \
python push_prices.py
```

Cron it weekdays after the close (it needs `yfinance`, already in
`requirements.txt`):

```bash
# macOS/Linux crontab — weekdays at 18:30 local
30 18 * * 1-5  cd /path/to/Stocks && /path/to/.venv/bin/python push_prices.py >> push.log 2>&1
```

Each run replaces the stored history for the symbols it successfully fetched;
symbols Yahoo can't serve are left untouched. Don't fire it many times in a few
minutes — Yahoo rate-limits per IP (HTTP 429). Once a day is plenty.

## Day-to-day use

- **Public dashboard:** share the base URL. Anyone can watch the standings.
- **Admin:** go to `/admin`, the browser asks for the password (any username, the
  password you set). Add competitors + photos, set each quarter's buy orders,
  activate the current quarter.
- **Prices:** run `push_prices.py` (or let cron do it). The dashboard reflects
  whatever's in the database.

## Cost & notes

- The **Starter** instance type (~$7/mo) is used because Render's **persistent
  disk requires a paid instance** — that disk is what protects your data across
  deploys. A free instance would wipe the database on every redeploy and has no
  Shell, so you'd have to seed via the API instead.
- Yahoo Finance is an unofficial data source and can occasionally rate-limit or
  change a symbol. Everything is real data only (never synthetic), so if a fetch
  fails the previous real prices simply stay in place.

## Alternative hosts

The same files work on most PaaS providers. `Procfile` covers Railway and
Heroku-style hosts; you'd add a persistent volume (Railway) or accept that SQLite
resets on redeploy. The push workflow is host-agnostic — point `push_prices.py`
at whatever URL the site ends up on. For anything bigger, the natural upgrade is
swapping SQLite for managed Postgres and photos for object storage
(S3/Cloudinary) — ask if you outgrow the single-disk setup.
