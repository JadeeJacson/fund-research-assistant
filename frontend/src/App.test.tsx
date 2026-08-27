import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";


const portfolio = {
  id: 1,
  name: "我的实验组合",
  capital_budget: 1000,
  updated_at: "2026-08-24T00:00:00Z",
  buckets: {},
  latest_snapshot: null,
};


function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><App /></MemoryRouter>
    </QueryClientProvider>,
  );
}


describe("基金仓位决策台", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      const body = path.endsWith("/health")
        ? { status: "ok", rule_version: "v2.1.0" }
        : path.endsWith("/portfolio")
          ? portfolio
          : path.endsWith("/reviews/latest")
            ? null
            : path.endsWith("/discoveries/latest")
              ? null
            : [];
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
  });

  it("shows a real first-use flow and keeps review disabled without a complete snapshot", async () => {
    renderApp();
    expect(screen.getByRole("heading", { name: "今天，需要动吗？" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始本次评估" })).toBeDisabled();
    expect(await screen.findByText("先确认你的完整持仓")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("本地服务正常")).toBeInTheDocument());
  });

  it("navigates through the five real product pages", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: /我的组合/ }));
    expect(screen.getByRole("heading", { name: "我的组合" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: /基金详情/ }));
    expect(screen.getByRole("heading", { name: "基金详情" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: /基金探索/ }));
    expect(screen.getByRole("heading", { name: "基金探索与替代对照" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: /历史与数据/ }));
    expect(screen.getByRole("heading", { name: "历史与数据" })).toBeInTheDocument();
  });

  it("shows the persisted holding list after manual or OCR confirmation", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      const body = path.endsWith("/health")
        ? { status: "ok", rule_version: "v2.1.0" }
        : path.endsWith("/portfolio")
          ? {
              ...portfolio,
              latest_snapshot: {
                id: 7,
                as_of_date: "2026-08-24",
                total_market_value: 1000,
                completeness: "complete",
                source: "manual",
                note: "",
                created_at: "2026-08-24",
                items: [{ id: 1, fund_code: "017470", fund_name: "测试指数基金", fund_type: "index", amount: 1000, weight: 1, displayed_profit: null, bucket: "satellite", assignment_source: "manual", quality_status: "ready", value_date: null }],
              },
            }
          : [];
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: /我的组合/ }));
    expect(await screen.findByRole("heading", { name: "当前已确认持仓" })).toBeInTheDocument();
    expect(screen.getByText("017470")).toBeInTheDocument();
    expect(screen.getByText("测试指数基金")).toBeInTheDocument();
  });

  it("shows intuitive percentage and risk metrics on fund detail", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      let body: unknown = [];
      if (path.endsWith("/health")) body = { status: "ok", rule_version: "v2.1.1" };
      else if (path.endsWith("/funds/017470")) body = {
        fund: { id: 1, code: "017470", name: "测试科创基金", fund_type: "index", subtype: "thematic_index", peer_key: "index:科创", default_bucket: "satellite", peer_percentile: 55, expense_ratio: null, aum_yi: 4.2, quality_status: "ready", value_date: "2026-08-22", source_name: "fixture", purchase_status: "开放申购", redemption_status: "开放赎回", manager: "", benchmark: "科创指数", tracked_index: "", currency: "CNY", valuation_lag_note: "", target_risk: "", product_status: "active", tracking_error: null, return_method: "累计净值" },
        nav: [], evidence: [],
        performance: { as_of_date: "2026-08-22", observations: 253, total_return: 0.12, return_1m: 0.04, return_3m: 0.08, return_1y: 0.12, annualized_return: 0.12, volatility: 0.096, max_drawdown: -0.08, sharpe: 1.25, calmar: 1.5 },
        performance_chart: [{ date: "2025-08-22", cumulative_return: 0, drawdown: 0 }, { date: "2026-08-22", cumulative_return: 0.12, drawdown: -0.03 }],
      };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: /基金详情/ }));
    fireEvent.change(screen.getByLabelText("基金代码"), { target: { value: "017470" } });
    fireEvent.click(screen.getByRole("button", { name: "查看" }));

    expect(await screen.findByRole("heading", { name: "近一年基金表现" })).toBeInTheDocument();
    expect(screen.getByText("收益与风险指标")).toBeInTheDocument();
    expect(screen.getByText("简化夏普")).toBeInTheDocument();
    expect(screen.getByText("1.25")).toBeInTheDocument();
    expect(screen.getByText("4.0%")).toBeInTheDocument();
  });

  it("runs fund discovery only after the user clicks and shows screened reasons", async () => {
    let started = false;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      let body: unknown = null;
      if (path.endsWith("/health")) body = { status: "ok", rule_version: "v2.1.1" };
      else if (path.endsWith("/discoveries") && init?.method === "POST") { started = true; body = { run_id: 3, status: "queued" }; }
      else if (path.endsWith("/discoveries/latest")) body = started ? {
        id: 3, snapshot_id: 7, status: "completed", progress: 100, rule_version: "v2.1.1", error: "", created_at: "2026-08-24", completed_at: "2026-08-24",
        results: [{ fund: { code: "017471", name: "候选科创基金A", value_date: "2026-08-22" }, bucket: "satellite", compared_to: { code: "017470", name: "当前科创基金C" }, suggestion: "值得进一步对照", tier: "strong", eligible: true, improvements: ["夏普比率改善至少 15%", "最大回撤改善 3.2%"], counterpoints: [], metrics: { max_drawdown: -0.08 } }],
      } : null;
      else body = [];
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: /基金探索/ }));
    fireEvent.click(await screen.findByRole("button", { name: "开始探索基金" }));
    expect(await screen.findByText("候选科创基金A")).toBeInTheDocument();
    expect(screen.getByText("夏普比率改善至少 15%")).toBeInTheDocument();
    expect(screen.getByText("值得进一步对照")).toBeInTheDocument();
  });

  it("generates an AI explanation only after the user clicks", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      let body: unknown = null;
      if (path.endsWith("/health")) body = { status: "ok", rule_version: "v2.1.1" };
      else if (path.endsWith("/portfolio")) body = { ...portfolio, current_bucket_summary: {}, latest_snapshot: { id: 7, as_of_date: "2026-08-24", total_market_value: 1000, completeness: "complete", items: [] } };
      else if (path.endsWith("/reviews/latest")) body = { id: 5, snapshot_id: 7, status: "completed", progress: 100, verdict: "review", verdict_label: "需要复核", data_quality: "ready", as_of_date: "2026-08-24", rule_version: "v2.1.1", bucket_summary: {}, headlines: [], error: "", created_at: "2026-08-24", completed_at: "2026-08-24", items: [] };
      else if (path.endsWith("/reviews/5/explain") && init?.method === "POST") body = { status: "ok", summary: "AI 只解释现有复核结果。", supporting_points: [{ text: "基金质量需要人工确认", evidence_ids: [] }], counterpoints: [], unknowns: ["缺少公告证据"], cached: false };
      else body = [];
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    renderApp();
    expect(screen.queryByText("AI 只解释现有复核结果。")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "生成 AI 解释" }));
    expect(await screen.findByText("AI 只解释现有复核结果。")).toBeInTheDocument();
    expect(screen.getByText("仍未知：缺少公告证据")).toBeInTheDocument();
  });

  it("configures DeepSeek without ever prefilling the saved key", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/settings/ai") && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body));
        expect(payload.api_key).toBe("new-local-key");
        return new Response(JSON.stringify({ status: "configured", enabled: true, key_configured: true, model: "deepseek-v4-flash", base_url: "https://api.deepseek.com", missing: [], environment_overrides: [], message: "AI 配置已保存并即时生效" }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      const body = path.endsWith("/health")
        ? { status: "ok", rule_version: "v2.1.0" }
        : path.endsWith("/settings/ai")
          ? { status: "configured", enabled: true, key_configured: true, model: "deepseek-v4-flash", base_url: "https://api.deepseek.com", missing: [], environment_overrides: [] }
          : path.endsWith("/data-health")
            ? { provider: "fixture", fund_count: 0, blocked_funds: 0, limited_funds: 0, latest_fetch: null, ocr: "ready", ai: "configured" }
            : path.endsWith("/reviews")
              ? []
              : path.endsWith("/portfolio")
                ? portfolio
                : null;
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: /历史与数据/ }));
    fireEvent.click(await screen.findByRole("button", { name: "配置 AI" }));
    const keyInput = screen.getByLabelText("API Key") as HTMLInputElement;
    expect(keyInput).toHaveAttribute("type", "password");
    expect(keyInput).toHaveValue("");
    expect(keyInput).toHaveAttribute("placeholder", "已保存；留空则不修改");
    fireEvent.change(keyInput, { target: { value: "new-local-key" } });
    fireEvent.click(screen.getByRole("button", { name: "保存并立即生效" }));
    expect(await screen.findByText("AI 配置已保存并即时生效")).toBeInTheDocument();
    expect(keyInput).toHaveValue("");
  });

  it("merges OCR data into an existing holding and keeps optional profit", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      const method = init?.method ?? "GET";
      let body: unknown = null;
      if (path.endsWith("/health")) body = { status: "ok", rule_version: "v2.1.1" };
      else if (path.endsWith("/portfolio")) body = {
        ...portfolio,
        current_bucket_summary: {},
        latest_snapshot: {
          id: 5, as_of_date: "2026-08-24", total_market_value: 600, completeness: "complete", source: "manual", note: "", created_at: "2026-08-24",
          items: [
            { id: 1, fund_code: "017470", fund_name: "嘉实芯片联接C", fund_type: "index", amount: 250, weight: 0.4167, displayed_profit: null, bucket: "satellite", assignment_source: "manual", quality_status: "ready", value_date: null },
            { id: 2, fund_code: "006985", fund_name: "兴全恒裕债券A", fund_type: "bond", amount: 350, weight: 0.5833, displayed_profit: 8, bucket: "core", assignment_source: "manual", quality_status: "ready", value_date: null },
          ],
        },
      };
      else if (path.endsWith("/imports") && method === "GET") body = [];
      else if (path.endsWith("/imports") && method === "POST") body = { id: 9, status: "uploaded", items: [] };
      else if (path.endsWith("/imports/9/process")) body = {
        id: 9, filename: "holding.png", status: "needs_review", page_type: "holdings", raw_text: "017470\n持有金额 300\n持有收益 -12.3", error: "", created_at: "2026-08-24",
        items: [{ id: 3, fund_code: "017470", fund_name: "待刷新基金 017470", amount: 300, displayed_profit: -12.3, bucket: "satellite", confidence: 0.9, issues: "", confirmed: false }],
      };
      else body = [];
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: /我的组合/ }));
    await screen.findByRole("heading", { name: "当前已确认持仓" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [new File(["image"], "holding.png", { type: "image/png" })] } });
    expect(await screen.findByText(/更新已有持仓 1 条，新增 0 条/)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/基金代码 \d/)).toHaveLength(2);
    expect(screen.getByLabelText("持仓金额 1")).toHaveValue(300);
    expect(screen.getByLabelText("持有收益 1")).toHaveValue(-12.3);
    expect(screen.getByLabelText("持仓金额 2")).toHaveValue(350);
    expect(screen.getByLabelText("持有收益 2")).toHaveValue(8);
    expect(screen.getByLabelText("我确认这是当前全部持仓")).not.toBeChecked();
  });
});
