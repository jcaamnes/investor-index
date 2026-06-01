"""SQLite data layer for the Investor Index competition app.

Tables
------
investors      : the competitors (and benchmark indices, flagged is_benchmark)
quarters       : a competition period, e.g. "Q2 2026" with start/end dates
positions      : one buy per investor per quarter (ticker + buy price)
price_history  : cached daily close prices per yahoo symbol

Everything is plain sqlite3 so the app has almost no dependencies and the
database is a single portable file at data/competition.db.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
# DB lives next to the app by default; override with INVESTOR_INDEX_DB if the
# app folder is on a filesystem that doesn't support SQLite locking (e.g. some
# network/synced mounts).
DB_PATH = os.environ.get("INVESTOR_INDEX_DB", os.path.join(DATA_DIR, "competition.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS investors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    tagline      TEXT DEFAULT '',
    photo        TEXT DEFAULT '',
    color        TEXT DEFAULT '',
    is_benchmark INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    is_active  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id  INTEGER NOT NULL,
    quarter_id   INTEGER NOT NULL,
    ticker       TEXT NOT NULL,          -- display ticker, e.g. POET
    yahoo_symbol TEXT NOT NULL,          -- symbol used for fetching, e.g. POET.OL
    buy_price    REAL NOT NULL,
    buy_date     TEXT NOT NULL,
    currency     TEXT DEFAULT 'NOK',
    FOREIGN KEY (investor_id) REFERENCES investors(id) ON DELETE CASCADE,
    FOREIGN KEY (quarter_id)  REFERENCES quarters(id)  ON DELETE CASCADE,
    UNIQUE (investor_id, quarter_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    yahoo_symbol TEXT NOT NULL,
    date         TEXT NOT NULL,
    close        REAL NOT NULL,
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    UNIQUE (yahoo_symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_price_symbol_date
    ON price_history (yahoo_symbol, date);
"""


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)


# ----------------------------------------------------------------------------
# Investors
# ----------------------------------------------------------------------------
def add_investor(name, tagline="", photo="", color="", is_benchmark=0):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO investors (name, tagline, photo, color, is_benchmark, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (name, tagline, photo, color, int(is_benchmark), datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def update_investor(investor_id, **fields):
    allowed = {"name", "tagline", "photo", "color", "is_benchmark"}
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not sets:
        return
    cols = ", ".join(f"{k} = ?" for k in sets)
    with db() as conn:
        conn.execute(f"UPDATE investors SET {cols} WHERE id = ?", (*sets.values(), investor_id))


def delete_investor(investor_id):
    with db() as conn:
        conn.execute("DELETE FROM investors WHERE id = ?", (investor_id,))


def list_investors(include_benchmark=True):
    q = "SELECT * FROM investors"
    if not include_benchmark:
        q += " WHERE is_benchmark = 0"
    q += " ORDER BY is_benchmark, name"
    with db() as conn:
        return [dict(r) for r in conn.execute(q)]


def get_investor(investor_id):
    with db() as conn:
        r = conn.execute("SELECT * FROM investors WHERE id = ?", (investor_id,)).fetchone()
        return dict(r) if r else None


# ----------------------------------------------------------------------------
# Quarters
# ----------------------------------------------------------------------------
def add_quarter(label, start_date, end_date, is_active=0):
    with db() as conn:
        if is_active:
            conn.execute("UPDATE quarters SET is_active = 0")
        cur = conn.execute(
            "INSERT INTO quarters (label, start_date, end_date, is_active) VALUES (?,?,?,?)",
            (label, start_date, end_date, int(is_active)),
        )
        return cur.lastrowid


def update_quarter(quarter_id, **fields):
    allowed = {"label", "start_date", "end_date"}
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not sets:
        return
    cols = ", ".join(f"{k} = ?" for k in sets)
    with db() as conn:
        conn.execute(f"UPDATE quarters SET {cols} WHERE id = ?", (*sets.values(), quarter_id))


def delete_quarter(quarter_id):
    """Delete a quarter. Positions for it are removed via ON DELETE CASCADE.
    Shared price_history is left intact."""
    with db() as conn:
        conn.execute("DELETE FROM quarters WHERE id = ?", (quarter_id,))


def set_active_quarter(quarter_id):
    with db() as conn:
        conn.execute("UPDATE quarters SET is_active = 0")
        conn.execute("UPDATE quarters SET is_active = 1 WHERE id = ?", (quarter_id,))


def list_quarters():
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM quarters ORDER BY start_date")]


def get_quarter(quarter_id):
    with db() as conn:
        r = conn.execute("SELECT * FROM quarters WHERE id = ?", (quarter_id,)).fetchone()
        return dict(r) if r else None


def get_active_quarter():
    with db() as conn:
        r = conn.execute(
            "SELECT * FROM quarters WHERE is_active = 1 ORDER BY start_date DESC LIMIT 1"
        ).fetchone()
        if not r:
            r = conn.execute("SELECT * FROM quarters ORDER BY start_date DESC LIMIT 1").fetchone()
        return dict(r) if r else None


# ----------------------------------------------------------------------------
# Positions
# ----------------------------------------------------------------------------
def upsert_position(investor_id, quarter_id, ticker, yahoo_symbol, buy_price, buy_date, currency="NOK"):
    with db() as conn:
        conn.execute(
            """INSERT INTO positions
                 (investor_id, quarter_id, ticker, yahoo_symbol, buy_price, buy_date, currency)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(investor_id, quarter_id) DO UPDATE SET
                 ticker=excluded.ticker, yahoo_symbol=excluded.yahoo_symbol,
                 buy_price=excluded.buy_price, buy_date=excluded.buy_date,
                 currency=excluded.currency""",
            (investor_id, quarter_id, ticker, yahoo_symbol, buy_price, buy_date, currency),
        )


def delete_position(position_id):
    with db() as conn:
        conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))


def list_positions(quarter_id):
    with db() as conn:
        rows = conn.execute(
            """SELECT p.*, i.name, i.photo, i.color, i.tagline, i.is_benchmark
               FROM positions p JOIN investors i ON i.id = p.investor_id
               WHERE p.quarter_id = ?""",
            (quarter_id,),
        )
        return [dict(r) for r in rows]


# ----------------------------------------------------------------------------
# Price history
# ----------------------------------------------------------------------------
def store_prices(yahoo_symbol, series):
    """Store real daily closes. series: list of (date_str, close_float)."""
    with db() as conn:
        conn.executemany(
            """INSERT INTO price_history (yahoo_symbol, date, close, is_synthetic)
               VALUES (?,?,?,0)
               ON CONFLICT(yahoo_symbol, date) DO UPDATE SET
                 close=excluded.close, is_synthetic=0""",
            [(yahoo_symbol, d, float(c)) for d, c in series],
        )


def get_prices(yahoo_symbol, start=None, end=None):
    q = "SELECT date, close, is_synthetic FROM price_history WHERE yahoo_symbol = ?"
    args = [yahoo_symbol]
    if start:
        q += " AND date >= ?"
        args.append(start)
    if end:
        q += " AND date <= ?"
        args.append(end)
    q += " ORDER BY date"
    with db() as conn:
        return [dict(r) for r in conn.execute(q, args)]


def clear_prices(yahoo_symbol):
    with db() as conn:
        conn.execute("DELETE FROM price_history WHERE yahoo_symbol = ?", (yahoo_symbol,))


def clear_synthetic_prices():
    """Purge any legacy fabricated rows. Returns the number deleted."""
    with db() as conn:
        cur = conn.execute("DELETE FROM price_history WHERE is_synthetic = 1")
        return cur.rowcount
