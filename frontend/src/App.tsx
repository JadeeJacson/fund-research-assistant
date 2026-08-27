import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import type { AiConfiguration, AiExplanation, AiSettingsResponse, AiSettingsUpdate, BucketKey, BucketSummary, DataHealth, DiscoveryRun, FundDetail, HoldingSnapshot, ImportBatch, Portfolio, Review, ReviewItem } from "./types";

const bucketOrder: BucketKey[] = ["defense", "core", "satellite"];
const bucketLabels: Record<BucketKey, string> = { defense: "流动防守仓", core: "核心配置仓", satellite: "卫星进攻仓" };
const actionLabels: Record<string, string> = { observe: "继续观察", reduce: "减仓复核", exit_review: "退出复核", compare: "对照替代" };
const reasonLabels: Record<string, string> = { data_quality: "数据问题", hard_risk: "硬风险", quality_deterioration: "质量恶化", alternative: "替代对照" };
const bucketColors: Record<BucketKey, string> = { defense: "#247A5A", core: "#5D7E70", satellite: "#B7791F" };

function money(value: number) { return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }).format(value); }
function percent(value: number | null | undefined) { return value == null ? "—" : `${(value * 100).toFixed(1)}%`; }
function dateText(value: string | null | undefined) { return value ? new Date(value).toLocaleDateString("zh-CN") : "—"; }
function profitText(value: number | null | undefined) { return value == null ? "未录入" : value > 0 ? `盈利 ${money(value)}` : value < 0 ? `亏损 ${money(Math.abs(value))}` : "持平 ¥0"; }
function ratioText(value: number | null | undefined) { return value == null ? "—" : value.toFixed(2); }
function metricTone(value: number | null | undefined, _inverse = false) { if (value == null || value === 0) return "neutral"; return value > 0 ? "positive" : "negative"; }

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

function StatusPill({ value }: { value: string }) {
  const tone = value === "ready" || value === "completed" || value === "hold" ? "good" : value === "blocked" || value === "failed" || value === "critical" ? "danger" : "warn";
  const labels: Record<string, string> = { ready: "数据就绪", limited: "数据有限", blocked: "数据阻断", completed: "已完成", partial: "部分完成", running: "评估中", queued: "等待中", failed: "失败", critical: "严重", high: "高", medium: "中", info: "信息" };
  return <span className={`pill ${tone}`}>{labels[value] ?? value}</span>;
}

function AiExplanationPanel({ runId }: { runId: number }) {
  const explanation = useMutation({ mutationFn: () => api.post<AiExplanation>(`/reviews/${runId}/explain`) });
  const result = explanation.data;
  return <div className="ai-explanation">
    <div className="ai-explanation-heading"><div><span className="eyebrow">AI EXPLANATION</span><strong>DeepSeek 辅助解释</strong></div><button className="button secondary" disabled={explanation.isPending} onClick={() => explanation.mutate()}>{explanation.isPending ? "正在整理证据…" : result ? "重新读取解释" : "生成 AI 解释"}</button></div>
    {!result && <p>只发送公开基金身份、匿名指标和已选证据；不会改变确定性结论。</p>}
    {explanation.error && <div className="notice error">{(explanation.error as Error).message}</div>}
    {result && result.status !== "ok" && <div className="notice warning">{result.summary}</div>}
    {result?.status === "ok" && <div className="ai-explanation-result"><p className="ai-summary">{result.summary}</p><div className="ai-point-grid"><div><h3>支持理由</h3>{result.supporting_points.length ? <ul>{result.supporting_points.map((point, index) => <li key={`${point.text}-${index}`}>{point.text}{point.evidence_ids.length > 0 && <small>引用 {point.evidence_ids.join("、")}</small>}</li>)}</ul> : <p>没有额外支持项。</p>}</div><div><h3>反方与限制</h3>{result.counterpoints.length ? <ul>{result.counterpoints.map((point, index) => <li key={`${point.text}-${index}`}>{point.text}{point.evidence_ids.length > 0 && <small>引用 {point.evidence_ids.join("、")}</small>}</li>)}</ul> : <p>没有额外反方项。</p>}</div></div>{result.unknowns.length > 0 && <p className="ai-unknowns">仍未知：{result.unknowns.join("；")}</p>}<small>{result.cached ? "已复用相同评估的缓存解释" : "本次新生成"}</small></div>}
  </div>;
}

function AllocationDonut({ summary, total }: { summary: Partial<Record<BucketKey, BucketSummary>>; total: number }) {
  const data = bucketOrder.map((key) => ({ key, name: bucketLabels[key], amount: summary[key]?.amount ?? 0, weight: summary[key]?.weight ?? 0 })).filter((item) => item.amount > 0);
  if (!data.length) return null;
  return <Card className="allocation-card"><div className="section-heading"><div><span className="eyebrow">POSITION MIX</span><h2>当前仓位结构</h2></div><strong>{money(total)}</strong></div><div className="allocation-content"><div className="donut-chart" role="img" aria-label="三仓金额比例环状图"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data} dataKey="amount" nameKey="name" innerRadius={62} outerRadius={88} paddingAngle={2} stroke="#FFFDF8" strokeWidth={3}>{data.map((item) => <Cell key={item.key} fill={bucketColors[item.key]} />)}</Pie></PieChart></ResponsiveContainer><div className="donut-center"><strong>{data.length}</strong><span>个有持仓仓位</span></div></div><div className="allocation-legend">{data.map((item) => <div key={item.key}><i style={{ background: bucketColors[item.key] }} /><span><strong>{item.name}</strong><small>{money(item.amount)}</small></span><b>{percent(item.weight)}</b></div>)}</div></div><p className="storage-note">比例按最近完整持仓快照总市值计算，不使用计划投入金额作为分母。</p></Card>;
}

function Shell({ children }: { children: ReactNode }) {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.get<Record<string, string>>("/health"), refetchInterval: 30_000 });
  const links = [
    ["/", "决策台", "本次判断与复核"], ["/portfolio", "我的组合", "持仓快照与三仓"],
    ["/funds", "基金详情", "质量、净值与证据"], ["/alternatives", "基金探索", "主动筛选与替代"],
    ["/history", "历史与数据", "运行留痕与设置"],
  ];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">仓</div><div><strong>基金仓位决策台</strong><small>个人研究 · 理性决策</small></div></div>
      <nav aria-label="主要导航">{links.map(([to, label, desc]) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}><span>{label}</span><small>{desc}</small></NavLink>)}</nav>
      <div className="system-state"><span className={`dot ${health.isSuccess ? "online" : ""}`} /><div><strong>{health.isSuccess ? "本地服务正常" : "正在连接"}</strong><small>{health.data?.rule_version ? `规则 ${health.data.rule_version}` : "等待健康检查"}</small></div></div>
    </aside>
    <main className="workspace">{children}</main>
  </div>;
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}

function Dashboard() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: () => api.get<Portfolio>("/portfolio") });
  const review = useQuery({
    queryKey: ["review", "latest"], queryFn: () => api.get<Review | null>("/reviews/latest"),
    refetchInterval: (query) => { const data = query.state.data as Review | null; return data && ["queued", "running"].includes(data.status) ? 1200 : false; },
  });
  const run = useMutation({
    mutationFn: () => api.post<{ run_id: number }>("/reviews"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["review"] }),
  });
  const latest = review.data;
  const ready = Boolean(portfolio.data?.latest_snapshot?.completeness === "complete");
  const headlineItems = latest?.headlines.filter((item) => item.reason_type !== "band_breach") ?? [];
  const queueItems = latest?.items.filter((item) => item.reason_type !== "band_breach") ?? [];
  return <>
    <PageHeader eyebrow="DECISION DESK" title="今天，需要动吗？" description="每次由你主动运行。系统检查数据、硬风险、基金质量和替代项；仓位比例只作展示。" action={<div className="page-actions"><NavLink className="button secondary large" to="/alternatives">探索基金</NavLink><button className="button primary large" disabled={!ready || run.isPending || latest?.status === "running"} onClick={() => run.mutate()}>{run.isPending || latest?.status === "running" ? "正在评估…" : "开始本次评估"}</button></div>} />
    {!portfolio.data?.latest_snapshot && <Card className="onboarding"><span className="step">首次使用</span><h2>先确认你的完整持仓</h2><p>投入金额可随时修改。录入所有基金并确认这是完整快照后，才能运行基金质量与风险评估。</p><button className="button primary" onClick={() => navigate("/portfolio")}>设置我的组合</button></Card>}
    {(portfolio.isLoading || review.isLoading) && <Card className="progress-card"><strong>正在读取本地组合与历史评估…</strong></Card>}
    {(portfolio.error || review.error) && <div className="notice error">{((portfolio.error || review.error) as Error).message}</div>}
    {run.error && <div className="notice error">{(run.error as Error).message}</div>}
    {latest && portfolio.data?.rule_version && latest.rule_version !== portfolio.data.rule_version && <div className="notice warning">当前显示的是规则 {latest.rule_version} 的历史结果；现行规则已更新为 {portfolio.data.rule_version}。请点击“开始本次评估”生成新结论，旧记录会保留在历史中。</div>}
    {portfolio.data?.latest_snapshot && <AllocationDonut summary={portfolio.data.current_bucket_summary ?? {}} total={portfolio.data.latest_snapshot.total_market_value} />}
    {latest && ["queued", "running"].includes(latest.status) && <Card className="progress-card"><div><strong>评估正在进行</strong><span>{latest.progress}%</span></div><div className="progress"><i style={{ width: `${latest.progress}%` }} /></div><p>正在刷新公开数据、核验事件并运行确定性规则。离开本页不会取消任务。</p></Card>}
    {latest && !["queued", "running"].includes(latest.status) && <>
      <Card className={`verdict ${latest.verdict === "hold" ? "hold" : "review"}`}>
        <div><span className="eyebrow">本次总判断 · {latest.as_of_date}</span><h2>{latest.verdict_label}</h2><p>{latest.verdict === "hold" ? "当前没有足够证据支持调整，继续按计划观察。" : "至少一项数据、硬风险、基金质量或替代条件需要你确认。"}</p></div>
        <div className="verdict-meta"><StatusPill value={latest.data_quality} /><span>规则 {latest.rule_version}</span><span>{latest.status === "partial" ? "部分基金被数据门阻断" : "结果已保存"}</span></div>
      </Card>
      <div className="bucket-grid">{bucketOrder.map((key) => { const item = latest.bucket_summary[key]; if (!item) return null; return <Card key={key} className={`bucket-card ${key}`}><div className="bucket-heading"><span>{item.label}</span><span className={`pill ${item.in_band ? "good" : "warn"}`}>{item.in_band ? "区间内" : "区间外 · 仅展示"}</span></div><strong className="bucket-value">{percent(item.weight)}</strong><div className="bucket-track"><i style={{ width: `${Math.min(item.weight * 100, 100)}%` }} /></div><div className="bucket-foot"><span>{money(item.amount)}</span><span>目标 {percent(item.low)}～{percent(item.high)}</span></div></Card>; })}</div>
      <div className="dashboard-grid">
        <Card><div className="section-heading"><div><span className="eyebrow">TOP EVIDENCE</span><h2>最需要看的三件事</h2></div><span>{headlineItems.length} 条</span></div>{headlineItems.length ? <div className="headline-list">{headlineItems.map((item, index) => <article key={`${item.title}-${index}`}><span className="number">0{index + 1}</span><div><strong>{item.title}</strong><p>{item.detail}</p></div><StatusPill value={item.severity} /></article>)}</div> : <p className="empty">本次没有触发强证据。</p>}</Card>
        <Card><div className="section-heading"><div><span className="eyebrow">REVIEW QUEUE</span><h2>复核队列</h2></div><span>{queueItems.length} 项</span></div>{queueItems.length ? <div className="review-list">{queueItems.slice(0, 5).map((item) => <ReviewRow key={item.id} item={item} compact />)}</div> : <p className="empty">没有待复核事项。</p>}</Card>
      </div>
      <Card><AiExplanationPanel runId={latest.id} /></Card>
    </>}
    {!latest && portfolio.data?.latest_snapshot && <Card className="empty-state"><h2>持仓已准备好</h2><p>点击“开始本次评估”，首次结论会保存到历史记录中。</p></Card>}
  </>;
}

type DraftRow = { fund_code: string; fund_name: string; amount: string; displayed_profit: string; bucket: BucketKey };
const blankRow = (): DraftRow => ({ fund_code: "", fund_name: "", amount: "", displayed_profit: "", bucket: "satellite" });

function snapshotRows(snapshot: HoldingSnapshot | null | undefined): DraftRow[] {
  return snapshot?.items.map((item) => ({ fund_code: item.fund_code, fund_name: item.fund_name, amount: item.amount.toString(), displayed_profit: item.displayed_profit?.toString() ?? "", bucket: item.bucket })) ?? [];
}

function mergeOcrRows(existing: DraftRow[], incoming: ImportBatch["items"]): { rows: DraftRow[]; updated: number; added: number } {
  const merged = new Map(existing.filter((row) => row.fund_code).map((row) => [row.fund_code, row]));
  let updated = 0;
  let added = 0;
  for (const item of incoming) {
    if (!item.fund_code) continue;
    const previous = merged.get(item.fund_code);
    const incomingName = item.fund_name && !item.fund_name.startsWith("待刷新基金") ? item.fund_name : "";
    if (previous) {
      merged.set(item.fund_code, {
        ...previous,
        fund_name: incomingName || previous.fund_name,
        amount: item.amount == null ? previous.amount : item.amount.toString(),
        displayed_profit: item.displayed_profit == null ? previous.displayed_profit : item.displayed_profit.toString(),
      });
      updated += 1;
    } else {
      merged.set(item.fund_code, {
        fund_code: item.fund_code,
        fund_name: incomingName || item.fund_name,
        amount: item.amount?.toString() ?? "",
        displayed_profit: item.displayed_profit?.toString() ?? "",
        bucket: item.bucket,
      });
      added += 1;
    }
  }
  return { rows: [...merged.values()], updated, added };
}

function PortfolioPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["portfolio"], queryFn: () => api.get<Portfolio>("/portfolio") });
  const imports = useQuery({ queryKey: ["imports"], queryFn: () => api.get<ImportBatch[]>("/imports") });
  const [budget, setBudget] = useState("");
  const [rows, setRows] = useState<DraftRow[]>([blankRow()]);
  const [complete, setComplete] = useState(true);
  const [source, setSource] = useState<"manual" | "ocr">("manual");
  const [batchId, setBatchId] = useState<number | null>(null);
  const [ocrResult, setOcrResult] = useState<ImportBatch | null>(null);
  const [notice, setNotice] = useState("");
  const ocrResultRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (query.data) setBudget(query.data.capital_budget.toString()); }, [query.data?.capital_budget]);
  const applyOcrResult = (data: ImportBatch) => {
    const existing = snapshotRows(query.data?.latest_snapshot);
    const merged = mergeOcrRows(existing, data.items);
    setRows(merged.rows.length ? merged.rows : [blankRow()]);
    setComplete(false);
    setSource("ocr");
    setBatchId(data.id);
    setOcrResult(data);
    setNotice(data.items.length ? `OCR 已提取 ${data.items.length} 条：更新已有持仓 ${merged.updated} 条，新增 ${merged.added} 条，并已自动归仓。未出现在截图中的原持仓已保留，请核对后再确认完整快照。` : "OCR 已读取图片文字，但没有找到可安全确认的具体基金；原持仓已保留，请查看原因和原始文本");
    client.invalidateQueries({ queryKey: ["imports"] });
    window.requestAnimationFrame(() => ocrResultRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
  };
  const saveBudget = useMutation({ mutationFn: () => api.put<Portfolio>("/portfolio", { name: "我的实验组合", capital_budget: Number(budget) }), onSuccess: (data) => { setNotice("预算已保存"); client.setQueryData(["portfolio"], data); } });
  const saveSnapshot = useMutation({
    mutationFn: () => {
      const payload = {
        as_of_date: new Date().toISOString().slice(0, 10),
        completeness: complete ? "complete" : "partial",
        items: rows.filter((row) => row.fund_code && Number(row.amount) > 0).map((row) => ({ ...row, amount: Number(row.amount), displayed_profit: row.displayed_profit.trim() === "" ? null : Number(row.displayed_profit) })),
      };
      return source === "ocr" && batchId
        ? api.post<HoldingSnapshot>(`/imports/${batchId}/confirm`, payload)
        : api.post<HoldingSnapshot>("/portfolio/snapshots", { ...payload, source });
    },
    onSuccess: () => { setNotice(complete ? "完整持仓快照已确认，可以开始评估；明细已显示在下方列表" : "部分快照已保存，不会参与仓位判断"); setBatchId(null); client.invalidateQueries({ queryKey: ["portfolio"] }); client.invalidateQueries({ queryKey: ["imports"] }); },
  });
  const upload = useMutation({
    mutationFn: async (file: File) => { const batch = await api.upload<{ id: number }>("/imports", file); return api.post<ImportBatch>(`/imports/${batch.id}/process`); },
    onSuccess: applyOcrResult,
  });
  const reprocess = useMutation({
    mutationFn: (id: number) => api.post<ImportBatch>(`/imports/${id}/process`),
    onSuccess: applyOcrResult,
  });
  const total = rows.reduce((sum, row) => sum + (Number(row.amount) || 0), 0);
  const updateRow = (index: number, patch: Partial<DraftRow>) => setRows((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  const selectedImport = ocrResult ?? imports.data?.[0] ?? null;
  const loadSnapshot = (snapshot: HoldingSnapshot) => {
    setRows(snapshotRows(snapshot));
    setSource("manual");
    setBatchId(null);
    setNotice("已把最近持仓载入校对表；修改后需要重新确认快照");
  };
  return <>
    <PageHeader eyebrow="PORTFOLIO" title="我的组合" description="这里只保存当前持仓快照，不保存逐笔交易。只有你确认的完整快照才会参与判断。" />
    {notice && <div className="notice">{notice}</div>}
    {query.data?.latest_draft && <div className="notice">存在 {dateText(query.data.latest_draft.as_of_date)} 的部分快照草稿；它不会覆盖最近的完整持仓，也不会参与评估。</div>}
    <div className="portfolio-top">
      <Card><span className="eyebrow">CAPITAL BUDGET</span><h2>计划投入金额</h2><div className="budget-input"><span>¥</span><input aria-label="计划投入金额" type="number" min="100" value={budget} onChange={(event) => setBudget(event.target.value)} placeholder="自行填写" /><button className="button secondary" onClick={() => saveBudget.mutate()} disabled={saveBudget.isPending || Number(budget) < 100}>保存</button></div>{query.data?.latest_snapshot && <button className="text-button" type="button" onClick={() => setBudget(query.data!.latest_snapshot!.total_market_value.toString())}>按最近快照金额填入</button>}<p>这是可修改的计划值，不作为仓位比例分母；仓位比例始终按最近完整快照总市值计算。</p></Card>
      <Card><span className="eyebrow">LATEST SNAPSHOT</span><h2>最近快照</h2><strong className="big-number">{query.data?.latest_snapshot ? money(query.data.latest_snapshot.total_market_value) : "尚未录入"}</strong><p>{query.data?.latest_snapshot ? `${dateText(query.data.latest_snapshot.as_of_date)} · ${query.data.latest_snapshot.completeness === "complete" ? "完整" : "部分"}快照` : "完成下方录入后即可运行评估"}</p></Card>
      <Card><span className="eyebrow">SCREENSHOT OCR</span><h2>从支付宝截图开始</h2><label className="file-button"><input type="file" disabled={query.isLoading || upload.isPending || reprocess.isPending} accept="image/png,image/jpeg,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) upload.mutate(file); }} /><span>{query.isLoading ? "正在读取原持仓…" : upload.isPending || reprocess.isPending ? "正在识别…" : "选择持仓截图"}</span></label><p>支持从中文名称核对基金代码并自动归仓；同代码会更新原行，草稿仍须人工核对。</p></Card>
    </div>
    {query.data?.latest_snapshot && <Card className="confirmed-holdings"><div className="section-heading"><div><span className="eyebrow">CONFIRMED SNAPSHOT</span><h2>当前已确认持仓</h2></div><div className="section-actions"><span>{query.data.latest_snapshot.items.length} 只 · {money(query.data.latest_snapshot.total_market_value)}</span><button className="button secondary" onClick={() => loadSnapshot(query.data!.latest_snapshot!)}>载入后修改</button></div></div>
      <div className="holding-table confirmed-table"><div className="holding-row table-head"><span>基金代码</span><span>基金名称</span><span>当前金额</span><span>个人持有收益</span><span>职责归仓</span><span>查看</span></div>{query.data.latest_snapshot.items.map((item) => <div className="holding-row" key={item.id}><strong>{item.fund_code}</strong><span>{item.fund_name || `待刷新基金 ${item.fund_code}`}</span><span>{money(item.amount)}</span><span className={item.displayed_profit == null ? "profit unknown" : item.displayed_profit >= 0 ? "profit positive" : "profit negative"}>{profitText(item.displayed_profit)}</span><span>{bucketLabels[item.bucket]}</span><NavLink to={`/funds/${item.fund_code}`}>详情</NavLink></div>)}</div>
      <p className="storage-note">该列表来自快照 #{query.data.latest_snapshot.id}，保存在本机 <code>data/private/fundlab_v2.sqlite3</code>。</p>
    </Card>}
    {(selectedImport || imports.isLoading) && <div ref={ocrResultRef}><Card className="ocr-result"><div className="section-heading"><div><span className="eyebrow">OCR RESULT</span><h2>截图识别结果</h2></div>{selectedImport && <div className="section-actions"><span>批次 #{selectedImport.id} · {selectedImport.status === "confirmed" ? "已确认" : selectedImport.status === "needs_review" ? "待校对" : selectedImport.status}</span><button className="button secondary" type="button" disabled={reprocess.isPending} onClick={() => reprocess.mutate(selectedImport.id)}>{reprocess.isPending ? "正在重新识别…" : "重新识别此截图"}</button></div>}</div>
      {imports.isLoading && <p>正在读取本地 OCR 历史…</p>}
      {selectedImport && <><div className="ocr-summary"><strong>{selectedImport.items.length} 条结构化基金记录</strong><span>页面判断：{selectedImport.page_type === "holdings" ? "持仓页" : selectedImport.page_type === "candidates" ? "自选/候选页" : "未能确认页面类型"}</span><span>文件：{selectedImport.filename}</span></div>
        {selectedImport.items.length === 0 && <div className="notice warning">OCR 已读取图片文字，但没有可靠匹配到具体基金。常见原因是截图没有六位代码、名称被截断，或“余额宝”等平台产品没有显示底层基金。可点击“重新识别此截图”；仍未匹配时请补充基金代码。</div>}
        {selectedImport.items.length > 0 && <div className="ocr-item-list">{selectedImport.items.map((item) => <article key={item.id}><div><strong>{item.fund_name}</strong><span>{item.fund_code} · {bucketLabels[item.bucket]} · 名称/文字置信度 {(item.confidence * 100).toFixed(0)}%</span></div><div><strong>{item.amount == null ? "金额待补充" : money(item.amount)}</strong><span>{profitText(item.displayed_profit)}</span></div><p>{item.issues}</p></article>)}</div>}
        {selectedImport.items.some((item) => item.displayed_profit != null) && <div className="notice">已识别到个人持有收益。它只用于展示你的当前收益状态，不参与基金质量或调仓判断。</div>}
        <details className="ocr-raw" open={ocrResult?.id === selectedImport.id}><summary>查看 OCR 原始识别文本</summary><pre>{selectedImport.raw_text || "没有识别到文字"}</pre></details>
        <p className="storage-note">原图保存在本机 <code>data/private/uploads-v2/</code>，识别文本、置信度和人工修订记录保存在 v2 数据库，不会发送给 DeepSeek。</p></>}
      {imports.data && imports.data.length > 1 && <details className="import-history"><summary>查看其他导入批次（{imports.data.length - 1}）</summary><div>{imports.data.slice(1).map((item) => <button type="button" key={item.id} onClick={() => { setOcrResult(item); window.requestAnimationFrame(() => ocrResultRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" })); }}>#{item.id} · {item.filename} · {item.items.length} 条</button>)}</div></details>}
    </Card></div>}
    <Card className="snapshot-editor"><div className="section-heading"><div><span className="eyebrow">{source === "ocr" ? "OCR REVIEW DRAFT" : "MANUAL HOLDINGS"}</span><h2>{source === "ocr" ? `校对 OCR 草稿${batchId ? ` #${batchId}` : ""}` : "录入当前全部持仓"}</h2></div><strong>合计 {money(total)}</strong></div>
      <div className="holding-table"><div className="holding-row table-head"><span>基金代码</span><span>基金名称</span><span>当前金额</span><span>持有收益（可选）</span><span>职责归仓</span><span /></div>{rows.map((row, index) => <div className="holding-row" key={`${row.fund_code}-${index}`}><input aria-label={`基金代码 ${index + 1}`} inputMode="numeric" maxLength={6} value={row.fund_code} onChange={(event) => updateRow(index, { fund_code: event.target.value.replace(/\D/g, "") })} placeholder="六位代码" /><input aria-label={`基金名称 ${index + 1}`} value={row.fund_name} onChange={(event) => updateRow(index, { fund_name: event.target.value })} placeholder="可留空，评估时刷新" /><input aria-label={`持仓金额 ${index + 1}`} type="number" min="0" value={row.amount} onChange={(event) => updateRow(index, { amount: event.target.value })} placeholder="元" /><input aria-label={`持有收益 ${index + 1}`} type="number" step="0.01" value={row.displayed_profit} onChange={(event) => updateRow(index, { displayed_profit: event.target.value })} placeholder="可不填；亏损填负数" /><select aria-label={`职责归仓 ${index + 1}`} value={row.bucket} onChange={(event) => updateRow(index, { bucket: event.target.value as BucketKey })}>{bucketOrder.map((key) => <option value={key} key={key}>{bucketLabels[key]}</option>)}</select><button className="icon-button" aria-label={`删除第 ${index + 1} 行`} onClick={() => setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}>×</button></div>)}</div>
      <div className="editor-actions"><button className="button secondary" onClick={() => setRows((current) => [...current, blankRow()])}>添加一只基金</button><label className="check"><input type="checkbox" checked={complete} onChange={(event) => setComplete(event.target.checked)} />我确认这是当前全部持仓</label><button className="button primary" disabled={saveSnapshot.isPending || !rows.some((row) => row.fund_code.length === 6 && Number(row.amount) > 0)} onClick={() => { if (!complete || window.confirm("确认这份快照包含当前全部持仓？保存后它将参与仓位评估。")) saveSnapshot.mutate(); }}>{saveSnapshot.isPending ? "正在保存…" : "确认持仓快照"}</button></div>
      {(query.error || saveBudget.error || saveSnapshot.error || upload.error || reprocess.error) && <div className="notice error">{((query.error || saveBudget.error || saveSnapshot.error || upload.error || reprocess.error) as Error).message}</div>}
    </Card>
  </>;
}

function FundPage() {
  const params = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [input, setInput] = useState(params.code ?? "");
  const code = params.code && /^\d{6}$/.test(params.code) ? params.code : "";
  const query = useQuery({ queryKey: ["fund", code], queryFn: () => api.get<FundDetail>(`/funds/${code}`), enabled: Boolean(code), retry: false });
  const refresh = useMutation({ mutationFn: () => api.post<FundDetail>(`/funds/${code}/refresh`), onSuccess: (data) => client.setQueryData(["fund", code], data) });
  return <>
    <PageHeader eyebrow="FUND RESEARCH" title="基金详情" description="区分公开事实、确定性计算、事件证据与未知项。单位净值不被解释为便宜或昂贵。" action={<form className="code-search" onSubmit={(event) => { event.preventDefault(); if (/^\d{6}$/.test(input)) navigate(`/funds/${input}`); }}><input aria-label="基金代码" value={input} onChange={(event) => setInput(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="输入六位基金代码" /><button className="button primary">查看</button></form>} />
    {!code && <Card className="empty-state"><h2>输入一只基金代码</h2><p>可以查看当前数据库中的事实；若尚未刷新，页面会提供真实公开数据刷新按钮。</p></Card>}
    {code && query.isLoading && <Card className="progress-card"><strong>正在读取基金事实与净值…</strong></Card>}
    {code && query.isError && <Card className="empty-state"><h2>尚未建立基金档案</h2><p>{(query.error as Error).message}</p><button className="button primary" onClick={() => refresh.mutate()} disabled={refresh.isPending}>{refresh.isPending ? "正在连接公开数据…" : "刷新真实公开数据"}</button>{refresh.error && <div className="notice error">{(refresh.error as Error).message}</div>}</Card>}
    {query.data?.warning && <div className="notice">{query.data.warning}</div>}
    {query.data && <FundDetailView detail={query.data} refresh={() => refresh.mutate()} refreshing={refresh.isPending} />}
  </>;
}

function FundDetailView({ detail, refresh, refreshing }: { detail: FundDetail; refresh: () => void; refreshing: boolean }) {
  const fund = detail.fund;
  const metrics = detail.performance;
  return <>
    <Card className="fund-hero"><div><div className="tag-row"><span className="pill neutral">{fund.code}</span><span className="pill neutral">{fund.fund_type}</span><StatusPill value={fund.quality_status} /></div><h2>{fund.name}</h2><p>{fund.peer_key || "同类尚未确认"} · 数据截至 {dateText(fund.value_date)}</p></div><button className="button secondary" onClick={refresh} disabled={refreshing}>{refreshing ? "刷新中…" : "刷新公开数据"}</button></Card>
    <div className="fund-grid">
      <Card><div className="section-heading"><div><span className="eyebrow">TOTAL RETURN & DRAWDOWN</span><h2>近一年基金表现</h2></div><span>{metrics ? `截至 ${dateText(metrics.as_of_date)}` : "累计净值不足"}</span></div>{detail.performance_chart.length ? <div className="chart performance-chart" role="img" aria-label="近一年累计收益率和回撤百分比走势图"><ResponsiveContainer width="100%" height="100%"><LineChart data={detail.performance_chart} margin={{ top: 8, right: 12, bottom: 4, left: 2 }}><XAxis dataKey="date" minTickGap={40} tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><YAxis width={54} tickLine={false} axisLine={false} tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`} /><Tooltip formatter={(value, name) => [`${(Number(value) * 100).toFixed(2)}%`, name]} labelFormatter={(label) => `日期 ${label}`} /><Legend /><Line name="累计收益率" type="monotone" dataKey="cumulative_return" stroke="#247A5A" strokeWidth={2.4} dot={false} /><Line name="同期回撤" type="monotone" dataKey="drawdown" stroke="#B4473A" strokeWidth={1.7} strokeDasharray="5 4" dot={false} /></LineChart></ResponsiveContainer></div> : <p className="empty">没有足够的累计净值，暂不生成收益率和回撤图。</p>}<p>以窗口首个累计净值归零，展示基金自身收益，不是你的个人持有收益。口径：{fund.return_method || "累计净值"}。</p></Card>
      <Card><span className="eyebrow">FUND FACTS</span><h2>产品事实</h2><dl className="fact-list"><div><dt>默认职责</dt><dd>{bucketLabels[fund.default_bucket]}</dd></div><div><dt>同类分位</dt><dd>{fund.peer_percentile == null ? "未知" : `${fund.peer_percentile.toFixed(1)}`}</dd></div><div><dt>资产规模</dt><dd>{fund.aum_yi == null ? "未知" : `${fund.aum_yi.toFixed(2)} 亿元`}</dd></div><div><dt>费率</dt><dd>{percent(fund.expense_ratio)}</dd></div><div><dt>申购 / 赎回</dt><dd>{fund.purchase_status} / {fund.redemption_status}</dd></div><div><dt>币种 / 状态</dt><dd>{fund.currency || "未知"} / {fund.product_status || "未知"}</dd></div><div><dt>跟踪误差</dt><dd>{fund.tracking_error == null ? "未知" : percent(fund.tracking_error)}</dd></div><div><dt>来源</dt><dd>{fund.source_name || "待刷新"}</dd></div></dl>{fund.valuation_lag_note && <p className="notice">{fund.valuation_lag_note}</p>}</Card>
    </div>
    <Card className="performance-metrics"><div className="section-heading"><div><span className="eyebrow">DETERMINISTIC METRICS</span><h2>收益与风险指标</h2></div><span>{metrics ? `${metrics.observations} 个净值观察值` : "不可计算"}</span></div>{metrics ? <div className="metric-grid"><article><span>近 1 月收益</span><strong className={metricTone(metrics.return_1m)}>{percent(metrics.return_1m)}</strong><small>约 21 个净值交易日</small></article><article><span>近 3 月收益</span><strong className={metricTone(metrics.return_3m)}>{percent(metrics.return_3m)}</strong><small>约 63 个净值交易日</small></article><article><span>近 1 年收益</span><strong className={metricTone(metrics.return_1y)}>{percent(metrics.return_1y)}</strong><small>约 252 个净值交易日</small></article><article><span>年化波动率</span><strong>{percent(metrics.volatility)}</strong><small>越高表示净值波动越大</small></article><article><span>最大回撤</span><strong className={metricTone(metrics.max_drawdown, true)}>{percent(metrics.max_drawdown)}</strong><small>窗口内高点至低点最大跌幅</small></article><article><span>简化夏普</span><strong>{ratioText(metrics.sharpe)}</strong><small>年化收益 ÷ 年化波动，无风险利率按 0</small></article><article><span>卡玛比率</span><strong>{ratioText(metrics.calmar)}</strong><small>年化收益 ÷ 最大回撤绝对值</small></article><article><span>窗口年化收益</span><strong className={metricTone(metrics.annualized_return)}>{percent(metrics.annualized_return)}</strong><small>仅用于统一窗口比较，不代表未来收益</small></article></div> : <p className="empty">累计净值不足，不能可靠计算收益、波动、回撤和风险调整指标。</p>}<p className="storage-note">这些是基金公开累计净值的确定性计算，不使用支付宝个人盈亏，也不由 AI 生成。</p></Card>
    <Card><div className="section-heading"><div><span className="eyebrow">EVENT EVIDENCE</span><h2>公告与事件</h2></div><span>{detail.evidence.length} 条</span></div>{detail.evidence.length ? <div className="evidence-table">{detail.evidence.map((item) => <article key={item.id}><div><strong>{item.title}</strong><span>{item.published_at} · 来源 {item.source_level} · {item.verified ? "已核验" : "待核验"}</span></div><StatusPill value={item.severity} /><a href={item.source_url} target="_blank" rel="noreferrer">查看来源</a></article>)}</div> : <p className="empty">暂无已保存事件。自动公告将在评估时刷新，也可在“历史与数据”手工补充。</p>}</Card>
  </>;
}

function AlternativesPage() {
  const params = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState(params.code ?? "");
  const code = params.code && /^\d{6}$/.test(params.code) ? params.code : "";
  const client = useQueryClient();
  const discovery = useQuery({
    queryKey: ["discovery", "latest"],
    queryFn: () => api.get<DiscoveryRun | null>("/discoveries/latest"),
    refetchInterval: (query) => { const data = query.state.data as DiscoveryRun | null; return data && ["queued", "running"].includes(data.status) ? 1200 : false; },
  });
  const startDiscovery = useMutation({
    mutationFn: () => api.post<{ run_id: number }>("/discoveries"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["discovery"] }),
  });
  const query = useQuery({ queryKey: ["alternatives", code], queryFn: () => api.get<Array<{ fund: Record<string, unknown>; tier: string; eligible: boolean; review_ready: boolean; persistence_count: number; improvements: string[]; counterpoints: string[]; metrics: Record<string, number | null> }>>(`/funds/${code}/alternatives`), enabled: Boolean(code), retry: false });
  return <>
    <PageHeader eyebrow="FUND DISCOVERY" title="基金探索与替代对照" description="主动寻找当前组合的同类候选，只展示多维改善和风险，不使用单一总分，也不生成直接买入指令。" action={<button className="button primary large" disabled={startDiscovery.isPending || ["queued", "running"].includes(discovery.data?.status ?? "")} onClick={() => startDiscovery.mutate()}>{startDiscovery.isPending || ["queued", "running"].includes(discovery.data?.status ?? "") ? "正在探索…" : "开始探索基金"}</button>} />
    {(discovery.error || startDiscovery.error) && <div className="notice error">{((discovery.error || startDiscovery.error) as Error).message}</div>}
    {discovery.data && ["queued", "running"].includes(discovery.data.status) && <Card className="progress-card"><div><strong>正在刷新持仓同类候选</strong><span>{discovery.data.progress}%</span></div><div className="progress"><i style={{ width: `${discovery.data.progress}%` }} /></div><p>按当前持仓的 peer 分类有限扫描，不遍历全市场全部基金。</p></Card>}
    {discovery.data && !["queued", "running"].includes(discovery.data.status) && <Card className="discovery-results"><div className="section-heading"><div><span className="eyebrow">DISCOVERY RESULT</span><h2>本次探索候选</h2></div><span>#{discovery.data.id} · {discovery.data.results.length} 只</span></div>{discovery.data.error && <div className="notice warning">部分同类刷新失败：{discovery.data.error}</div>}{discovery.data.results.length ? <div className="discovery-grid">{discovery.data.results.map((item) => <article key={item.fund.code} className={item.eligible ? "eligible" : ""}><div className="alternative-title"><div><span>{item.fund.code} · {bucketLabels[item.bucket]}</span><strong>{item.fund.name}</strong></div><span className={`pill ${item.eligible ? "good" : "warn"}`}>{item.suggestion}</span></div><p>相对当前持有：{item.compared_to.name}（{item.compared_to.code}）</p><h3>筛选通过项</h3><ul>{item.improvements.map((value) => <li key={value}>{value}</li>)}</ul><h3>风险与未知</h3><ul>{item.counterpoints.length ? item.counterpoints.map((value) => <li key={value}>{value}</li>) : <li>当前规则未发现关键恶化，仍需查看基金详情和公告。</li>}</ul><div className="alternative-meta"><span>{item.tier === "strong" ? "基础候选层" : item.tier === "watch" ? "观察候选层" : "资料待补层"}</span><span>数据截至 {dateText(item.fund.value_date)}</span><span>最大回撤 {percent(item.metrics.max_drawdown)}</span></div><div className="candidate-actions"><NavLink to={`/funds/${item.fund.code}`}>查看详情</NavLink><NavLink to={`/alternatives/${item.compared_to.code}`}>查看完整对照</NavLink></div></article>)}</div> : <p className="empty">本次没有发现同时满足至少两项显著改善的数据候选。不会用演示数据或降低门槛补位。</p>}</Card>}
    <Card className="single-comparison"><div className="section-heading"><div><span className="eyebrow">SINGLE FUND COMPARISON</span><h2>指定基金替代对照</h2></div></div><form className="code-search" onSubmit={(event) => { event.preventDefault(); if (/^\d{6}$/.test(input)) navigate(`/alternatives/${input}`); }}><input aria-label="当前持仓基金代码" value={input} onChange={(event) => setInput(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="当前持仓代码" /><button className="button secondary">生成对照</button></form></Card>
    {!code && <Card className="empty-state"><h2>输入当前持仓基金代码</h2><p>系统只在已缓存的同仓同类基金中比较；不足两项显著改善不会标记为替代候选。</p></Card>}
    {code && query.isLoading && <Card className="progress-card"><strong>正在刷新月度候选宇宙与最新净值…</strong></Card>}
    {query.isError && <div className="notice error">{(query.error as Error).message}</div>}
    {code && query.data && <Card><div className="section-heading"><div><span className="eyebrow">COMPARISON</span><h2>{code} 的多维对照</h2></div><span>最多 3 只</span></div>{query.data.length ? <div className="alternative-grid">{query.data.map((item) => <article key={String(item.fund.code)} className={item.review_ready ? "eligible" : ""}><div className="alternative-title"><div><span>{String(item.fund.code)}</span><strong>{String(item.fund.name)}</strong></div><StatusPill value={item.review_ready ? "ready" : "limited"} /></div><h3>明确改善</h3><ul>{item.improvements.length ? item.improvements.map((value) => <li key={value}>{value}</li>) : <li>未达到两项显著改善</li>}</ul><h3>反方与限制</h3><ul>{item.counterpoints.length ? item.counterpoints.map((value) => <li key={value}>{value}</li>) : <li>当前规则未发现关键恶化</li>}</ul><div className="alternative-meta"><span>{item.tier === "strong" ? "基础候选层" : item.tier === "watch" ? "观察候选层" : "资料待补层"}</span><span>{item.review_ready ? "已升级为替换复核" : item.eligible ? `有效对照 ${item.persistence_count}/2` : "尚未满足替代条件"}</span><span>最大回撤 {percent(item.metrics.max_drawdown)}</span></div></article>)}</div> : <p className="empty">当前月度候选宇宙中没有满足同类与数据门的候选。数据不足时不会以演示数据补位。</p>}</Card>}
  </>;
}

function ReviewRow({ item, compact = false }: { item: ReviewItem; compact?: boolean }) {
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const decision = useMutation({ mutationFn: (choice: string) => api.post(`/review-items/${item.id}/decision`, { user_choice: choice, note }), onSuccess: () => client.invalidateQueries({ queryKey: ["reviews"] }) });
  return <article className={`review-item ${compact ? "compact" : ""}`}><div className="review-main"><div className="review-tags"><span className="pill neutral">{reasonLabels[item.reason_type] ?? item.reason_type}</span><span className="pill neutral">{actionLabels[item.proposed_action] ?? item.proposed_action}</span><StatusPill value={item.severity} /></div><strong>{item.title}</strong><p>{item.detail}</p>{item.fund_code && <NavLink to={`/funds/${item.fund_code}`}>查看 {item.fund_code} 详情</NavLink>}</div>{!compact && <div className="decision-box">{item.decision ? <p>已选择：{item.decision.choice} · {item.decision.note || "无备注"}</p> : <><input value={note} onChange={(event) => setNote(event.target.value)} placeholder="可选备注" aria-label="复核决定备注" /><div><button disabled={decision.isPending} onClick={() => decision.mutate("agree")}>同意</button><button disabled={decision.isPending} onClick={() => decision.mutate("reject")}>拒绝</button><button disabled={decision.isPending} onClick={() => decision.mutate("defer")}>稍后</button></div></>}</div>}</article>;
}

function HistoryPage() {
  const client = useQueryClient();
  const reviews = useQuery({ queryKey: ["reviews"], queryFn: () => api.get<Review[]>("/reviews") });
  const health = useQuery({ queryKey: ["data-health"], queryFn: () => api.get<DataHealth>("/data-health") });
  const aiSettings = useQuery({ queryKey: ["ai-settings"], queryFn: () => api.get<AiConfiguration>("/settings/ai") });
  const aiTest = useMutation({ mutationFn: () => api.post<{ ok: boolean; status: string; message: string; model?: string }>("/settings/ai/test") });
  const [showAiSettings, setShowAiSettings] = useState(false);
  const [aiForm, setAiForm] = useState<AiSettingsUpdate>({ enabled: false, api_key: "", base_url: "https://api.deepseek.com", model: "deepseek-v4-flash" });
  const [evidence, setEvidence] = useState({ fund_code: "", title: "", source_url: "", published_at: new Date().toISOString().slice(0, 10), source_level: "B", content: "", event_type: "other", verified: false });
  const addEvidence = useMutation({ mutationFn: () => api.post("/evidence/manual", { ...evidence, fund_code: evidence.fund_code || null, evidence_kind: "manual" }), onSuccess: () => setEvidence((value) => ({ ...value, title: "", source_url: "", content: "" })) });
  const saveAiSettings = useMutation({
    mutationFn: (payload: AiSettingsUpdate) => api.put<AiSettingsResponse>("/settings/ai", payload),
    onSuccess: (result) => {
      setAiForm((value) => ({ ...value, api_key: "" }));
      client.setQueryData<AiConfiguration>(["ai-settings"], result);
      client.invalidateQueries({ queryKey: ["data-health"] });
    },
  });
  const aiConfig = aiSettings.data?.status ? aiSettings.data : health.data?.ai_config;
  const aiLabel = aiConfig?.status === "configured" ? "已配置" : aiConfig?.status === "incomplete" ? "配置不完整" : "开关已关闭";
  useEffect(() => {
    if (!aiSettings.data) return;
    setAiForm((value) => ({
      ...value,
      enabled: aiSettings.data.enabled,
      base_url: aiSettings.data.base_url,
      model: aiSettings.data.model ?? "deepseek-v4-flash",
      api_key: "",
    }));
  }, [aiSettings.data]);

  function submitAiSettings(event: FormEvent) {
    event.preventDefault();
    const apiKey = aiForm.api_key?.trim();
    saveAiSettings.mutate({ ...aiForm, api_key: apiKey || undefined, clear_api_key: false });
  }

  function clearAiKey() {
    if (!window.confirm("确定清除本机已保存的 DeepSeek API Key？清除后 AI 解释将不可用。")) return;
    saveAiSettings.mutate({ ...aiForm, api_key: undefined, clear_api_key: true });
  }

  return <>
    <PageHeader eyebrow="AUDIT TRAIL" title="历史与数据" description="查看每次评估、用户决定、数据健康和可选 AI。这里的记录不会执行或模拟交易。" action={<button className="button secondary" onClick={() => api.download("/exports/full", `fundlab-v2-${new Date().toISOString().slice(0, 10)}.json`)}>导出完整数据</button>} />
    {(reviews.isLoading || health.isLoading || aiSettings.isLoading) && <Card className="progress-card"><strong>正在读取运行留痕与数据健康…</strong></Card>}
    {(reviews.error || health.error || aiSettings.error) && <div className="notice error">{((reviews.error || health.error || aiSettings.error) as Error).message}</div>}
    <div className="health-grid">
      <Card><span className="eyebrow">MARKET DATA</span><h2>公开数据</h2><strong>{health.data?.provider ?? "检查中"}</strong><p>{health.data?.fund_count ?? 0} 只基金 · 最近获取 {dateText(health.data?.latest_fetch)}</p></Card>
      <Card><span className="eyebrow">LOCAL OCR</span><h2>本地识别</h2><strong>{health.data?.ocr === "ready" ? "RapidOCR 就绪" : "手工录入可用"}</strong><p>原图和草稿不会发送给 DeepSeek。</p></Card>
      <Card>
        <span className="eyebrow">DEEPSEEK</span><h2>可选解释</h2><strong>{aiLabel}</strong>
        {aiConfig && <div className="ai-config"><span>开关：{aiConfig.enabled ? "已开启" : "已关闭"}</span><span>API Key：{aiConfig.key_configured ? "已保存" : "未保存"}</span><span>模型：{aiConfig.model ?? "未填写"}</span>{aiConfig.missing.length > 0 && <span className="config-missing">缺少：{aiConfig.missing.join("、")}</span>}</div>}
        <div className="ai-actions"><button className="button primary" aria-expanded={showAiSettings} onClick={() => setShowAiSettings((value) => !value)}>{showAiSettings ? "收起配置" : "配置 AI"}</button><button className="button secondary" onClick={() => aiTest.mutate()} disabled={aiTest.isPending || aiConfig?.status !== "configured"}>{aiTest.isPending ? "正在测试…" : "测试连接"}</button></div>
        {aiTest.data && <div className={`notice ${aiTest.data.ok ? "" : "error"}`}>{aiTest.data.message}</div>}{aiTest.error && <div className="notice error">{(aiTest.error as Error).message}</div>}
      </Card>
    </div>
    {showAiSettings && <Card className="ai-settings-card">
      <div className="section-heading"><div><span className="eyebrow">LOCAL AI SETTINGS</span><h2>DeepSeek 配置</h2></div><StatusPill value={aiConfig?.status ?? "disabled"} /></div>
      <p className="settings-intro">配置只写入这台电脑上的项目 <code>.env</code>，保存后立即生效。已保存的 Key 永远不会回显；留空表示保留原 Key。</p>
      {aiConfig && aiConfig.environment_overrides.length > 0 && <div className="notice warning">以下值由启动环境覆盖，需先从启动脚本或系统环境中移除：{aiConfig.environment_overrides.join("、")}</div>}
      <form className="ai-settings-form" onSubmit={submitAiSettings}>
        <label className="check ai-enabled"><input type="checkbox" checked={aiForm.enabled} onChange={(event) => setAiForm({ ...aiForm, enabled: event.target.checked })} />启用 DeepSeek 解释</label>
        <label>API Key<input type="password" autoComplete="new-password" value={aiForm.api_key ?? ""} onChange={(event) => setAiForm({ ...aiForm, api_key: event.target.value })} placeholder={aiConfig?.key_configured ? "已保存；留空则不修改" : "请输入 DeepSeek API Key"} aria-describedby="ai-key-help" /></label>
        <small id="ai-key-help">Key 不进入数据库、日志或导出文件；它只由本机后端写入被 Git 忽略的 .env。</small>
        <div className="form-pair"><label>模型<select value={aiForm.model} onChange={(event) => setAiForm({ ...aiForm, model: event.target.value })}><option value="deepseek-v4-flash">deepseek-v4-flash</option><option value="deepseek-v4-pro">deepseek-v4-pro</option></select></label><label>Base URL<input type="url" required value={aiForm.base_url} onChange={(event) => setAiForm({ ...aiForm, base_url: event.target.value })} /></label></div>
        <div className="ai-form-actions"><button className="button primary" disabled={saveAiSettings.isPending}>{saveAiSettings.isPending ? "正在保存…" : "保存并立即生效"}</button>{aiConfig?.key_configured && <button type="button" className="button danger-outline" disabled={saveAiSettings.isPending} onClick={clearAiKey}>清除已保存 Key</button>}</div>
        {saveAiSettings.data && <div className="notice">{saveAiSettings.data.message}</div>}{saveAiSettings.error && <div className="notice error">{(saveAiSettings.error as Error).message}</div>}
      </form>
    </Card>}
    <div className="history-grid"><Card><div className="section-heading"><div><span className="eyebrow">REVIEW HISTORY</span><h2>评估历史</h2></div><span>{reviews.data?.length ?? 0} 次</span></div><div className="run-list">{reviews.data?.map((run) => <details key={run.id}><summary><span>#{run.id} · {run.as_of_date}</span><strong>{run.verdict_label}</strong><StatusPill value={run.status} /></summary><div className="run-body"><div className="run-meta"><StatusPill value={run.data_quality} /><span>规则 {run.rule_version}</span><span>{run.items.length} 项复核</span></div>{run.items.map((item) => <ReviewRow key={item.id} item={item} />)}<AiExplanationPanel runId={run.id} /></div></details>) ?? <p className="empty">暂无评估历史</p>}</div></Card>
      <Card><span className="eyebrow">MANUAL EVIDENCE</span><h2>补充公告或新闻</h2><form className="evidence-form" onSubmit={(event: FormEvent) => { event.preventDefault(); addEvidence.mutate(); }}><label>基金代码（可空）<input value={evidence.fund_code} onChange={(event) => setEvidence({ ...evidence, fund_code: event.target.value.replace(/\D/g, "").slice(0, 6) })} /></label><label>标题<input required value={evidence.title} onChange={(event) => setEvidence({ ...evidence, title: event.target.value })} /></label><label>来源链接<input required type="url" value={evidence.source_url} onChange={(event) => setEvidence({ ...evidence, source_url: event.target.value })} /></label><div className="form-pair"><label>发布日期<input type="date" value={evidence.published_at} onChange={(event) => setEvidence({ ...evidence, published_at: event.target.value })} /></label><label>来源等级<select value={evidence.source_level} onChange={(event) => setEvidence({ ...evidence, source_level: event.target.value })}><option>S</option><option>A</option><option>B</option><option>C</option></select></label></div><label>摘要<textarea value={evidence.content} onChange={(event) => setEvidence({ ...evidence, content: event.target.value })} /></label><label className="check"><input type="checkbox" checked={evidence.verified} onChange={(event) => setEvidence({ ...evidence, verified: event.target.checked })} />我已核对原始来源</label><button className="button primary" disabled={addEvidence.isPending}>保存证据</button>{addEvidence.isSuccess && <p className="success-text">证据已保存</p>}{addEvidence.error && <div className="notice error">{(addEvidence.error as Error).message}</div>}</form></Card></div>
  </>;
}

function App() {
  return <Shell><Routes><Route path="/" element={<Dashboard />} /><Route path="/portfolio" element={<PortfolioPage />} /><Route path="/funds" element={<FundPage />} /><Route path="/funds/:code" element={<FundPage />} /><Route path="/alternatives" element={<AlternativesPage />} /><Route path="/alternatives/:code" element={<AlternativesPage />} /><Route path="/history" element={<HistoryPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></Shell>;
}

export default App;
