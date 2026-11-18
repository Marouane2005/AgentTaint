// Screenshots of the product site and public demo.
//   SITE_URL=https://... node scripts/site_screenshots.mjs <outDir>
import { mkdirSync } from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const base = (process.env.SITE_URL || "http://127.0.0.1:8099").replace(/\/$/, "");
const outDir = path.resolve(process.argv[2] || "site-shots");
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const shot = async (name, full = false) => {
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: full });
  console.log(`saved ${name}.png`);
};

await page.goto(`${base}/`, { waitUntil: "networkidle", timeout: 180000 });
await page.waitForSelector(".hero h1");
await shot("01-landing");
await shot("02-landing-full", true);
await page.locator("#pricing").scrollIntoViewIfNeeded();
await page.evaluate(() => document.querySelector("#pricing")?.scrollIntoView());
await shot("03-pricing");

await page.goto(`${base}/demo/`, { waitUntil: "networkidle" });
await page.waitForSelector(".scenario-item");
await page.getByRole("button", { name: "Run test-atk-direct-01" }).click();
await page.waitForSelector('[data-testid="demo-result"]');
const benign = page.locator('button[aria-label^="Run test-ben"]').first();
if (await benign.count()) {
  await benign.click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="demo-result"]').length > 1);
}
await shot("04-demo-run-results");

await page.locator('[data-testid="demo-result"] a', { hasText: "View provenance" }).last().click();
await page.waitForSelector("[data-node]");
await shot("05-demo-provenance");

await page.goto(`${base}/overview/`, { waitUntil: "networkidle" });
await page.waitForSelector(".kpi-value");
await shot("06-demo-overview");

await page.goto(`${base}/confirmations/`, { waitUntil: "networkidle" });
await page.waitForSelector("text=Approvals are locked in the public demo");
await shot("07-demo-approvals-locked");

for (const [route, name] of [["limitations", "08-limitations"], ["terms", "09-terms"], ["privacy", "10-privacy"], ["refunds", "11-refunds"]]) {
  await page.goto(`${base}/${route}/`, { waitUntil: "networkidle" });
  await shot(name);
}
await browser.close();
