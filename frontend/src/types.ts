export type BucketKey = "defense" | "core" | "satellite";

export interface HoldingItem {
  id: number;
  fund_code: string;
  fund_name: string;
  fund_type: string;
  amount: number;
  weight: number;
  displayed_profit: number | null;
  bucket: BucketKey;
  assignment_source: string;
  quality_status: string;
  value_date: string | null;
}

export interface HoldingSnapshot {
  id: number;
  as_of_date: string;
  total_market_value: number;
  completeness: "complete" | "partial";
  source: string;
  note: string;
  created_at: string;
  items: HoldingItem[];
}

export interface BucketRule {
  label: string;
  low: number;
  mid: number;
  high: number;
  drawdown_reference: number;
  horizon_days: number;
}

export interface Portfolio {
  id: number;
  name: string;
  capital_budget: number;
  updated_at: string;
  rule_version: string;
  buckets: Record<BucketKey, BucketRule>;
  latest_snapshot: HoldingSnapshot | null;
  latest_draft?: HoldingSnapshot | null;
  current_bucket_summary: Partial<Record<BucketKey, BucketSummary>>;
}

export interface ImportDraftItem {
  id: number;
  fund_code: string;
  fund_name: string;
  amount: number | null;
  displayed_profit: number | null;
  bucket: BucketKey;
  confidence: number;
  issues: string;
  confirmed: boolean;
}

export interface ImportBatch {
  id: number;
  filename: string;
  status: "uploaded" | "needs_review" | "confirmed" | "partially_confirmed" | "failed";
  page_type: "holdings" | "candidates" | "unknown" | "unprocessed";
  raw_text: string;
  error: string;
  created_at: string;
  items: ImportDraftItem[];
}

export interface AiConfiguration {
  status: "disabled" | "incomplete" | "configured";
  enabled: boolean;
  key_configured: boolean;
  model: string | null;
  base_url: string;
  missing: string[];
  environment_overrides: string[];
}

export interface AiSettingsUpdate {
  enabled: boolean;
  api_key?: string;
  clear_api_key?: boolean;
  base_url: string;
  model: string;
}

export interface AiSettingsResponse extends AiConfiguration {
  message: string;
}

export interface AiEvidencePoint {
  text: string;
  evidence_ids: string[];
}

export interface AiExplanation {
  status: "ok" | "disabled" | "configuration_error" | "failed";
  summary: string;
  supporting_points: AiEvidencePoint[];
  counterpoints: AiEvidencePoint[];
  unknowns: string[];
  model?: string;
  cached?: boolean;
  created_at?: string;
}

export interface DataHealth {
  provider: string;
  fund_count: number;
  blocked_funds: number;
  limited_funds: number;
  latest_fetch: string | null;
  ocr: "ready" | "manual_only";
  ai: AiConfiguration["status"];
  ai_config: AiConfiguration;
}

export interface BucketSummary extends BucketRule {
  key: BucketKey;
  amount: number;
  weight: number;
  in_band: boolean;
  deviation_from_band: number;
}

export interface ReviewItem {
  id: number;
  fund_code: string | null;
  fund_name: string | null;
  reason_type: string;
  proposed_action: string;
  severity: string;
  title: string;
  detail: string;
  metrics: Record<string, unknown>;
  evidence_ids: number[];
  status: string;
  decision: { choice: string; note: string; decided_at: string } | null;
}

export interface Review {
  id: number;
  snapshot_id: number;
  status: "queued" | "running" | "completed" | "partial" | "failed";
  progress: number;
  verdict: "hold" | "review";
  verdict_label: string;
  data_quality: "ready" | "limited" | "blocked";
  as_of_date: string;
  rule_version: string;
  bucket_summary: Record<BucketKey, BucketSummary>;
  headlines: Array<{ kind: string; reason_type?: string; title: string; detail: string; severity: string }>;
  error: string;
  created_at: string;
  completed_at: string | null;
  items: ReviewItem[];
}

export interface DiscoveryCandidate {
  fund: Fund;
  bucket: BucketKey;
  compared_to: { code: string; name: string };
  suggestion: "值得进一步对照" | "观察候选";
  tier: "strong" | "watch" | "unknown";
  eligible: boolean;
  improvements: string[];
  counterpoints: string[];
  metrics: Record<string, number | null>;
}

export interface DiscoveryRun {
  id: number;
  snapshot_id: number;
  status: "queued" | "running" | "completed" | "partial" | "failed";
  progress: number;
  rule_version: string;
  results: DiscoveryCandidate[];
  error: string;
  created_at: string;
  completed_at: string | null;
}

export interface Fund {
  id: number;
  code: string;
  name: string;
  fund_type: string;
  subtype: string;
  peer_key: string;
  default_bucket: BucketKey;
  peer_percentile: number | null;
  expense_ratio: number | null;
  aum_yi: number | null;
  quality_status: string;
  value_date: string | null;
  source_name: string;
  purchase_status: string;
  redemption_status: string;
  manager: string;
  benchmark: string;
  tracked_index: string;
  currency: string;
  valuation_lag_note: string;
  target_risk: string;
  product_status: string;
  tracking_error: number | null;
  return_method: string;
}

export interface FundDetail {
  fund: Fund;
  nav: Array<{ date: string; value: number; total_return_quality: string }>;
  performance: {
    as_of_date: string;
    observations: number;
    total_return: number | null;
    return_1m: number | null;
    return_3m: number | null;
    return_1y: number | null;
    annualized_return: number | null;
    volatility: number | null;
    max_drawdown: number | null;
    sharpe: number | null;
    calmar: number | null;
  } | null;
  performance_chart: Array<{ date: string; cumulative_return: number; drawdown: number }>;
  evidence: Array<{ id: number; title: string; source_url: string; published_at: string; source_level: string; event_type: string; severity: string; verified: boolean }>;
  cache_used?: boolean;
  warning?: string;
}
