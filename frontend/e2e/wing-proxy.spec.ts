import { test, expect } from "@playwright/test";
// Wing Admin proxy workflow. Requires seeded ADMIN7WG.
test("wing admin can enter and exit proxy mode", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/access code/i).fill("ADMIN7WG");
  await page.getByRole("button", { name: /log in/i }).click();
  await expect(page.getByRole("heading", { name: /Wing Overview/i })).toBeVisible();
  await page.getByLabel(/Squadron/i).selectOption({ index: 1 });
  await page.getByPlaceholder(/Reason/i).fill("Assisting squadron with planning");
  await page.getByRole("button", { name: /Enter proxy mode/i }).click();
  await expect(page.getByText(/PROXY MODE ACTIVE/i)).toBeVisible();
  await page.getByRole("button", { name: /Exit proxy mode/i }).click();
});
