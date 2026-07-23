import { test, Page } from "@playwright/test";

// One-off evidence capture against live staging — not part of the regular verification
// suite. Run with: npx playwright test --config=playwright.connected.staging.config.ts e2e-connected/capture-screenshots.spec.ts
const OUT = "/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source/artifacts/final-beta-consolidation/d999623";

async function loginSquadron(page: Page, code: string, role: "sqn_admin" | "sqn_general" = "sqn_admin") {
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await page.locator(".ph-title", { hasText: "Training Dashboard" }).waitFor({ timeout: 10000 });
}

async function loginWing(page: Page, code: string) {
  await page.goto("/");
  await page.locator("#auth-type").selectOption("wing");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-role").selectOption("wing_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await page.waitForTimeout(2000);
}

async function loginNational(page: Page, code: string) {
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption({ index: 1 });
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await page.waitForTimeout(2000);
}

test("capture Main TMS screenshots", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${OUT}/dashboard.png`, fullPage: true });

  await page.evaluate(() => (window as any).nav("parade-nights"));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/parade-nights.png`, fullPage: true });

  await page.getByRole("button", { name: "Generate Parade Nights" }).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/parade-night-generator.png` });
  await page.locator("#m-gen-dates .modal-x").click();

  await page.evaluate(() => (window as any).nav("activities"));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/activities.png`, fullPage: true });

  await page.getByRole("button", { name: "+ Add Holiday" }).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/add-holiday.png` });
  await page.locator("#m-add-holiday button", { hasText: "Cancel" }).click();

  await page.evaluate(() => (window as any).nav("facilitators"));
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/facilitators.png`, fullPage: true });

  await page.evaluate(() => (window as any).nav("curriculum"));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/curriculum.png`, fullPage: true });

  await page.evaluate(() => (window as any).nav("resources"));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/resources-training-areas.png`, fullPage: true });

  // Desktop nav
  await page.screenshot({ path: `${OUT}/desktop-navigation.png` });
});

test("capture mobile navigation screenshot", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginSquadron(page, "ADMIN703");
  await page.locator("#btn-hamburger").click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/mobile-navigation.png` });
});

test("capture Mission Backlog (Planning Workspace drawer)", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  const pwLinkHref = await page.locator("#nav-pw-link").getAttribute("href");
  await page.goto(pwLinkHref!);
  await page.waitForTimeout(2000);
  const activitiesBtn = page.getByRole("button", { name: "Activities" }).last();
  if (await activitiesBtn.count()) {
    await activitiesBtn.click();
    await page.waitForTimeout(500);
    const missionBacklogTab = page.getByText("Mission Backlog", { exact: true });
    if (await missionBacklogTab.count()) {
      await missionBacklogTab.click();
      await page.waitForTimeout(500);
    }
  }
  await page.screenshot({ path: `${OUT}/mission-backlog.png`, fullPage: true });
  await page.screenshot({ path: `${OUT}/planning-workspace.png` });
});

test("capture wing dashboard", async ({ page }) => {
  await loginWing(page, "ADMIN7WG");
  await page.screenshot({ path: `${OUT}/wing-dashboard.png`, fullPage: true });
});

test("capture national dashboard", async ({ page }) => {
  await loginNational(page, "ADMINNATIONAL");
  await page.screenshot({ path: `${OUT}/national-dashboard.png`, fullPage: true });
});
