// Capture every dashboard page against a running API + dashboard with real data.
//
//   DASHBOARD_URL=http://127.0.0.1:3000 AGENTTAINT_APPROVER_TOKEN=... \
//     node scripts/screenshots.mjs [outDir] [--video]
//
// The approver token is read from the environment and typed into the approval
// screen exactly as a person would; it is never written to disk or logged.
import { mkdirSync, readdirSync, renameSync } from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const base = process.env.DASHBOARD_URL || "http://127.0.0.1:3000";
const args = process.argv.slice(2);
const outDir = path.resolve(args.find((a) => !a.startsWith("--")) || "../../docs/screenshots");
const video = args.includes("--video");
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined,
});
const context = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
  deviceScaleFactor: 1,
  ...(video ? { recordVideo: { dir: outDir, size: { width: 1600, height: 1000 } } } : {}),
});
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(video ? ms : Math.min(ms, 600));

async function shot(name) {
  await pause(900);
  await page.screenshot({ path: path.join(outDir, `${name}.png`) });
  console.log(`saved ${name}.png`);
}

// Overview: seed through the real gateway first.
await page.goto(`${base}/`);
await page.getByRole("button", { name: /Seed demo session/ }).click();
await page.waitForSelector(".kpi-value");
await page.waitForFunction(() => document.querySelectorAll(".data-table tbody tr").length > 3);
await shot("01-overview");

await page.goto(`${base}/provenance`);
await page.waitForSelector("[data-node]");
await shot("02-provenance-trace");
await page.locator('[aria-label^="action email.send"]').first().click();
await shot("03-provenance-selected-action");
await page.getByRole("button", { name: /All traces/ }).click();
await page.waitForSelector("[data-node]");
await page.getByLabel("Zoom in").click();
await shot("04-provenance-all-traces");

await page.goto(`${base}/audit`);
await page.waitForSelector(".data-table tbody tr");
await shot("05-audit");

await page.goto(`${base}/confirmations`);
await shot("06-confirmations-locked");
const token = process.env.AGENTTAINT_APPROVER_TOKEN;
if (token) {
  await page.getByLabel("Approver token").fill(token);
  await page.getByRole("button", { name: "Unlock approvals" }).click();
  await page.waitForSelector(".confirm-item, .empty");
  await shot("07-confirmations-queue");
  const approve = page.getByRole("button", { name: "Approve once" }).first();
  if (await approve.count()) {
    await approve.click();
    await page.waitForSelector(".confirm-log li");
    await shot("08-confirmations-approved");
  }
} else {
  console.log("AGENTTAINT_APPROVER_TOKEN not set: skipped unlocked approval screenshots");
}

for (const [route, name] of [
  ["/reconstruction", "09-reconstruction"],
  ["/gateway", "10-gateway"],
  ["/benchmarks", "11-benchmarks"],
]) {
  await page.goto(`${base}${route}`);
  await page.waitForLoadState("networkidle");
  await shot(name);
}

await context.close();
await browser.close();
if (video) {
  const webm = readdirSync(outDir).filter((f) => f.endsWith(".webm"));
  if (webm.length) renameSync(path.join(outDir, webm[0]), path.join(outDir, "walkthrough.webm"));
}
