#!/usr/bin/env node
"use strict";
/**
 * Headless sender: post one image + caption to the WhatsApp group cached in
 * state.json by setup.js. Called by push_gui.py after a successful price
 * push; not meant to be run interactively (no QR code — if the session
 * isn't authenticated yet, this exits with an error telling you to run
 * setup.js first).
 *
 * Usage: node send_update.js <imagePath> [caption]
 */

const fs = require("fs");
const path = require("path");
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");

const HERE = __dirname;
const STATE_PATH = path.join(HERE, "state.json");

function fail(msg) {
  console.error("FAIL " + msg);
  process.exit(1);
}

async function main() {
  const [imagePath, caption] = process.argv.slice(2);
  if (!imagePath) fail("Usage: node send_update.js <imagePath> [caption]");
  if (!fs.existsSync(imagePath)) fail(`Image not found: ${imagePath}`);

  let state;
  try {
    state = JSON.parse(fs.readFileSync(STATE_PATH, "utf8"));
  } catch (e) {
    fail('No whatsapp/state.json found — run "node whatsapp/setup.js" once first.');
    return;
  }
  if (!state.groupId) {
    fail("whatsapp/state.json has no groupId — re-run whatsapp/setup.js.");
    return;
  }

  const client = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(HERE, ".wwebjs_auth") }),
    puppeteer: { headless: true, channel: "chrome" },
  });

  const readyTimeout = setTimeout(() => {
    fail(
      "Timed out waiting for the WhatsApp session to be ready. If your " +
        "phone unlinked this device, re-run whatsapp/setup.js."
    );
  }, 90000);

  client.on("auth_failure", (msg) => {
    clearTimeout(readyTimeout);
    fail("Auth failed: " + msg + " — re-run whatsapp/setup.js.");
  });
  client.on("disconnected", (reason) => {
    clearTimeout(readyTimeout);
    fail("Session disconnected (" + reason + ") — re-run whatsapp/setup.js.");
  });

  client.on("ready", async () => {
    clearTimeout(readyTimeout);
    try {
      const media = MessageMedia.fromFilePath(imagePath);
      await client.sendMessage(state.groupId, media, { caption: caption || "" });
      console.log("OK   WhatsApp message sent" + (state.groupName ? ` to "${state.groupName}"` : ""));
      await client.destroy();
      process.exit(0);
    } catch (err) {
      fail("Send failed: " + (err && err.message ? err.message : err));
    }
  });

  client.initialize();
}

main();
