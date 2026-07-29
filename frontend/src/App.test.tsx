import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const health = {
  status: "ok",
  database: "ok",
  ocr: "manual_review",
  market_provider: "demo_fallback",
  ai: "mock",
  risk_tolerance: 0.1,
};

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.endsWith("/health")
          ? health
          : url.endsWith("/dashboard")
            ? {
                candidate_count: 0,
                holding_count: 0,
                portfolio_amount: 0,
                pending_imports: 0,
                latest_snapshot_date: null,
                risk_tolerance: 0.1,
              }
            : [];
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
  });

  it("shows the dashboard and navigates to candidate research", async () => {
    render(<App />);
    expect(screen.getByText("投资研究总览")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("本地服务正常")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /候选研究/ }));
    expect(screen.getByText("候选基金研究")).toBeInTheDocument();
    expect(await screen.findByText("还没有候选基金，请先输入代码。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加入候选" })).toBeEnabled();
  });
});
