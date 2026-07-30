export type Page = "dashboard" | "candidates" | "imports" | "portfolio" | "triggers" | "settings";

export interface Candidate {
  id: number;
  fund_code: string;
  fund_name: string;
  share_class: string;
  fund_type: string;
  note: string;
  planned_amount: number | null;
  latest_nav: number | null;
  nav_date: string | null;
  data_source: string;
  refreshed_at: string | null;
  created_at: string;
}

export interface Holding {
  id: number;
  fund_code: string;
  fund_name: string;
  amount: number;
  weight: number | null;
  holding_profit: number | null;
  snapshot_date: string;
  source: string;
  created_at: string;
}

export interface Transaction {
  id: number;
  fund_code: string;
  fund_name: string;
  action: string;
  amount: number | null;
  shares: number | null;
  nav: number | null;
  fee: number | null;
  trade_time: string;
  source: string;
  created_at: string;
}

export interface ImportItem {
  id: number;
  kind: "candidate" | "holding" | "transaction";
  fund_code: string;
  fund_name: string;
  action: string;
  amount: number | null;
  shares: number | null;
  event_time: string | null;
  confidence: number;
  issues: string;
  confirmed: boolean;
}

export interface ImportBatch {
  id: number;
  filename: string;
  page_type: string;
  raw_text: string;
  status: string;
  error: string;
  created_at: string;
  items: ImportItem[];
}

export interface Trigger {
  id: number;
  candidate_id: number;
  metric: string;
  operator: string;
  threshold: number;
  enabled: boolean;
  last_value: number | null;
  last_matched: boolean | null;
  checked_at: string | null;
}

export interface Evidence {
  id: number;
  candidate_id: number;
  title: string;
  source_url: string;
  published_at: string;
  trust_level: "S" | "A" | "B" | "C";
  content: string;
  created_at: string;
}

export interface Report {
  report_id: number;
  horizon: "short" | "long";
  as_of_date: string;
  current_weight: number;
  candidate: Candidate;
  metrics: Record<string, number | string | null>;
  decision: {
    state: string;
    target_weight: [number, number];
    confidence: string;
    positive_points: string[];
    risk_points: string[];
    unknowns: string[];
    triggers: Array<{ description: string }>;
    valid_days: number;
    disclaimer?: string;
  };
  ai_explanation?: {
    status: string;
    summary?: string;
    supporting_points?: Array<{ text: string; evidence_ids: string[] }>;
    counterpoints?: Array<{ text: string; evidence_ids: string[] }>;
    unknowns?: string[];
  };
}
