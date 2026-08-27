import { expect, test } from "@playwright/test";


test("首次设置到复核决定的真实交互链路", async ({ page }) => {
  let snapshot: Record<string, unknown> | null = null;
  let review: Record<string, unknown> | null = null;
  let decided = false;
  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v2", "");
    if (path === "/health") {
      return route.fulfill({ json: { status: "ok", rule_version: "v2.1.0" } });
    }
    if (path === "/portfolio" && request.method() === "GET") {
      return route.fulfill({ json: { id: 1, name: "我的实验组合", capital_budget: 1000, updated_at: "2026-08-24", buckets: {}, latest_snapshot: snapshot } });
    }
    if (path === "/portfolio/snapshots" && request.method() === "POST") {
      snapshot = { id: 1, as_of_date: "2026-08-24", total_market_value: 1000, completeness: "complete", source: "manual", note: "", created_at: "2026-08-24", items: [] };
      return route.fulfill({ status: 201, json: snapshot });
    }
    if (path === "/reviews/latest") return route.fulfill({ json: review });
    if (path === "/reviews" && request.method() === "POST") {
      review = {
        id: 1, snapshot_id: 1, status: "completed", progress: 100, verdict: "review", verdict_label: "需要复核", data_quality: "ready", as_of_date: "2026-08-24", rule_version: "v2.1.0", error: "", created_at: "2026-08-24", completed_at: "2026-08-24",
        bucket_summary: { defense: { label: "流动防守仓", amount: 0, weight: 0, low: 0.3, mid: 0.4, high: 0.5, in_band: false }, core: { label: "核心配置仓", amount: 0, weight: 0, low: 0.3, mid: 0.35, high: 0.45, in_band: false }, satellite: { label: "卫星进攻仓", amount: 1000, weight: 1, low: 0.15, mid: 0.25, high: 0.3, in_band: false } },
        headlines: [{ kind: "finding", reason_type: "hard_risk", title: "测试基金命中硬风险", detail: "基金合同终止公告", severity: "critical" }],
        items: [{ id: 9, fund_code: "017470", fund_name: "测试基金", reason_type: "hard_risk", proposed_action: "exit_review", severity: "critical", title: "测试基金命中硬风险", detail: "基金合同终止公告", metrics: {}, evidence_ids: [], status: decided ? "acknowledged" : "open", decision: decided ? { choice: "agree", note: "已核对", decided_at: "2026-08-24" } : null }],
      };
      return route.fulfill({ status: 202, json: { run_id: 1, status: "queued" } });
    }
    if (path === "/reviews" && request.method() === "GET") return route.fulfill({ json: review ? [review] : [] });
    if (path === "/data-health") return route.fulfill({ json: { provider: "AKShare", fund_count: 1, latest_fetch: "2026-08-24", ocr: "ready", ai: "disabled" } });
    if (path === "/review-items/9/decision") {
      decided = true;
      if (review) {
        const items = review.items as Array<Record<string, unknown>>;
        items[0] = { ...items[0], status: "acknowledged", decision: { choice: "agree", note: "已核对", decided_at: "2026-08-24" } };
      }
      return route.fulfill({ json: { item_id: 9, status: "acknowledged", choice: "agree" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await expect(page.getByText("先确认你的完整持仓")).toBeVisible();
  await page.getByRole("button", { name: "设置我的组合" }).click();
  await page.getByLabel("基金代码 1").fill("017470");
  await page.getByLabel("持仓金额 1").fill("1000");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "确认持仓快照" }).click();
  await expect(page.getByText("完整持仓快照已确认，可以开始评估")).toBeVisible();

  await page.getByRole("link", { name: /决策台/ }).click();
  await page.getByRole("button", { name: "开始本次评估" }).click();
  await expect(page.getByRole("heading", { name: "需要复核" })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: "test-results/dashboard-1440.png", fullPage: true });
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.screenshot({ path: "test-results/dashboard-1024.png", fullPage: true });
  await page.setViewportSize({ width: 820, height: 900 });
  await page.screenshot({ path: "test-results/dashboard-narrow.png", fullPage: true });
  await page.getByRole("link", { name: /历史与数据/ }).click();
  await page.getByText("#1 · 2026-08-24").click();
  await page.getByPlaceholder("可选备注").fill("已核对");
  await page.getByRole("button", { name: "同意" }).click();
  await expect(page.getByText("已选择：agree · 已核对")).toBeVisible();
});

test("OCR 完成后展示原文和可校对草稿", async ({ page }) => {
  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v2", "");
    if (path === "/health") return route.fulfill({ json: { status: "ok", rule_version: "v2.1.0" } });
    if (path === "/portfolio") return route.fulfill({ json: { id: 1, name: "我的实验组合", capital_budget: 1000, updated_at: "2026-08-24", buckets: {}, latest_snapshot: null, latest_draft: null } });
    if (path === "/imports" && request.method() === "GET") return route.fulfill({ json: [] });
    if (path === "/imports" && request.method() === "POST") return route.fulfill({ status: 201, json: { id: 3, status: "uploaded", items: [] } });
    if (path === "/imports/3/process") return route.fulfill({ json: { id: 3, filename: "holding.png", status: "needs_review", page_type: "holdings", raw_text: "全部持有\n017470\n持有金额 250.00元", error: "", created_at: "2026-08-24", items: [{ id: 1, fund_code: "017470", fund_name: "测试指数基金", amount: 250, bucket: "satellite", confidence: 0.88, issues: "请核对", confirmed: false }] } });
    return route.fulfill({ json: [] });
  });
  await page.goto("/portfolio");
  await page.locator('input[type="file"]').setInputFiles({ name: "holding.png", mimeType: "image/png", buffer: Buffer.from("fake-image") });
  await expect(page.getByRole("heading", { name: "截图识别结果" })).toBeVisible();
  await expect(page.getByText("1 条结构化基金记录")).toBeVisible();
  await expect(page.getByText("全部持有")).toBeVisible();
  await expect(page.getByRole("heading", { name: "校对 OCR 草稿 #3" })).toBeVisible();
  await expect(page.getByLabel("基金代码 1")).toHaveValue("017470");
});

test("从前端安全保存并立即启用 DeepSeek", async ({ page }) => {
  let configured = false;
  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v2", "");
    const aiState = { status: configured ? "configured" : "disabled", enabled: configured, key_configured: configured, model: "deepseek-v4-flash", base_url: "https://api.deepseek.com", missing: configured ? [] : ["FUNDLAB_AI_ENABLED=true", "DEEPSEEK_API_KEY"], environment_overrides: [] };
    if (path === "/settings/ai" && request.method() === "GET") return route.fulfill({ json: aiState });
    if (path === "/settings/ai" && request.method() === "PUT") {
      const payload = request.postDataJSON();
      expect(payload.api_key).toBe("local-test-key");
      configured = true;
      return route.fulfill({ json: { ...aiState, status: "configured", enabled: true, key_configured: true, missing: [], message: "AI 配置已保存并即时生效" } });
    }
    if (path === "/settings/ai/test") return route.fulfill({ json: { ok: true, status: "ok", message: "连接和 JSON 输出正常" } });
    if (path === "/data-health") return route.fulfill({ json: { provider: "fixture", fund_count: 0, blocked_funds: 0, limited_funds: 0, latest_fetch: null, ocr: "ready", ai: aiState.status, ai_config: aiState } });
    if (path === "/reviews") return route.fulfill({ json: [] });
    if (path === "/health") return route.fulfill({ json: { status: "ok", rule_version: "v2.1.0" } });
    if (path === "/portfolio") return route.fulfill({ json: { id: 1, name: "我的实验组合", capital_budget: 1000, updated_at: "2026-08-24", buckets: {}, latest_snapshot: null } });
    return route.fulfill({ json: null });
  });

  await page.goto("/history");
  await page.getByRole("button", { name: "配置 AI" }).click();
  const keyInput = page.getByLabel("API Key");
  await expect(keyInput).toHaveAttribute("type", "password");
  await keyInput.fill("local-test-key");
  await page.getByLabel("启用 DeepSeek 解释").check();
  await page.getByRole("button", { name: "保存并立即生效" }).click();
  await expect(page.getByText("AI 配置已保存并即时生效")).toBeVisible();
  await expect(keyInput).toHaveValue("");
  await expect(page.getByText("API Key：已保存")).toBeVisible();
  await page.getByRole("button", { name: "测试连接" }).click();
  await expect(page.getByText("连接和 JSON 输出正常")).toBeVisible();
});
