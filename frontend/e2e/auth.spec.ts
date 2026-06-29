import { test, expect } from "@playwright/test";
// E2E smoke. Requires backend on :8000 (seeded) and frontend dev server on :5173.
test("703 admin logs in and reaches the dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/access code/i).fill("ADMIN703");
  await page.getByRole("button", { name: /log in/i }).click();
  await expect(page.getByRole("heading", { name: /Dashboard/i })).toBeVisible();
});

test("curriculum and reports load", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/access code/i).fill("ADMIN703");
  await page.getByRole("button", { name: /log in/i }).click();
  await page.getByRole("link", { name: /Curriculum/i }).click();
  await expect(page.getByText(/single source of schedulable items/i)).toBeVisible();
  await page.getByRole("link", { name: /Reports/i }).click();
  await expect(page.getByText(/Training summary/i)).toBeVisible();
});

test("invalid login shows an error and does not enter", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/access code/i).fill("WRONGCODE");
  await page.getByRole("button", { name: /log in/i }).click();
  await expect(page.getByRole("alert")).toBeVisible();
});
