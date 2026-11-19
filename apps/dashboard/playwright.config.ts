import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.DASHBOARD_URL || "http://127.0.0.1:8080";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL,
    trace: "off",
    ...devices["Desktop Chrome"],
    channel: process.env.PLAYWRIGHT_CHROME_CHANNEL || "chrome",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
});
