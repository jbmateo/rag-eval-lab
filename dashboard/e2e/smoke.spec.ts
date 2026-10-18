import { expect, test } from "@playwright/test";

test("experiments → experiment → compare → case drawer", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/experiments/");
  // real lumen questions contain long unbreakable tokens (e-mail addresses); the overflow check below covers them
  const cards = page.locator("main ul li a");
  await expect(cards.first()).toBeVisible();
  // pick an experiment with at least two runs
  const count = await cards.count();
  let opened = false;
  for (let i = 0; i < count && !opened; i++) {
    const runs = Number(await cards.nth(i).locator("dd").first().innerText());
    if (runs >= 2) { await cards.nth(i).click(); opened = true; }
  }
  expect(opened).toBe(true);

  const expName = await page.getByRole("heading", { level: 1 }).innerText();
  const boxes = page.getByRole("checkbox", { name: /Select run/ });
  await expect(boxes.nth(1)).toBeVisible();
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByRole("link", { name: /Compare 2 runs/ }).click();

  await expect(page.getByRole("heading", { name: "Verdict" })).toBeVisible();
  // runs can be shared between experiments; the page must label them from the experiment we came from
  await expect(page.getByRole("link", { name: `← ${expName}` })).toBeVisible();
  await page.getByLabel("Status").selectOption("all");
  await page.locator("main ul li button").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByRole("heading", { name: "Expected evidence" })).toBeVisible();
  await expect(drawer.getByText(/^Baseline ·/)).toBeVisible();
  await expect(drawer.getByText(/^Candidate ·/)).toBeVisible();

  const [scrollWidth, innerWidth] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(scrollWidth).toBeLessThanOrEqual(innerWidth);
  expect(errors).toEqual([]);
});

test("overview: tiles, scoreboard and charts render; a scoreboard link opens its comparison", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hypothesis scoreboard" })).toBeVisible();
  await expect(page.locator("figure svg.recharts-surface").first()).toBeVisible();
  const [scrollWidth, innerWidth] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(scrollWidth).toBeLessThanOrEqual(innerWidth);
  await page.getByRole("link", { name: "Compare" }).first().click();
  await expect(page.getByRole("heading", { name: "Verdict" })).toBeVisible();
  expect(errors).toEqual([]);
});
