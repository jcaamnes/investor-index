#!/usr/bin/env node
"use strict";
/**
 * One-time interactive WhatsApp login for the Stocks Elite auto-post feature.
 *
 * Run this once (double-click ../whatsapp_login.command, or `node setup.js`
 * from this folder). It shows a QR code — scan it with WhatsApp on your
 * phone (Settings > Linked Devices > Link a Device) — then joins the group
 * from push_config.json's "whatsapp.group_invite" link and caches the
 * resulting group id in state.json. The session itself is saved under
 * .wwebjs_auth/ so later runs of send_update.js don't need to re-scan.
 *
 * Re-run this only if you unlink the device on your phone, or if
 * send_update.js reports the session is disconnected.
 */

const fs = require("fs");
const path = require("path");
const qrcode = require("qrcode-terminal");
const { Client, LocalAuth } = require("whatsapp-web.js");

const HERE = __dirname;
const STATE_PATH = path.join(HERE, "state.json");
const CONFIG_PATH = path.join(HERE, "..", "push_config.json");

function loadInviteLink() {
  let cfg = {};
  try {
    cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
  } catch (e) {
    // fall through — handled below by the missing-link check
  }
  const link = (cfg.whatsapp && cfg.whatsapp.group_invite) || process.env.WHATSAPP_GROUP_INVITE;
  if (!link) {
    console.error(
      "No WhatsApp group invite link configured.\n" +
        "Add it to push_config.json next to push_gui.py, e.g.:\n" +
        '  "whatsapp": {"enabled": true, "group_invite": "https://chat.whatsapp.com/XXXX"}'
    );
    process.exit(1);
  }
  return link;
}

function inviteCodeFrom(link) {
  const m = link.match(/chat\.whatsapp\.com\/([A-Za-z0-9]+)/);
  if (!m) {
    console.error(`Could not find an invite code in: ${link}`);
    process.exit(1);
  }
  return m[1];
}

async function resolveGroup(client, inviteCode) {
  // The normal path: join the group via the invite link.
  try {
    const chat = await client.acceptInvite(inviteCode);
    return { id: chat.id._serialized, name: chat.name || null };
  } catch (err) {
    console.log(
      "acceptInvite didn't succeed directly (" +
        (err && err.message ? err.message : err) +
        "). This usually means this WhatsApp account is already a member " +
        "— looking the group up instead…"
    );
  }
  // Fallback: this account is likely already in the group. getInviteInfo
  // resolves the group id from the invite code without requiring a fresh
  // join.
  const info = await client.getInviteInfo(inviteCode);
  const id = info && info.id && (info.id._serialized || info.id);
  if (!id) {
    throw new Error("Could not resolve a group id from the invite link.");
  }
  let name = null;
  try {
    const chat = await client.getChatById(id);
    name = chat.name || null;
  } catch (_) {
    // non-fatal — we still have the id
  }
  return { id, name };
}

async function main() {
  const inviteLink = loadInviteLink();
  const inviteCode = inviteCodeFrom(inviteLink);

  console.log("Stocks Elite — WhatsApp one-time setup");
  console.log("Scan this QR code with WhatsApp on your phone:");
  console.log("  WhatsApp app > Settings > Linked Devices > Link a Device\n");

  const client = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(HERE, ".wwebjs_auth") }),
    puppeteer: { headless: true, channel: "chrome" },
  });

  client.on("qr", (qr) => qrcode.generate(qr, { small: true }));
  client.on("authenticated", () => console.log("\nAuthenticated. Finishing sign-in…"));
  client.on("auth_failure", (msg) => {
    console.error("Authentication failed:", msg);
    process.exit(1);
  });

  client.on("ready", async () => {
    console.log("Signed in as", client.info.pushname || client.info.wid.user);
    try {
      const group = await resolveGroup(client, inviteCode);
      fs.writeFileSync(
        STATE_PATH,
        JSON.stringify({ groupId: group.id, groupName: group.name }, null, 2)
      );
      console.log(`Joined/found the group: ${group.name || group.id}`);
      console.log("Saved group id to", STATE_PATH);
      console.log("\nSetup complete. push_gui.py can now post to WhatsApp automatically.");
    } catch (err) {
      console.error("Setup failed:", err && err.message ? err.message : err);
      process.exitCode = 1;
    } finally {
      await client.destroy();
      process.exit(process.exitCode || 0);
    }
  });

  client.initialize();
}

main();
