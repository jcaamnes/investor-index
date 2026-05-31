# Deploying Investor Index online (Render)

This puts your competition on a real always-on URL, with live Yahoo Finance
prices, a password-protected admin area, and a daily auto-refresh.

## What's already wired for you

- **`render.yaml`** — a Blueprint that creates the web service (with a
  persistent disk so the database + photos survive every redeploy) plus a
  daily cron job that refreshes prices.
- **`Procfile`** — production server command (`gunicorn`).
- **Admin password** — `/admin` and every "save/delete" action require a
  password when the `ADMIN_PASSWORD` environment variable is set. The public
  dashboard stays open to everyone.
- **`refresh_job.py`** — the daily job. On Render it calls your live site's
  refresh endpoint; on your own machine it refreshes the local database.

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
The `.gitignore` keeps your local database and uploaded photos out of the repo.

### Step 2 — create the services on Render
1. Sign up at render.com and connect your GitHub.
2. **New ➜ Blueprint**, pick the repo. Render reads `render.yaml` and proposes a
   **web service** + a **cron job**. Click **Apply**.
3. When prompted (or under the web service ➜ **Environment**), set
   **`ADMIN_PASSWORD`** to a password you'll share with your friends.
4. First deploy takes a few minutes. You'll get a URL like
   `https://investor-index.onrender.com`.

### Step 3 — point the cron job at your real URL
The Blueprint guesses `https://investor-index.onrender.com`. If your URL differs,
open the **investor-index-refresh** cron service ➜ **Environment** ➜ edit
`REFRESH_URL` to `https://<your-real-host>/api/refresh`.

### Step 4 — load the starting data
Open the **web service ➜ Shell** and run once:
```bash
python seed.py
```
That loads the Q2 2026 line-up and fetches prices. (Or skip it and add everyone
yourself in `/admin`.)

## Day-to-day use

- **Public dashboard:** share the base URL. Anyone can watch the standings.
- **Admin:** go to `/admin`, the browser asks for the password (any username,
  the password you set). Add competitors + photos, set each quarter's buy
  orders, activate the current quarter.
- **Prices:** the cron job refreshes every weekday at 18:00 UTC. You can also
  hit **Refresh** on the dashboard anytime.

## Getting real Yahoo symbols right

The seeded `.OL` symbols are guesses; fix any that don't resolve:
1. Find the correct symbol on finance.yahoo.com (Oslo stocks end in `.OL`,
   indices start with `^`, e.g. `^OSEBX`).
2. In `/admin` ➜ Buy Orders, edit the **Yahoo symbol** field for that
   competitor and **save**.
3. Hit **Refresh**. The chart banner switches from "demo data" to
   "live · Yahoo Finance" once real closes arrive.

## Cost & notes

- The **Starter** instance type (~$7/mo) is used because Render's **persistent
  disk requires a paid instance** — that disk is what protects your data across
  deploys. A free instance would wipe the database on every redeploy.
- Yahoo Finance is an unofficial data source and can occasionally rate-limit or
  change a symbol. The daily job uses real data only (never synthetic), so if a
  fetch fails the previous real prices simply stay in place.
- Want to run the daily refresh from your own computer instead of Render's cron?
  ```bash
  # macOS/Linux crontab — weekdays at 20:00 local
  0 20 * * 1-5 cd /path/to/Stocks && /path/to/.venv/bin/python refresh_job.py
  ```

## Alternative hosts

The same files work on most PaaS providers. `Procfile` covers Railway and
Heroku-style hosts; you'd add a persistent volume (Railway) or accept that
SQLite resets on redeploy. For anything bigger, the natural upgrade is swapping
SQLite for managed Postgres and photos for object storage (S3/Cloudinary) — tell
me if you outgrow the single-disk setup and I'll wire that in.
