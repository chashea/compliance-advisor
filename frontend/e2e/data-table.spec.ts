import { test, expect } from "@playwright/test";

test("eDiscovery page shows data table", async ({ page }) => {
  await page.goto("/ediscovery");
  await page.waitForTimeout(1500);
  // Should have a table
  const table = page.locator("table").first();
  await expect(table).toBeVisible();
});
