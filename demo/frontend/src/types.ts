export interface SimulateRequest {
  actor: string;
  action: string;
  resource: string;
  payload?: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface PassportData {
  passport_id: string;
  actor: string;
  action: string;
  resource: string;
  timestamp: string;
  risk_score: number;
  decision: "ALLOW" | "WARN" | "BLOCK";
  risk_factors: string[];
  pipeline_ms: number;
  signature?: string;
  signed: boolean;
  human_summary: string;
  payload?: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface SimulateResponse {
  decision: "ALLOW" | "WARN" | "BLOCK";
  risk_score: number;
  risk_factors: string[];
  pipeline_ms: number;
  passport: PassportData;
  human_summary: string;
}

export interface HistoryEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  resource: string;
  risk_score: number;
  decision: "ALLOW" | "WARN" | "BLOCK";
  passport_id: string;
  response: SimulateResponse;
}
