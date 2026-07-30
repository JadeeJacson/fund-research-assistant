import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const path = new URL(url).pathname;
    if (path.endsWith("/health")) {
      await route.fulfill({
        json: {
          status: "ok",
          database: "ok",
          ocr: "rapidocr",
          market_provider: "demo",
          ai: "mock",
          risk_tolerance: 0.1,
        },
      });
    } else if (path.endsWith("/dashboard")) {
      await route.fulfill({
        json: {
          candidate_count: 1,
          holding_count: 0,
          portfolio_amount: 0,
          pending_imports: 0,
          latest_snapshot_date: null,
          risk_tolerance: 0.1,
        },
      });
    } else if (path.endsWith("/candidates") && route.request().method() === "GET") {
      await route.fulfill({
        json: [
          {
            id: 1,
            fund_code: "017470",
            fund_name: "嘉实上证科创板芯片ETF联接C",
            share_class: "C",
            fund_type: "index",
            note: "",
            planned_amount: null,
            latest_nav: 2.8227,
            nav_date: "2026-07-29",
            data_source: "离线演示数据",
            refreshed_at: "2026-07-29T12:00:00Z",
            created_at: "2026-07-29T12:00:00Z",
          },
        ],
      });
    } else {
      await route.fulfill({ json: [] });
    }
  });
});

test("dashboard and candidate page have working navigation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("投资研究总览")).toBeVisible();
  await page.getByRole("button", { name: /候选研究/ }).click();
  await expect(page.getByText("嘉实上证科创板芯片ETF联接C")).toBeVisible();
  await expect(page.getByRole("button", { name: "研究 2～3 个月" })).toBeEnabled();
});
