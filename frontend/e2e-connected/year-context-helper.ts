import { expect, type Page } from "@playwright/test";

/**
 * Select a materialised Planning Year through the same canonical setter used by
 * the current Main-TMS year menu. The retired #py-select no longer exists.
 *
 * The helper waits on canonical state (P.years / P.currentYearId) rather than
 * sleeping for a guessed duration, so cross-browser timing differences do not
 * turn into random failures.
 */
export async function selectConnectedPlanningYear(page: Page, requestedId?: string): Promise<string> {
  await page.evaluate("nav('activities')");

  await expect.poll(async () =>
    page.evaluate("Array.isArray(P.years) ? P.years.filter(y => y && y.materialised !== false && (y.id || y.planning_year_id)).length : 0"),
  { timeout: 10000, message: "materialised planning years did not load" }).toBeGreaterThan(0);

  const selectedId = await page.evaluate((wanted: string | undefined) => {
    const years = (P.years || []).filter((y: any) => y && y.materialised !== false && (y.id || y.planning_year_id));
    const idOf = (y: any) => String(y.id || y.planning_year_id || "");
    const target = wanted
      ? years.find((y: any) => idOf(y) === wanted)
      : years.find((y: any) => y.active_status) || years[0];
    if (!target) {
      throw new Error(wanted
        ? `Requested planning year ${wanted} is not present in P.years`
        : "No materialised planning year is available");
    }
    setCurrentYear(target);
    return idOf(target);
  }, requestedId);

  await expect.poll(async () =>
    page.evaluate("String(P.currentYearId || '')"),
  { timeout: 10000, message: `planning year ${selectedId} was not applied` }).toBe(selectedId);

  return selectedId;
}

/** Re-apply a known year after test data changes, failing if the year vanished. */
export async function refreshConnectedPlanningYear(page: Page, yearId: string): Promise<void> {
  await selectConnectedPlanningYear(page, yearId);
}
