"""Tests for the yfinance-based price fetching layer (fetch_prices.py).

These tests do NOT hit the network. They install a tiny fake `yfinance` module
into sys.modules whose `download()` returns canned pandas DataFrames, so we
exercise our parsing/error handling without touching Yahoo.

Run from the project root:

    python -m pytest tests/test_fetch.py -q      # if pytest is installed
    python tests/test_fetch.py                   # plain-stdlib fallback runner
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_prices  # noqa: E402

try:
    import pandas as pd
    _HAVE_PANDAS = True
except Exception:
    _HAVE_PANDAS = False


def _install_fake_yf(download_fn):
    """Put a fake yfinance module in sys.modules for the duration of a test."""
    fake = types.ModuleType("yfinance")
    fake.download = download_fn
    sys.modules["yfinance"] = fake


def _frame(rows):
    """Build a DataFrame with a DatetimeIndex and a Close column from
    [(date_str, close)] rows."""
    idx = pd.to_datetime([d for d, _ in rows])
    return pd.DataFrame({"Close": [c for _, c in rows]}, index=idx)


def test_parses_closes():
    if not _HAVE_PANDAS:
        return  # skip silently when pandas isn't present
    _install_fake_yf(lambda *a, **k: _frame(
        [("2026-04-01", 10.0), ("2026-04-02", 11.0), ("2026-04-03", 12.5)]))
    rows, reason = fetch_prices.fetch_quotes("AAPL", "2026-04-01", "2026-04-03")
    assert reason == "ok"
    assert rows[0] == ("2026-04-01", 10.0)
    assert rows[-1] == ("2026-04-03", 12.5)


def test_skips_nan_closes():
    if not _HAVE_PANDAS:
        return
    import numpy as np
    _install_fake_yf(lambda *a, **k: _frame(
        [("2026-04-01", 10.0), ("2026-04-02", np.nan), ("2026-04-03", 12.0)]))
    rows, _ = fetch_prices.fetch_quotes("AAPL", "2026-04-01", "2026-04-03")
    assert [c for _, c in rows] == [10.0, 12.0]


def test_empty_frame_is_no_data():
    if not _HAVE_PANDAS:
        return
    _install_fake_yf(lambda *a, **k: pd.DataFrame())
    rows, reason = fetch_prices.fetch_quotes("NOPE", "2026-04-01", "2026-04-03")
    assert rows is None
    assert "no data" in reason


def test_rate_limit_error():
    def _boom(*a, **k):
        raise Exception("YFRateLimitError: Too Many Requests. Rate limited. 429")
    _install_fake_yf(_boom)
    rows, reason = fetch_prices.fetch_quotes("AAPL", "2026-04-01", "2026-04-03")
    assert rows is None
    assert "429" in reason


def test_generic_yfinance_error():
    def _boom(*a, **k):
        raise ValueError("something odd")
    _install_fake_yf(_boom)
    rows, reason = fetch_prices.fetch_quotes("AAPL", "2026-04-01", "2026-04-03")
    assert rows is None
    assert "yfinance error" in reason


def test_yfinance_not_installed(monkeypatch):
    # Simulate yfinance being absent: block the import.
    import builtins
    real_import = builtins.__import__

    def _no_yf(name, *a, **k):
        if name == "yfinance":
            raise ImportError("No module named 'yfinance'")
        return real_import(name, *a, **k)

    sys.modules.pop("yfinance", None)
    monkeypatch.setattr(builtins, "__import__", _no_yf)
    rows, reason = fetch_prices.fetch_quotes("AAPL", "2026-04-01", "2026-04-03")
    assert rows is None
    assert "not installed" in reason


def test_fetch_yahoo_alias_exists():
    # Older scripts import fetch_yahoo; it must still resolve to fetch_quotes.
    assert fetch_prices.fetch_yahoo is fetch_prices.fetch_quotes


def test_history_fallback_when_download_empty():
    # When download() yields nothing, fetch_quotes should fall back to the
    # Ticker.history() path and still return real closes.
    if not _HAVE_PANDAS:
        return

    class _FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, *a, **k):
            return _frame([("2026-04-01", 7.5), ("2026-04-02", 8.0)])

    fake = types.ModuleType("yfinance")
    fake.download = lambda *a, **k: pd.DataFrame()  # empty -> triggers fallback
    fake.Ticker = _FakeTicker
    sys.modules["yfinance"] = fake

    rows, reason = fetch_prices.fetch_quotes("MOBA.OL", "2026-04-01", "2026-04-02")
    assert reason == "ok"
    assert rows[-1] == ("2026-04-02", 8.0)


# ---------------------------------------------------------------------------
# Minimal stdlib runner so the file works even without pytest installed.
# ---------------------------------------------------------------------------
class _MonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, obj, name, value):
        self._undo.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, old in reversed(self._undo):
            setattr(obj, name, old)
        self._undo.clear()


def _run_plain():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    passed = 0
    for name, fn in tests:
        mp = _MonkeyPatch()
        sys.modules.pop("yfinance", None)
        try:
            argcount = fn.__code__.co_argcount
            if "monkeypatch" in fn.__code__.co_varnames[:argcount]:
                fn(mp)
            else:
                fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
        finally:
            mp.undo()
            sys.modules.pop("yfinance", None)
    print(f"\n{passed}/{len(tests)} tests passed.")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_plain() else 1)
