// Captures README screenshots from the static build: `npm run build && npm run screenshots`.
import { spawn } from "node:child_process";
import { chromium } from "@playwright/test";

const OUT = "../docs/screenshots";
const server = spawn("npx", ["serve", "out", "-l", "4174", "--no-clipboard"], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 2500));
const base = "http://localhost:4174";
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: "light", deviceScaleFactor: 2 });
  await page.goto(`${base}/`);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/overview.png`, fullPage: true });
  await page.goto(`${base}/experiments/model-sweep/`);
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/experiment.png`, fullPage: true });
  const index = await (await fetch(`${base}/data/experiments/model-sweep.json`)).json();
  const id = (label) => index.runs.find((r) => r.label === label).run_id;
  const url = `${base}/compare/?base=${id("model=claude-sonnet-5-5")}&cand=${id("model=claude-haiku-5-5")}&exp=model-sweep`;
  await page.goto(url);
  await page.getByRole("heading", { name: "Verdict" }).waitFor();
  await page.screenshot({ path: `${OUT}/compare.png`, fullPage: true });
  await page.locator("main ul li button").first().click();
  await page.getByRole("dialog").waitFor();
  await page.screenshot({ path: `${OUT}/case-drawer.png` });
  const phone = await browser.newPage({ viewport: { width: 375, height: 812 }, colorScheme: "dark", deviceScaleFactor: 2 });
  await phone.goto(url);
  await phone.getByRole("heading", { name: "Verdict" }).waitFor();
  await phone.screenshot({ path: `${OUT}/mobile.png` });
} finally {
  await browser.close();
  server.kill();
}
