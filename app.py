"""Investor Index — a luxury stock-picking competition tracker.

Run:
    pip install -r requirements.txt
    python seed.py        # one-time: load the Q2 2026 demo + fetch prices
    python app.py         # then open http://127.0.0.1:5000
"""

import functools
import os
import time
import uuid

from flask import (Flask, Response, jsonify, render_template, request,
                   send_from_directory, abort)

import db
import analytics
import summaries
import fetch_prices

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Photos live next to the app by default; override with INVESTOR_INDEX_PHOTOS
# so they can sit on a persistent disk in production.
PHOTO_DIR = os.environ.get("INVESTOR_INDEX_PHOTOS",
                           os.path.join(BASE_DIR, "static", "photos"))
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# Simple shared password for the admin area. If unset (e.g. local dev), the
# admin area is open. Set ADMIN_PASSWORD in production to lock it down.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB uploads

db.init_db()
os.makedirs(PHOTO_DIR, exist_ok=True)

# Optional: seed the Q2 2026 demo on first boot if the DB is empty. Best run
# with a single worker; for multi-worker deploys prefer running `python seed.py`
# once via a shell. Off unless SEED_ON_START=1.
if os.environ.get("SEED_ON_START") == "1":
    try:
        if not db.list_quarters():
            import seed
            seed.run()
    except Exception as exc:  # pragma: no cover
        print("seed-on-start skipped:", exc)


# ---------------------------------------------------------------------------
# Admin authentication (HTTP Basic, password only)
# ---------------------------------------------------------------------------
def _authed():
    if not ADMIN_PASSWORD:
        return True  # no password configured -> open (local dev)
    auth = request.authorization
    return auth is not None and auth.password == ADMIN_PASSWORD


def require_admin(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not _authed():
            return Response(
                "Investor Index — admin login required", 401,
                {"WWW-Authenticate": 'Basic realm="Investor Index Admin"'})
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
@require_admin
def admin():
    return render_template("admin.html")


@app.route("/static/photos/<path:filename>")
def photo(filename):
    return send_from_directory(PHOTO_DIR, filename)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _save_photo(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        abort(400, "Unsupported image type")
    name = f"{uuid.uuid4().hex}{ext}"
    file_storage.save(os.path.join(PHOTO_DIR, name))
    return f"/static/photos/{name}"


def _resolve_quarter_id():
    qid = request.args.get("quarter_id", type=int)
    if qid:
        return qid
    q = db.get_active_quarter()
    return q["id"] if q else None


# ---------------------------------------------------------------------------
# API — read
# ---------------------------------------------------------------------------
@app.get("/api/quarters")
def api_quarters():
    active = db.get_active_quarter()
    return jsonify({
        "quarters": db.list_quarters(),
        "active_id": active["id"] if active else None,
    })


@app.get("/api/investors")
def api_investors():
    return jsonify({"investors": db.list_investors()})


@app.get("/api/positions")
def api_positions():
    qid = _resolve_quarter_id()
    if not qid:
        return jsonify({"positions": []})
    return jsonify({"positions": db.list_positions(qid)})


@app.get("/api/dashboard")
def api_dashboard():
    qid = _resolve_quarter_id()
    if not qid:
        return jsonify({"error": "no quarters defined"}), 200
    data = analytics.compute_quarter(qid)
    data["summaries"] = summaries.weekly_summaries(qid)
    data["hall_of_fame"] = analytics.hall_of_fame()
    return jsonify(data)


# ---------------------------------------------------------------------------
# API — write
# ---------------------------------------------------------------------------
@app.post("/api/investors")
@require_admin
def api_add_investor():
    name = (request.form.get("name") or "").strip()
    if not name:
        abort(400, "name required")
    photo = _save_photo(request.files.get("photo"))
    iid = db.add_investor(
        name=name,
        tagline=(request.form.get("tagline") or "").strip(),
        color=(request.form.get("color") or "").strip(),
        photo=photo,
        is_benchmark=1 if request.form.get("is_benchmark") in ("1", "true", "on") else 0,
    )
    return jsonify({"id": iid})


@app.post("/api/investors/<int:iid>")
@require_admin
def api_update_investor(iid):
    fields = {}
    for f in ("name", "tagline", "color"):
        if request.form.get(f) is not None:
            fields[f] = request.form.get(f).strip()
    if request.form.get("is_benchmark") is not None:
        fields["is_benchmark"] = 1 if request.form.get("is_benchmark") in ("1", "true", "on") else 0
    if request.files.get("photo"):
        fields["photo"] = _save_photo(request.files.get("photo"))
    db.update_investor(iid, **fields)
    return jsonify({"ok": True})


@app.delete("/api/investors/<int:iid>")
@require_admin
def api_delete_investor(iid):
    db.delete_investor(iid)
    return jsonify({"ok": True})


@app.post("/api/quarters")
@require_admin
def api_add_quarter():
    d = request.get_json(force=True, silent=True) or request.form
    label = (d.get("label") or "").strip()
    start = (d.get("start_date") or "").strip()
    end = (d.get("end_date") or "").strip()
    if not (label and start and end):
        abort(400, "label, start_date, end_date required")
    active = d.get("is_active") in (1, "1", True, "true", "on")
    qid = db.add_quarter(label, start, end, is_active=active)
    return jsonify({"id": qid})


@app.post("/api/quarters/<int:qid>")
@require_admin
def api_update_quarter(qid):
    d = request.get_json(force=True, silent=True) or request.form
    fields = {}
    for f in ("label", "start_date", "end_date"):
        if d.get(f) is not None and str(d.get(f)).strip():
            fields[f] = str(d.get(f)).strip()
    if not fields:
        abort(400, "nothing to update")
    db.update_quarter(qid, **fields)
    return jsonify({"ok": True})


@app.delete("/api/quarters/<int:qid>")
@require_admin
def api_delete_quarter(qid):
    db.delete_quarter(qid)
    return jsonify({"ok": True})


@app.post("/api/quarters/<int:qid>/activate")
@require_admin
def api_activate_quarter(qid):
    db.set_active_quarter(qid)
    return jsonify({"ok": True})


@app.post("/api/positions")
@require_admin
def api_add_position():
    d = request.get_json(force=True, silent=True) or request.form
    try:
        db.upsert_position(
            investor_id=int(d["investor_id"]),
            quarter_id=int(d["quarter_id"]),
            ticker=(d.get("ticker") or "").strip().upper(),
            yahoo_symbol=(d.get("yahoo_symbol") or d.get("ticker") or "").strip().upper(),
            buy_price=float(d["buy_price"]),
            buy_date=(d.get("buy_date") or "").strip(),
            currency=(d.get("currency") or "NOK").strip().upper(),
        )
    except (KeyError, ValueError):
        abort(400, "investor_id, quarter_id, ticker, buy_price, buy_date required")
    return jsonify({"ok": True})


@app.delete("/api/positions/<int:pid>")
@require_admin
def api_delete_position(pid):
    db.delete_position(pid)
    return jsonify({"ok": True})


@app.post("/api/prices")
@require_admin
def api_ingest_prices():
    """Ingest real closes fetched elsewhere (e.g. push_prices.py running on a
    machine whose IP Yahoo will serve). Body:

        {"prices": {"<yahoo_symbol>": [["2026-04-01", 12.3], ...], ...}}

    Each symbol's stored history is replaced with the supplied closes. This is
    the server-side half of the local-fetch-and-push workflow: the server never
    calls Yahoo (its datacenter IP is blocked), it just stores what's pushed.
    """
    payload = request.get_json(force=True, silent=True) or {}
    prices = payload.get("prices")
    if not isinstance(prices, dict) or not prices:
        abort(400, "expected {'prices': {symbol: [[date, close], ...]}}")

    stored, skipped = {}, {}
    for symbol, rows in prices.items():
        sym = (symbol or "").strip().upper()
        series = []
        for row in rows or []:
            try:
                d = str(row[0])[:10]
                c = float(row[1])
            except (TypeError, ValueError, IndexError):
                continue
            if c == c:  # drop NaN
                series.append((d, c))
        if not sym or not series:
            skipped[symbol] = "no valid rows"
            continue
        db.clear_prices(sym)
        db.store_prices(sym, series)
        stored[sym] = len(series)

    return jsonify({"stored": stored, "skipped": skipped,
                    "symbols": len(stored)})


@app.post("/api/refresh")
def api_refresh():
    qid = _resolve_quarter_id()
    if not qid:
        abort(400, "no quarter")
    t0 = time.time()
    report = fetch_prices.refresh_quarter(qid)
    live = sum(1 for r in report.values() if isinstance(r, dict) and r.get("kind") == "real")
    failed = sum(1 for r in report.values() if isinstance(r, dict) and r.get("kind") == "failed")
    return jsonify({
        "report": report,
        "live": live,
        "failed": failed,
        "seconds": round(time.time() - t0, 1),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
