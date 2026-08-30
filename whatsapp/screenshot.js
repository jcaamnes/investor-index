#!/usr/bin/env node
"use strict";
/**
 * Renders the live dashboard at a phone-width viewport and screenshots just
 * "The Standings" panel (#standingsPanel in templates/index.html). At this
 * width the site's own responsive CSS already drops the columns that don't
 * fit a phone (Buy/Last/Gap/Days#1/Vol — see the @media(max-width:640px)
 * block in index.html), so the result reads cleanly on a phone screen
 * without any extra cropping logic here.
 *
 * Usage: node screenshot.js <url> <outPath> [widthPx]
 */

const puppeteer = require("puppeteer");

async function main() {
  const [url, outPath, widthArg] = process.argv.slice(2);
  if (!url || !outPath) {
    throw new Error("Usage: node screenshot.js <url> <outPath> [widthPx]");
  }
  const width = parseInt(widthArg, 10) || 430; // iPhone-ish mobile width, comfortably under the 640px breakpoint

  const browser = await puppeteer.launch({ headless: "new", channel: "chrome" });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width, height: 900, deviceScaleFactor: 3 });
    await page.goto(url, { waitUntil: "networkidle0", timeout: 45000 });
    await page.waitForSelector("#boardBody tr", { timeout: 20000 });
    // brief settle so web fonts / the just-rendered table have painted
    await new Promise((r) => setTimeout(r, 400));
    const el = await page.$("#standingsPanel");
    if (!el) {
      throw new Error("Could not find #standingsPanel on the page — did templates/index.html change?");
    }
    await el.screenshot({ path: outPath });
    console.log("OK   Screenshot saved: " + outPath);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("FAIL Screenshot: " + (err && err.message ? err.message : err));
  process.exit(1);
});
