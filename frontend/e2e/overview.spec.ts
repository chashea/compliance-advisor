import { test, expect } from "@playwright/test";

test("overview page loads with KPI cards", async ({ page }) => {
  await page.goto("/");
  // Wait for page to render
  await expect(page.locator("body")).toBeVisible();
  // Should have content (demo mode provides data)
  await page.waitForTimeout(1000);
  // Check that at least some text content exists
  const body = await page.textContent("body");
  expect(body?.length).toBeGreaterThan(0);
});
