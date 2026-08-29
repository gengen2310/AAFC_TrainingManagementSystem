import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const B = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => { await resetBackendRateLimits(B!); });

async function toCodeStep(page: Page) {
  await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, B);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await expect(page.locator("#auth-code")).toBeVisible();
}

test("the sign-in screen offers a way back in", async ({ page }) => {
  await toCodeStep(page);
  const link = page.locator("#auth-forgot-btn");
  await expect(link).toBeVisible();
  await expect(link).toHaveText("Forgot access code?");
  const box = (await link.boundingBox())!;
  expect(Math.round(box.height), "44px touch target").toBeGreaterThanOrEqual(44);
});

test("the recovery message is identical whether or not the account exists", async ({ page }) => {
  // The backend is enumeration-resistant; the UI must not undo that by
  // rendering a different message for a miss.
  const said: string[] = [];
  for (const addr of ["definitely-not-a-user@example.invalid", "sysadmin@example.com"]) {
    await toCodeStep(page);
    await page.locator("#auth-forgot-btn").click();
    await expect(page.locator("#auth-forgot")).toBeVisible();
    await page.locator("#forgot-email").fill(addr);
    await page.locator("#forgot-btn").click();
    await expect(page.locator("#forgot-note")).not.toBeEmpty();
    said.push(((await page.locator("#forgot-note").textContent()) || "").trim());
  }
  expect(new Set(said).size, said.join(" || ")).toBe(1);
  expect(said[0]).toContain("If an eligible account matches");
});

test("the recovery screens never claim an account does not exist", async ({ page }) => {
  await toCodeStep(page);
  await page.locator("#auth-forgot-btn").click();
  await page.locator("#forgot-email").fill("nobody@example.invalid");
  await page.locator("#forgot-btn").click();
  await page.waitForTimeout(400);
  const text = ((await page.locator("#auth-forgot").textContent()) || "").toLowerCase();
  for (const leak of ["no account", "not found", "does not exist", "unknown account", "no such"]) {
    expect(text, `leaks "${leak}"`).not.toContain(leak);
  }
});

test("an invalid recovery code is refused without explaining why", async ({ page }) => {
  await toCodeStep(page);
  await page.locator("#auth-forgot-btn").click();
  await page.locator("#forgot-email").fill("someone@example.invalid");
  await page.locator("#forgot-btn").click();
  await expect(page.locator("#auth-reset")).toBeVisible({ timeout: 6000 });

  await page.locator("#reset-token").fill("not-a-real-token");
  await page.locator("#reset-new").fill("A-Perfectly-Fine-Code-2027");
  await page.locator("#reset-btn").click();
  await expect(page.locator("#reset-note")).toContainText("not valid");
  const note = ((await page.locator("#reset-note").textContent()) || "").toLowerCase();
  // "expired" vs "already used" vs "unknown" would each be a small oracle.
  for (const leak of ["expired", "already used", "consumed", "unknown"]) {
    expect(note, `distinguishes "${leak}"`).not.toContain(leak);
  }
});

test("a short access code is refused before anything is sent", async ({ page }) => {
  await toCodeStep(page);
  await page.locator("#auth-forgot-btn").click();
  await page.locator("#forgot-email").fill("someone@example.invalid");
  await page.locator("#forgot-btn").click();
  await expect(page.locator("#auth-reset")).toBeVisible({ timeout: 6000 });

  let posted = false;
  page.on("request", (r) => { if (r.url().includes("/reset-code")) posted = true; });
  await page.locator("#reset-token").fill("whatever");
  await page.locator("#reset-new").fill("short");
  await page.locator("#reset-btn").click();
  await expect(page.locator("#reset-note")).toContainText("at least 8 characters");
  expect(posted, "must not call the API with a code it already knows is invalid").toBe(false);
});
