import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type {
  Candidate,
  Evidence,
  Holding,
  ImportBatch,
  ImportItem,
  Page,
  Report,
  Transaction,
  Trigger,
} from "./types";

const NAV: Array<{ id: Page; label: string; icon: string }> = [
  { id: "dashboard", label: "总览", icon: "◫" },
  { id: "candidates", label: "候选研究", icon: "◇" },
  { id: "imports", label: "截图导入", icon: "▣" },
  { id: "portfolio", label: "持仓交易", icon: "◎" },
  { id: "triggers", label: "条件触发", icon: "⌁" },
  { id: "settings", label: "设置", icon: "⚙" },
];

function money(value: number | null | undefined) {
  return value == null
    ? "—"
    : new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" }).format(value);
}

function percent(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(2)}%`;
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

function Notice({ value }: { value: { kind: "ok" | "error"; text: string } | null }) {
  if (!value) return null;
  return (
    <div className={`notice ${value.kind}`} role={value.kind === "error" ? "alert" : "status"}>
      {value.text}
    </div>
  );
}

function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [health, setHealth] = useState<Record<string, string | number> | null>(null);

  useEffect(() => {
    api.get<Record<string, string | number>>("/health").then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">F</span>
          <div>
            <strong>FundLab</strong>
            <small>个人基金研究助手</small>
          </div>
        </div>
        <nav aria-label="主导航">
          {NAV.map((item) => (
            <button
              className={page === item.id ? "nav-item active" : "nav-item"}
              key={item.id}
              onClick={() => setPage(item.id)}
              type="button"
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className={health ? "status-dot online" : "status-dot"} />
          <div>
            <strong>{health ? "本地服务正常" : "正在连接服务"}</strong>
            <small>
              {health
                ? `${String(health.market_provider)} · ${String(health.ocr)}`
                : "请确认后端已经启动"}
            </small>
          </div>
        </div>
      </aside>
      <main className="workspace">
        {page === "dashboard" && <Dashboard />}
        {page === "candidates" && <Candidates />}
        {page === "imports" && <Imports />}
        {page === "portfolio" && <Portfolio />}
        {page === "triggers" && <Triggers />}
        {page === "settings" && <Settings />}
      </main>
    </div>
  );
}

function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}

function Dashboard() {
  const [data, setData] = useState<Record<string, number | string | null> | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = async () => {
    setLoading(true);
    setNotice(null);
    try {
      setData(await api.get("/dashboard"));
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="LOCAL RESEARCH DESK"
        title="投资研究总览"
        description="先看数据质量和风险，再决定是否扩大暴露。"
        action={
          <button className="button secondary" onClick={load} disabled={loading} type="button">
            {loading ? "刷新中…" : "刷新总览"}
          </button>
        }
      />
      <Notice value={notice} />
      <div className="metric-grid">
        <Card>
          <span className="metric-label">候选基金</span>
          <strong className="metric-value">{data?.candidate_count ?? "—"}</strong>
          <small>等待研究或比较</small>
        </Card>
        <Card>
          <span className="metric-label">当前持仓</span>
          <strong className="metric-value">{data?.holding_count ?? "—"}</strong>
          <small>按最近快照统计</small>
        </Card>
        <Card>
          <span className="metric-label">实验组合</span>
          <strong className="metric-value">
            {typeof data?.portfolio_amount === "number" ? money(data.portfolio_amount) : "—"}
          </strong>
          <small>{data?.latest_snapshot_date ? `快照 ${data.latest_snapshot_date}` : "尚无快照"}</small>
        </Card>
        <Card className="risk-card">
          <span className="metric-label">阶段性回撤参考</span>
          <strong className="metric-value">
            {typeof data?.risk_tolerance === "number" ? percent(data.risk_tolerance) : "10.00%"}
          </strong>
          <small>不是损失保证或自动止损</small>
        </Card>
      </div>
      <div className="two-column">
        <Card>
          <div className="card-heading">
            <div>
              <span className="eyebrow">WORKFLOW</span>
              <h2>建议工作顺序</h2>
            </div>
          </div>
          <ol className="workflow-list">
            <li><span>01</span><div><strong>建立候选</strong><p>输入基金代码，或从支付宝自选截图导入。</p></div></li>
            <li><span>02</span><div><strong>刷新公开数据</strong><p>截图只描述你的状态，基金研究依赖公开数据。</p></div></li>
            <li><span>03</span><div><strong>选择研究期限</strong><p>2～3 个月和约 1 年分别运行规则。</p></div></li>
            <li><span>04</span><div><strong>校对个人数据</strong><p>OCR 结果确认后才能进入持仓和交易。</p></div></li>
          </ol>
        </Card>
        <Card>
          <div className="card-heading">
            <div>
              <span className="eyebrow">REVIEW QUEUE</span>
              <h2>待处理事项</h2>
            </div>
          </div>
          <div className="review-count">
            <strong>{data?.pending_imports ?? "—"}</strong>
            <span>个截图批次等待人工确认</span>
          </div>
          <p className="muted">
            低置信度、截断名称、金额/份额和交易时间必须校对。未确认草稿不会参与任何建议。
          </p>
        </Card>
      </div>
    </>
  );
}

function Candidates() {
  const [items, setItems] = useState<Candidate[]>([]);
  const [code, setCode] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = async () => {
    setItems(await api.get<Candidate[]>("/candidates"));
  };
  useEffect(() => {
    load().catch((error) => setNotice({ kind: "error", text: (error as Error).message }));
  }, []);

  const add = async (event: FormEvent) => {
    event.preventDefault();
    setBusy("add");
    setNotice(null);
    try {
      await api.post("/candidates", { fund_code: code, note });
      setCode("");
      setNote("");
      await load();
      setNotice({ kind: "ok", text: "候选基金已保存，可以刷新公开数据。" });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  };

  const act = async (candidate: Candidate, action: "refresh" | "short" | "long" | "delete") => {
    setBusy(`${action}-${candidate.id}`);
    setNotice(null);
    try {
      if (action === "refresh") {
        await api.post(`/candidates/${candidate.id}/refresh`);
        await load();
        setNotice({ kind: "ok", text: `${candidate.fund_code} 的公开数据已刷新。` });
      } else if (action === "delete") {
        if (!window.confirm(`确认删除候选“${candidate.fund_name}”吗？`)) return;
        await api.delete(`/candidates/${candidate.id}`);
        if (report?.candidate.id === candidate.id) setReport(null);
        await load();
      } else {
        setReport(
          await api.post<Report>("/reports", {
            candidate_id: candidate.id,
            horizon: action,
          }),
        );
      }
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="CANDIDATE LAB"
        title="候选基金研究"
        description="基金详情优先来自公开数据；支付宝截图用于确认你真正关注或持有的标的。"
      />
      <Notice value={notice} />
      <Card>
        <form className="inline-form" onSubmit={add}>
          <label>
            六位基金代码
            <input
              aria-label="六位基金代码"
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              pattern="\d{6}"
              placeholder="例如 017470"
              required
            />
          </label>
          <label className="grow">
            关注原因
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="可选：为什么关注这只基金"
            />
          </label>
          <button className="button primary" disabled={busy === "add"} type="submit">
            {busy === "add" ? "保存中…" : "加入候选"}
          </button>
        </form>
      </Card>
      <div className="candidate-layout">
        <div className="stack">
          {items.length === 0 && <Card><p className="empty">还没有候选基金，请先输入代码。</p></Card>}
          {items.map((candidate) => (
            <Card key={candidate.id} className="candidate-card">
              <div className="candidate-title">
                <div>
                  <span className="code">{candidate.fund_code}</span>
                  <h2>{candidate.fund_name}</h2>
                  <div className="tag-row">
                    <span className="tag">{candidate.fund_type}</span>
                    {candidate.share_class && <span className="tag">{candidate.share_class} 类份额</span>}
                    <span className={candidate.data_source.includes("演示") ? "tag warning" : "tag"}>
                      {candidate.data_source}
                    </span>
                  </div>
                </div>
                <div className="nav-value">
                  <strong>{candidate.latest_nav?.toFixed(4) ?? "未刷新"}</strong>
                  <small>{candidate.nav_date ?? "无净值日期"}</small>
                </div>
              </div>
              {candidate.note && <p className="note">{candidate.note}</p>}
              <div className="action-row">
                <button
                  className="button secondary"
                  disabled={Boolean(busy)}
                  onClick={() => act(candidate, "refresh")}
                  type="button"
                >
                  {busy === `refresh-${candidate.id}` ? "刷新中…" : "刷新公开数据"}
                </button>
                <button
                  className="button primary"
                  disabled={Boolean(busy)}
                  onClick={() => act(candidate, "short")}
                  type="button"
                >
                  研究 2～3 个月
                </button>
                <button
                  className="button primary"
                  disabled={Boolean(busy)}
                  onClick={() => act(candidate, "long")}
                  type="button"
                >
                  研究约 1 年
                </button>
                <button
                  className="button danger"
                  disabled={Boolean(busy)}
                  onClick={() => act(candidate, "delete")}
                  type="button"
                >
                  删除
                </button>
              </div>
            </Card>
          ))}
        </div>
        <ReportPanel report={report} />
      </div>
    </>
  );
}

function ReportPanel({ report }: { report: Report | null }) {
  if (!report) {
    return (
      <Card className="report-panel">
        <span className="eyebrow">ANALYSIS</span>
        <h2>研究报告</h2>
        <p className="empty">选择候选基金并运行一个期限，结果会显示在这里。</p>
      </Card>
    );
  }
  return <ReportContents key={report.report_id} initialReport={report} />;
}

function ReportContents({ initialReport }: { initialReport: Report }) {
  const [report, setReport] = useState(initialReport);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    source_url: "",
    published_at: new Date().toISOString().slice(0, 10),
    trust_level: "B",
    content: "",
  });
  const decision = report.decision;
  const loadEvidence = async () => {
    setEvidence(await api.get<Evidence[]>(`/evidence?candidate_id=${report.candidate.id}`));
  };
  useEffect(() => {
    loadEvidence().catch((reason) => setError((reason as Error).message));
  }, [report.candidate.id]);
  const addEvidence = async (event: FormEvent) => {
    event.preventDefault(); setBusy("evidence"); setError("");
    try {
      await api.post("/evidence", { ...form, candidate_id: report.candidate.id });
      setForm({ ...form, title: "", source_url: "", content: "" });
      await loadEvidence();
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(""); }
  };
  const removeEvidence = async (id: number) => {
    if (!window.confirm("确认删除这条证据吗？")) return;
    try { await api.delete(`/evidence/${id}`); await loadEvidence(); } catch (reason) { setError((reason as Error).message); }
  };
  const explain = async () => {
    setBusy("explain"); setError("");
    try { setReport(await api.post<Report>(`/reports/${report.report_id}/explain`)); }
    catch (reason) { setError((reason as Error).message); } finally { setBusy(""); }
  };
  return (
    <Card className="report-panel">
      <span className="eyebrow">REPORT #{report.report_id}</span>
      <div className="report-state">
        <div>
          <small>{report.horizon === "short" ? "2～3 个月" : "约 1 年"}</small>
          <h2>{decision.state}</h2>
        </div>
        <span className="confidence">置信度 {decision.confidence}</span>
      </div>
      <div className="range">
        <span>建议占实验组合</span>
        <strong>{percent(decision.target_weight[0])} ～ {percent(decision.target_weight[1])}</strong>
      </div>
      <div className="mini-metrics">
        <div><span>近 3 月</span><strong>{percent(report.metrics.return_3m as number | null)}</strong></div>
        <div><span>近 1 年</span><strong>{percent(report.metrics.return_1y as number | null)}</strong></div>
        <div><span>最大回撤</span><strong>{percent(report.metrics.max_drawdown as number | null)}</strong></div>
        <div><span>年化波动</span><strong>{percent(report.metrics.volatility as number | null)}</strong></div>
      </div>
      <h3>支持理由</h3>
      <ul>{decision.positive_points.length ? decision.positive_points.map((item) => <li key={item}>{item}</li>) : <li>暂无足够支持证据</li>}</ul>
      <h3>风险与反方</h3>
      <ul>{[...decision.risk_points, ...decision.unknowns].map((item) => <li key={item}>{item}</li>)}</ul>
      <h3>条件与有效期</h3>
      <ul>{decision.triggers.map((item) => <li key={item.description}>{item.description}</li>)}</ul>
      <p className="muted">数据截止 {report.as_of_date}，建议默认 {decision.valid_days} 天后复核。</p>
      <p className="disclaimer">{decision.disclaimer}</p>
      <div className="evidence-section">
        <h3>Evidence Pack</h3>
        {error && <p className="field-error">{error}</p>}
        {evidence.map((item) => (
          <div className="evidence-item" key={item.id}>
            <a href={item.source_url} target="_blank" rel="noreferrer">{item.title}</a>
            <span>{item.trust_level} 级 · {item.published_at}</span>
            <button aria-label={`删除证据 ${item.title}`} onClick={() => removeEvidence(item.id)} type="button">×</button>
          </div>
        ))}
        <details>
          <summary>添加公开证据</summary>
          <form className="form-grid evidence-form" onSubmit={addEvidence}>
            <label className="span-two">标题<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required /></label>
            <label className="span-two">来源 URL<input type="url" value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} required /></label>
            <label>发布日期<input type="date" value={form.published_at} onChange={(e) => setForm({ ...form, published_at: e.target.value })} required /></label>
            <label>可信等级<select value={form.trust_level} onChange={(e) => setForm({ ...form, trust_level: e.target.value })}><option value="S">S 官方/法定</option><option value="A">A 专业结构化</option><option value="B">B 可靠媒体</option><option value="C">C 待核验线索</option></select></label>
            <label className="span-two">证据正文<textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} minLength={10} required /></label>
            <button className="button secondary" disabled={busy !== ""} type="submit">{busy === "evidence" ? "保存中…" : "保存证据"}</button>
          </form>
        </details>
        <button className="button primary" disabled={busy !== "" || evidence.length === 0} onClick={explain} type="button">
          {busy === "explain" ? "生成中…" : "用已保存证据生成 AI 解释"}
        </button>
        {report.ai_explanation && (
          <div className="ai-box">
            <span className="eyebrow">AI · {report.ai_explanation.status}</span>
            <p>{report.ai_explanation.summary ?? "尚无解释"}</p>
          </div>
        )}
      </div>
    </Card>
  );
}

function Imports() {
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const selected = batches.find((batch) => batch.id === selectedId) ?? null;

  const load = async (prefer?: number) => {
    const values = await api.get<ImportBatch[]>("/imports");
    setBatches(values);
    if (prefer) setSelectedId(prefer);
    else if (!selectedId && values[0]) setSelectedId(values[0].id);
  };
  useEffect(() => {
    load().catch((error) => setNotice({ kind: "error", text: (error as Error).message }));
  }, []);

  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy("upload");
    setNotice(null);
    try {
      const batch = await api.upload<ImportBatch>("/imports", file);
      await load(batch.id);
      setFile(null);
      setNotice({ kind: "ok", text: "图片已识别为草稿。请逐字段核对后确认导入。" });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  };

  const confirm = async () => {
    if (!selected) return;
    setBusy("confirm");
    setNotice(null);
    try {
      await api.post(`/imports/${selected.id}/confirm`);
      await load(selected.id);
      setNotice({ kind: "ok", text: "已确认记录已经写入正式数据。" });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  };

  const remove = async () => {
    if (!selected || !window.confirm(`删除导入批次 #${selected.id} 及其原图吗？`)) return;
    setBusy("delete");
    try {
      await api.delete(`/imports/${selected.id}`);
      setSelectedId(null);
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="OCR REVIEW"
        title="截图导入中心"
        description="候选、持仓和交易图片先在本机 OCR，再由你确认。DeepSeek 不接收原图。"
      />
      <Notice value={notice} />
      <Card>
        <form className="upload-zone" onSubmit={upload}>
          <label>
            <strong>选择支付宝截图</strong>
            <span>支持 JPG、PNG、WebP，单张不超过 12 MB</span>
            <input
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              type="file"
              required
            />
          </label>
          <button className="button primary" disabled={!file || busy === "upload"} type="submit">
            {busy === "upload" ? "识别中…" : "上传并识别"}
          </button>
        </form>
      </Card>
      <div className="import-layout">
        <Card>
          <div className="card-heading"><h2>导入批次</h2></div>
          <div className="batch-list">
            {batches.length === 0 && <p className="empty">尚未上传截图。</p>}
            {batches.map((batch) => (
              <button
                className={selectedId === batch.id ? "batch active" : "batch"}
                key={batch.id}
                onClick={() => setSelectedId(batch.id)}
                type="button"
              >
                <strong>#{batch.id} {batch.filename}</strong>
                <span>{batch.page_type} · {batch.status} · {batch.items.length} 条</span>
              </button>
            ))}
          </div>
        </Card>
        <Card>
          {!selected ? (
            <p className="empty">选择一个批次开始校对。</p>
          ) : (
            <>
              <div className="card-heading">
                <div><span className="eyebrow">BATCH #{selected.id}</span><h2>逐字段校对</h2></div>
                <span className="tag">{selected.status}</span>
              </div>
              {selected.error && <div className="notice error">{selected.error}</div>}
              {selected.items.map((item) => (
                <ImportEditor item={item} key={item.id} onSaved={() => load(selected.id)} />
              ))}
              <details>
                <summary>查看 OCR 原文</summary>
                <pre className="ocr-text">{selected.raw_text || "没有 OCR 文本"}</pre>
              </details>
              <div className="action-row">
                <button
                  className="button primary"
                  disabled={busy !== "" || selected.status === "confirmed"}
                  onClick={confirm}
                  type="button"
                >
                  {busy === "confirm" ? "确认中…" : "确认并写入正式数据"}
                </button>
                <button className="button danger" disabled={busy !== ""} onClick={remove} type="button">
                  删除批次和原图
                </button>
              </div>
            </>
          )}
        </Card>
      </div>
    </>
  );
}

function ImportEditor({ item, onSaved }: { item: ImportItem; onSaved: () => Promise<void> }) {
  const [draft, setDraft] = useState(item);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setDraft(item), [item]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.put(`/import-items/${item.id}`, {
        kind: draft.kind,
        fund_code: draft.fund_code,
        fund_name: draft.fund_name,
        action: draft.action,
        amount: draft.amount,
        shares: draft.shares,
        event_time: draft.event_time,
      });
      await onSaved();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="draft-card" onSubmit={save}>
      <div className="draft-meta">
        <span className="tag">{draft.kind}</span>
        <span>识别置信度 {percent(draft.confidence)}</span>
        {draft.confirmed && <span className="tag success">已确认</span>}
      </div>
      {draft.issues && <p className="field-warning">{draft.issues}</p>}
      {error && <p className="field-error">{error}</p>}
      <div className="form-grid">
        <label>记录类型
          <select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as ImportItem["kind"] })} disabled={draft.confirmed}>
            <option value="candidate">候选</option><option value="holding">持仓</option><option value="transaction">交易</option>
          </select>
        </label>
        <label>基金代码
          <input value={draft.fund_code} onChange={(e) => setDraft({ ...draft, fund_code: e.target.value.replace(/\D/g, "").slice(0, 6) })} disabled={draft.confirmed} required />
        </label>
        <label className="span-two">基金名称
          <input value={draft.fund_name} onChange={(e) => setDraft({ ...draft, fund_name: e.target.value })} disabled={draft.confirmed} required />
        </label>
        {draft.kind === "transaction" && <label>动作
          <select value={draft.action || "buy"} onChange={(e) => setDraft({ ...draft, action: e.target.value })} disabled={draft.confirmed}>
            <option value="buy">买入</option><option value="sell">卖出</option><option value="convert_out">转换转出</option><option value="convert_in">转换转入</option>
          </select>
        </label>}
        {draft.kind !== "candidate" && <label>金额（元）
          <input type="number" min="0" step="0.01" value={draft.amount ?? ""} onChange={(e) => setDraft({ ...draft, amount: e.target.value ? Number(e.target.value) : null })} disabled={draft.confirmed} />
        </label>}
        {draft.kind === "transaction" && <label>份额
          <input type="number" min="0" step="0.0001" value={draft.shares ?? ""} onChange={(e) => setDraft({ ...draft, shares: e.target.value ? Number(e.target.value) : null })} disabled={draft.confirmed} />
        </label>}
        {draft.kind !== "candidate" && <label>时间
          <input type="datetime-local" value={draft.event_time?.slice(0, 16) ?? ""} onChange={(e) => setDraft({ ...draft, event_time: e.target.value ? new Date(e.target.value).toISOString() : null })} disabled={draft.confirmed} />
        </label>}
      </div>
      {!draft.confirmed && <button className="button secondary" disabled={busy} type="submit">{busy ? "保存中…" : "保存校对"}</button>}
    </form>
  );
}

function Portfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [mode, setMode] = useState<"holding" | "transaction">("holding");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [holdingForm, setHoldingForm] = useState({
    fund_code: "", fund_name: "", amount: "", snapshot_date: new Date().toISOString().slice(0, 10),
  });
  const [transactionForm, setTransactionForm] = useState({
    fund_code: "", fund_name: "", action: "buy", amount: "", trade_time: new Date().toISOString().slice(0, 16),
  });

  const load = async () => {
    const [holdingData, transactionData] = await Promise.all([
      api.get<Holding[]>("/holdings"),
      api.get<Transaction[]>("/transactions"),
    ]);
    setHoldings(holdingData);
    setTransactions(transactionData);
  };
  useEffect(() => { load().catch((e) => setNotice({ kind: "error", text: (e as Error).message })); }, []);
  const latestDate = holdings[0]?.snapshot_date;
  const latest = holdings.filter((item) => item.snapshot_date === latestDate);
  const total = latest.reduce((sum, item) => sum + item.amount, 0);

  const addHolding = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setNotice(null);
    try {
      await api.post("/holdings", { ...holdingForm, amount: Number(holdingForm.amount) });
      setHoldingForm({ fund_code: "", fund_name: "", amount: "", snapshot_date: new Date().toISOString().slice(0, 10) });
      await load(); setNotice({ kind: "ok", text: "持仓快照已保存。" });
    } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); } finally { setBusy(false); }
  };
  const addTransaction = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setNotice(null);
    try {
      await api.post("/transactions", {
        ...transactionForm,
        amount: Number(transactionForm.amount),
        trade_time: new Date(transactionForm.trade_time).toISOString(),
      });
      setTransactionForm({ fund_code: "", fund_name: "", action: "buy", amount: "", trade_time: new Date().toISOString().slice(0, 16) });
      await load(); setNotice({ kind: "ok", text: "交易已保存并完成重复检查。" });
    } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); } finally { setBusy(false); }
  };
  const remove = async (kind: "holdings" | "transactions", id: number) => {
    if (!window.confirm("确认删除这条记录吗？")) return;
    try { await api.delete(`/${kind}/${id}`); await load(); } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); }
  };

  return (
    <>
      <PageHeader eyebrow="PORTFOLIO LEDGER" title="持仓与交易" description="持仓截图是快照；精确成本和现金流需要确认后的完整交易记录。" />
      <Notice value={notice} />
      <div className="metric-grid compact">
        <Card><span className="metric-label">最新快照总额</span><strong className="metric-value">{money(total)}</strong><small>{latestDate ?? "尚无快照"}</small></Card>
        <Card><span className="metric-label">持仓项目</span><strong className="metric-value">{latest.length}</strong><small>按最新日期</small></Card>
        <Card><span className="metric-label">交易记录</span><strong className="metric-value">{transactions.length}</strong><small>已去重写入</small></Card>
      </div>
      <div className="tab-row">
        <button className={mode === "holding" ? "tab active" : "tab"} onClick={() => setMode("holding")} type="button">录入持仓</button>
        <button className={mode === "transaction" ? "tab active" : "tab"} onClick={() => setMode("transaction")} type="button">录入交易</button>
      </div>
      <div className="two-column">
        <Card>
          {mode === "holding" ? (
            <form className="form-grid" onSubmit={addHolding}>
              <label>基金代码<input pattern="\d{6}" value={holdingForm.fund_code} onChange={(e) => setHoldingForm({ ...holdingForm, fund_code: e.target.value.replace(/\D/g, "").slice(0, 6) })} required /></label>
              <label>快照日期<input type="date" value={holdingForm.snapshot_date} onChange={(e) => setHoldingForm({ ...holdingForm, snapshot_date: e.target.value })} required /></label>
              <label className="span-two">基金名称<input value={holdingForm.fund_name} onChange={(e) => setHoldingForm({ ...holdingForm, fund_name: e.target.value })} required /></label>
              <label>持仓金额<input min="0" step="0.01" type="number" value={holdingForm.amount} onChange={(e) => setHoldingForm({ ...holdingForm, amount: e.target.value })} required /></label>
              <button className="button primary align-end" disabled={busy} type="submit">{busy ? "保存中…" : "保存持仓快照"}</button>
            </form>
          ) : (
            <form className="form-grid" onSubmit={addTransaction}>
              <label>基金代码<input pattern="\d{6}" value={transactionForm.fund_code} onChange={(e) => setTransactionForm({ ...transactionForm, fund_code: e.target.value.replace(/\D/g, "").slice(0, 6) })} required /></label>
              <label>交易动作<select value={transactionForm.action} onChange={(e) => setTransactionForm({ ...transactionForm, action: e.target.value })}><option value="buy">买入</option><option value="sell">卖出</option><option value="convert_in">转换转入</option><option value="convert_out">转换转出</option><option value="dividend">分红</option></select></label>
              <label className="span-two">基金名称<input value={transactionForm.fund_name} onChange={(e) => setTransactionForm({ ...transactionForm, fund_name: e.target.value })} required /></label>
              <label>金额<input min="0" step="0.01" type="number" value={transactionForm.amount} onChange={(e) => setTransactionForm({ ...transactionForm, amount: e.target.value })} required /></label>
              <label>交易时间<input type="datetime-local" value={transactionForm.trade_time} onChange={(e) => setTransactionForm({ ...transactionForm, trade_time: e.target.value })} required /></label>
              <button className="button primary align-end" disabled={busy} type="submit">{busy ? "保存中…" : "保存交易"}</button>
            </form>
          )}
        </Card>
        <Card>
          <div className="card-heading"><h2>{mode === "holding" ? "持仓快照记录" : "交易流水"}</h2></div>
          <div className="record-list">
            {mode === "holding" && holdings.map((item) => (
              <div className="record" key={item.id}><div><strong>{item.fund_name}</strong><span>{item.fund_code} · {item.snapshot_date} · {item.source}</span></div><b>{money(item.amount)}</b><button aria-label={`删除持仓 ${item.fund_name}`} onClick={() => remove("holdings", item.id)} type="button">×</button></div>
            ))}
            {mode === "transaction" && transactions.map((item) => (
              <div className="record" key={item.id}><div><strong>{item.fund_name}</strong><span>{item.fund_code} · {item.action} · {new Date(item.trade_time).toLocaleString()}</span></div><b>{money(item.amount)}</b><button aria-label={`删除交易 ${item.fund_name}`} onClick={() => remove("transactions", item.id)} type="button">×</button></div>
            ))}
            {(mode === "holding" ? holdings : transactions).length === 0 && <p className="empty">暂无记录。</p>}
          </div>
        </Card>
      </div>
    </>
  );
}

function Triggers() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [items, setItems] = useState<Trigger[]>([]);
  const [form, setForm] = useState({ candidate_id: "", metric: "latest_nav", operator: "<=", threshold: "" });
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const names = useMemo(() => Object.fromEntries(candidates.map((item) => [item.id, item.fund_name])), [candidates]);
  const load = async () => {
    const [funds, triggers] = await Promise.all([api.get<Candidate[]>("/candidates"), api.get<Trigger[]>("/triggers")]);
    setCandidates(funds); setItems(triggers);
    if (!form.candidate_id && funds[0]) setForm((current) => ({ ...current, candidate_id: String(funds[0].id) }));
  };
  useEffect(() => { load().catch((e) => setNotice({ kind: "error", text: (e as Error).message })); }, []);
  const create = async (event: FormEvent) => {
    event.preventDefault(); setBusy("create");
    try {
      await api.post("/triggers", { ...form, candidate_id: Number(form.candidate_id), threshold: Number(form.threshold) });
      setForm({ ...form, threshold: "" }); await load();
    } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); } finally { setBusy(""); }
  };
  const check = async () => {
    setBusy("check");
    try { setItems(await api.post<Trigger[]>("/triggers/check")); setNotice({ kind: "ok", text: "已使用最新本地数据检查全部启用条件。" }); }
    catch (e) { setNotice({ kind: "error", text: (e as Error).message }); } finally { setBusy(""); }
  };
  const remove = async (id: number) => {
    if (!window.confirm("确认删除这个触发条件吗？")) return;
    try { await api.delete(`/triggers/${id}`); await load(); } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); }
  };
  return (
    <>
      <PageHeader eyebrow="CONDITION WATCH" title="条件触发器" description="本地版在你主动检查时运行。它提醒重新研究，不会自动申购或赎回。" action={<button className="button secondary" onClick={check} disabled={busy !== ""} type="button">{busy === "check" ? "检查中…" : "立即检查全部"}</button>} />
      <Notice value={notice} />
      <Card>
        <form className="inline-form" onSubmit={create}>
          <label>候选基金<select value={form.candidate_id} onChange={(e) => setForm({ ...form, candidate_id: e.target.value })} required><option value="">请选择</option>{candidates.map((item) => <option key={item.id} value={item.id}>{item.fund_code} {item.fund_name}</option>)}</select></label>
          <label>指标<select value={form.metric} onChange={(e) => setForm({ ...form, metric: e.target.value })}><option value="latest_nav">最新单位净值</option><option value="drawdown">最大回撤</option><option value="annualized_return">年化收益</option><option value="volatility">年化波动</option></select></label>
          <label>关系<select value={form.operator} onChange={(e) => setForm({ ...form, operator: e.target.value })}><option value="<=">≤</option><option value="<">&lt;</option><option value=">=">≥</option><option value=">">&gt;</option></select></label>
          <label>阈值<input type="number" step="0.0001" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} required /></label>
          <button className="button primary" disabled={busy !== "" || candidates.length === 0} type="submit">{busy === "create" ? "保存中…" : "保存条件"}</button>
        </form>
      </Card>
      <div className="stack">
        {items.map((item) => (
          <Card key={item.id}>
            <div className="trigger-row">
              <div><span className="eyebrow">{item.metric}</span><h2>{names[item.candidate_id] ?? `候选 #${item.candidate_id}`}</h2><p>当数值 {item.operator} {item.threshold}</p></div>
              <div className={item.last_matched ? "trigger-result matched" : "trigger-result"}><strong>{item.last_matched == null ? "未检查" : item.last_matched ? "已命中" : "未命中"}</strong><span>最近值 {item.last_value ?? "—"}</span></div>
              <button className="button danger" onClick={() => remove(item.id)} type="button">删除</button>
            </div>
          </Card>
        ))}
        {items.length === 0 && <Card><p className="empty">尚未保存触发条件。</p></Card>}
      </div>
    </>
  );
}

function Settings() {
  const [settings, setSettings] = useState<Record<string, string | number | boolean> | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const load = async () => {
    setBusy("load");
    try { setSettings(await api.get("/settings")); } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); } finally { setBusy(""); }
  };
  useEffect(() => { void load(); }, []);
  const testAI = async () => {
    setBusy("ai"); setNotice(null);
    try {
      const result = await api.post<{ ok: boolean; message: string; model?: string }>("/settings/ai/test");
      setNotice({ kind: result.ok ? "ok" : "error", text: `${result.message}${result.model ? `（${result.model}）` : ""}` });
    } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); } finally { setBusy(""); }
  };
  const exportData = async () => {
    setBusy("export"); setNotice(null);
    try {
      await api.download("/exports/full", `fundlab-export-${new Date().toISOString().slice(0, 10)}.json`);
      setNotice({ kind: "ok", text: "结构化数据导出已生成。" });
    } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); } finally { setBusy(""); }
  };
  return (
    <>
      <PageHeader eyebrow="LOCAL SETTINGS" title="运行设置" description="敏感配置只从本机环境变量读取，前端不会显示或保存 API Key。" action={<button className="button secondary" onClick={load} disabled={busy !== ""} type="button">{busy === "load" ? "刷新中…" : "刷新状态"}</button>} />
      <Notice value={notice} />
      <div className="two-column">
        <Card><span className="eyebrow">RISK</span><h2>风险参数</h2><div className="setting-row"><span>阶段性回撤参考</span><strong>{percent(settings?.risk_tolerance as number)}</strong></div><p className="muted">这个值参与决策门控与压力提示，但不代表能够在该位置成交或止损。</p></Card>
        <Card><span className="eyebrow">PROVIDERS</span><h2>本地能力</h2><div className="setting-row"><span>公开数据</span><strong>{String(settings?.market_provider ?? "—")}</strong></div><div className="setting-row"><span>截图识别</span><strong>{String(settings?.ocr ?? "—")}</strong></div><div className="setting-row"><span>原图保留</span><strong>{settings?.keep_uploads ? "是" : "否"}</strong></div></Card>
        <Card><span className="eyebrow">AI</span><h2>DeepSeek</h2><div className="setting-row"><span>启用状态</span><strong>{settings?.ai_enabled ? "已启用" : "Mock / 未启用"}</strong></div><div className="setting-row"><span>模型</span><strong>{String(settings?.ai_model ?? "—")}</strong></div><button className="button primary" onClick={testAI} disabled={busy !== ""} type="button">{busy === "ai" ? "测试中…" : "测试 AI 连接"}</button><p className="muted">测试请求不包含图片、持仓或交易数据，也不会自动启用 AI。</p></Card>
        <Card><span className="eyebrow">BOUNDARY</span><h2>数据边界</h2><ul><li>截图只在本机 OCR，并先进入草稿。</li><li>公开基金数据与个人事实分开保存。</li><li>DeepSeek 只能解释经过筛选的文字证据。</li><li>系统不登录支付宝，也不执行交易。</li></ul><button className="button secondary" onClick={exportData} disabled={busy !== ""} type="button">{busy === "export" ? "导出中…" : "导出结构化数据"}</button></Card>
      </div>
    </>
  );
}

export default App;
