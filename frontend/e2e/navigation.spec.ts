import { test, expect } from "@playwright/test";

const pages = [
  { path: "/", heading: /overview|compliance/i },
  { path: "/labels", heading: /label/i },
  { path: "/audit", heading: /audit/i },
  { path: "/alerts", heading: /alert/i },
  { path: "/threat-assessments", heading: /threat/i },
  { path: "/assessments", heading: /assessment/i },
  { path: "/trend", heading: /trend/i },
  { path: "/purview-insights", heading: /insight/i },
];

for (const page of pages) {
  test(`navigates to ${page.path}`, async ({ page: p }) => {
    await p.goto(page.path);
    await expect(p.locator("h1, h2").first()).toBeVisible();
  });
}
