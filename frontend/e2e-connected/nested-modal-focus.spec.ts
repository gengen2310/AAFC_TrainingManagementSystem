import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// PR #65 review T15 (P2): openModal/closeModal kept ONE return-focus slot.
// Opening a confirm from inside a dialog overwrote the dialog's opener; closing
// the confirm then skipped restoration (target inside a still-open dialog) so
// focus fell to <body>, and closing the dialog restored nothing. Keyboard and
// screen-reader users lost their place twice.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function login(page: Page) {
  if (LOCAL_API_BASE) await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

const activeId = (page: Page) => page.evaluate(() => {
  const a = document.activeElement as HTMLElement | null;
  if (!a) return null;
  // The dialog that holds focus, else the focused element itself.
  return a.closest(".modal-bg")?.id || a.id || a.tagName;
});

test("closing a nested confirm keeps focus in the parent dialog, then returns it to the original opener", async ({ page }) => {
  await login(page);
  await page.evaluate(() => {
    const b = document.createElement("button");
    b.id = "t15-opener"; b.textContent = "Open dialog";
    b.onclick = () => (window as any).openModal("m-cea-import");
    document.getElementById("app")!.prepend(b);
  });
  await page.locator("#t15-opener").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#m-cea-import")).toHaveClass(/active/);
  await expect.poll(() => activeId(page)).toBe("m-cea-import");     // focus moved into the dialog

  // Nested confirm opened from inside the dialog, dismissed with the keyboard.
  await page.locator("#m-cea-import .modal-x").focus();
  await page.evaluate(() => (window as any).confirmAction("Discard?", () => {}));
  await expect(page.locator("#m-confirm")).toHaveClass(/active/);
  await expect.poll(() => activeId(page)).toBe("m-confirm");
  await page.locator("#m-confirm .modal-x").click();
  await expect(page.locator("#m-confirm")).not.toHaveClass(/active/);
  await expect(page.locator("#m-cea-import")).toHaveClass(/active/);
  await expect.poll(() => activeId(page), { message: "focus must stay inside the parent dialog" }).toBe("m-cea-import");

  await page.evaluate(() => (window as any).closeModal("m-cea-import"));
  await expect.poll(() => activeId(page), { message: "focus must return to the original opener" }).toBe("t15-opener");
});

test("Escape closes the most recently opened dialog even when it comes first in the markup", async ({ page }) => {
  await login(page);
  // An outer dialog placed AFTER #m-confirm in the markup, so DOM order and
  // open order disagree.
  const outer = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll(".modal-bg")) as HTMLElement[];
    const ci = all.findIndex((m) => m.id === "m-confirm");
    return all.slice(ci + 1).find((m) => m.id && m.querySelector(".modal-x"))!.id;
  });
  await page.evaluate((id) => (window as any).openModal(id), outer);
  await page.evaluate(() => (window as any).confirmAction("Discard?", () => {}));
  await expect(page.locator("#m-confirm")).toHaveClass(/active/);
  await page.keyboard.press("Escape");
  await expect(page.locator("#m-confirm")).not.toHaveClass(/active/);
  await expect(page.locator(`#${outer}`), "Escape must close only the inner confirm").toHaveClass(/active/);
});
