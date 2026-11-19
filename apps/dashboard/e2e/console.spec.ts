import { expect, test, type Page } from "@playwright/test";

const ROUTES: Array<[string, string]> = [
  ["/overview/", "Security overview"],
  ["/activity/", "Live activity"],
  ["/demo/", "Try your own text"],
  ["/provenance/", "Provenance"],
  ["/audit/", "Decisions"],
  ["/confirmations/", "Pending confirmations"],
  ["/reconstruction/", "Reconstruction"],
  ["/gateway/", "Security Gateway"],
  ["/benchmarks/", "Benchmark Lab"],
  ["/product/", "provenance firewall"],
];

function watch(page: Page) {
  const failed: string[] = [];
  const consoleErrors: string[] = [];
  page.on("response", (res) => {
    const url = res.url();
    if (!url.includes("/api/")) return;
    if (res.status() >= 400) failed.push(`${res.status()} ${url}`);
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  return { failed, consoleErrors };
}

test.describe("console", () => {
  test("loads each section from the API", async ({ page }, info) => {
    const seen = watch(page);
    for (const [path, heading] of ROUTES) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: new RegExp(heading, "i") }).first()).toBeVisible();
    }
    expect(seen.failed, seen.failed.join("\n")).toEqual([]);
    const noisy = seen.consoleErrors.filter((line) => !/favicon/i.test(line));
    expect(noisy, noisy.join("\n")).toEqual([]);
    if (info.project.name === "mobile") {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/overview/");
      await page.getByRole("button", { name: "Menu" }).click();
      await expect(page.getByRole("link", { name: "Live activity" })).toBeVisible();
    }
  });

  test("demo catalogue is not a false zero and runs real verdicts", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "execution is covered on desktop");
    const seen = watch(page);
    await page.goto("/demo/");
    await expect(page.getByText("Loading scenarios…")).toBeHidden();
    await expect(page.getByText("0 available")).toHaveCount(0);
    await expect(page.getByText(/\d+ available/)).toBeVisible();

    await page.getByRole("button", { name: "Prompt injection in an email" }).click();
    const block = page.getByTestId("demo-result").first();
    await expect(block.getByText("BLOCK").first()).toBeVisible();

    await page.getByRole("button", { name: "Legitimate request" }).click();
    await expect(page.getByTestId("demo-result").first().getByText("ALLOW").first()).toBeVisible();

    await page.getByRole("button", { name: "Suspicious request" }).click();
    await expect(page.getByTestId("demo-result").first().getByText("CONFIRM").first()).toBeVisible();

    expect(seen.failed.filter((line) => !line.includes(" 429 "))).toEqual([]);
  });

  test("audit filter empty state and benchmark catalogue", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "covered on desktop");
    await page.goto("/audit/");
    await page.getByLabel("Search").fill("zzz-no-such-call");
    await expect(page.getByText("No audit records match these filters.")).toBeVisible();

    await page.goto("/benchmarks/");
    await expect(page.getByText(/runnable · input fixtures only/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "External benchmarks" })).toBeVisible();
    await expect(page.getByText(/do not have a published attack-success/)).toBeVisible();
  });

  test("confirmations stay locked in the public demo", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "covered on desktop");
    await page.goto("/confirmations/");
    await expect(page.getByRole("heading", { name: /Approvals are locked/ })).toBeVisible();
  });
});
