#!/bin/bash
# Investor Index — open the price-updater page in your browser.
# Double-click this file in Finder. A browser tab opens with an "Update Prices"
# button. Keep this small Terminal window open while you use it; close it (or
# press Ctrl-C) when you're done.

cd "$(dirname "$0")" || exit 1

if [ -x "./.venv/bin/python" ]; then
  PY="./.venv/bin/python"
else
  PY="python3"
fi

"$PY" push_gui.py
