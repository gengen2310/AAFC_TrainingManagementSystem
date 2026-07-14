import { test, expect } from "@playwright/test";

// ── Navigation and route coverage ────────────────────────────────────────────
// Tests that major nav routes load and render their page heading.
// Requires backend on :8000 seeded with 703 demo data.

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN703");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("Curriculum page loads", async ({ page }) => {
  await page.goto("/curriculum");
  await expect(page.getByRole("heading", { name: /curriculum/i })).toBeVisible({ timeout: 8000 });
});

test("Parade Nights page loads", async ({ page }) => {
  await page.goto("/parade-nights");
  await expect(page.getByRole("heading", { name: /parade night/i })).toBeVisible({ timeout: 8000 });
});

test("Mission Backlog (Action Items) page loads", async ({ page }) => {
  await page.goto("/action-items");
  await expect(page.getByRole("heading", { name: /mission backlog|action item/i })).toBeVisible({ timeout: 8000 });
});

test("Imports page loads", async ({ page }) => {
  await page.goto("/imports");
  await expect(page.getByRole("heading", { name: /import|activities/i })).toBeVisible({ timeout: 8000 });
});

test("Facilitators page loads", async ({ page }) => {
  await page.goto("/facilitators");
  await expect(page.getByRole("heading", { name: /facilitator/i })).toBeVisible({ timeout: 8000 });
});

test("Resources page loads", async ({ page }) => {
  await page.goto("/resources");
  await expect(page.getByRole("heading", { name: /resource|training area|equipment/i })).toBeVisible({ timeout: 8000 });
});

test("Weekly Program page loads", async ({ page }) => {
  await page.goto("/weekly-program");
  await expect(page.getByRole("heading", { name: /weekly program/i })).toBeVisible({ timeout: 8000 });
});

test("Calendar page loads", async ({ page }) => {
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { name: /calendar/i })).toBeVisible({ timeout: 8000 });
});

test("read-only role (sqn_general) cannot see admin controls", async ({ page }) => {
  // Log out and back in as general user
  await page.getByRole("button", { name: /log out|sign out/i }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  await page.getByLabel("Access code").fill("703SQN2026");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.goto("/parade-nights");
  // Admin create button should not exist for sqn_general
  await expect(page.getByRole("button", { name: /create.*parade|add.*night/i })).not.toBeVisible();
});
