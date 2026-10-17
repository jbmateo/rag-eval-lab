import { expect, test } from "@playwright/test";

test("experiments → experiment → compare → case drawer", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/");
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

  const boxes = page.getByRole("checkbox", { name: /Select run/ });
  await expect(boxes.nth(1)).toBeVisible();
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByRole("link", { name: /Compare 2 runs/ }).click();

  await expect(page.getByRole("heading", { name: "Verdict" })).toBeVisible();
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
