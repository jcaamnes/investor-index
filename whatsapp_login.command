#!/bin/bash
# Stocks Elite — one-time WhatsApp login for push_gui.py's auto-post feature.
# Double-click this once. It installs the Node dependencies if needed, then
# shows a QR code right in this Terminal window — scan it with WhatsApp on
# your phone (Settings > Linked Devices > Link a Device). After that,
# push_gui.py can post updates to the group automatically; you won't need to
# run this again unless you unlink the device on your phone.

cd "$(dirname "$0")" || exit 1

if [ ! -d "whatsapp/node_modules" ]; then
  echo "Installing WhatsApp dependencies (one-time, needs internet)…"
  # This uses your already-installed Google Chrome instead of downloading a
  # separate copy of Chromium (which is large and sometimes blocked by
  # networks) — screenshot.js/setup.js/send_update.js all launch with
  # channel:"chrome" for the same reason. Install Chrome first if you don't
  # have it: https://www.google.com/chrome/
  (cd whatsapp && PUPPETEER_SKIP_DOWNLOAD=true npm install) || exit 1
fi

node whatsapp/setup.js

echo ""
echo "Done — you can close this window."
