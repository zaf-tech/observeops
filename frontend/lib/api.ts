const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AnalyzeRequest {
  credentials: Record<string, string>;
  llm_provider: string;
  report_llm: string;
  llm_config?: { scan: Record<string, unknown>; report: Record<string, unknown> };
  custom_instructions?: string;
}

export interface AnalyzeResponse {
  job_id: string;
  message: string;
}

export interface StatusEvent {
  skill: string;
  status: "running" | "done" | "error" | "complete";
  findings_count: number;
}

export interface ValidationResult {
  platform: string;
  status: "ok" | "failed" | "skipped";
  message: string;
  detail?: string;
}

export interface ValidationResponse {
  results: ValidationResult[];
  ready: boolean;
}

export interface PluginAuditEntry {
  plugin: string;
  status: "available" | "skipped" | "error";
  findings: number;
}

export interface ReportResponse {
  job_id: string;
  markdown: string;
  summary: {
    total: number;
    by_severity: Record<string, number>;
    by_platform: Record<string, number>;
    by_category: Record<string, number>;
  };
  findings: Finding[];
  plugin_audit: PluginAuditEntry[];
  platform_stats: Record<string, Record<string, unknown>>;
}

export interface Finding {
  platform: string;
  resource: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
  category: string;
  finding: string;
  recommendation: string;
  evidence: Record<string, unknown>;
}

export interface Plugin {
  name: string;
  available: boolean;
  credential_keys: string[];
}

// ── API calls ────────────────────────────────────────────────────────

export async function startAnalysis(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Analysis failed: ${res.statusText}`);
  return res.json();
}

export async function fetchReport(jobId: string): Promise<ReportResponse> {
  const res = await fetch(`${API_BASE}/api/report/${jobId}`);
  if (!res.ok) throw new Error(`Report fetch failed: ${res.statusText}`);
  return res.json();
}

export function getPdfUrl(jobId: string): string {
  return `${API_BASE}/api/report/${jobId}/pdf`;
}

export async function fetchPlugins(): Promise<Plugin[]> {
  try {
    const res = await fetch(`${API_BASE}/api/plugins`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.plugins || [];
  } catch {
    return [];
  }
}

export interface JobSummary {
  job_id: string;
  status: "running" | "completed" | "error";
  started_at: string;
  completed_at: string | null;
  scan_llm: string;
  report_llm: string;
  platforms: string[];
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  error?: string;
}

export async function listReports(): Promise<JobSummary[]> {
  try {
    const res = await fetch(`${API_BASE}/api/reports`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.jobs || [];
  } catch {
    return [];
  }
}

export async function deleteReport(jobId: string): Promise<void> {
  await fetch(`${API_BASE}/api/reports/${jobId}`, { method: "DELETE" });
}

export async function validateCredentials(credentials: Record<string, string>): Promise<ValidationResponse> {
  const res = await fetch(`${API_BASE}/api/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credentials }),
  });
  if (!res.ok) throw new Error(`Validation failed: ${res.statusText}`);
  return res.json();
}

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

export function subscribeToStatus(
  jobId: string,
  onEvent: (event: StatusEvent) => void,
  onDone: () => void,
): () => void {
  const es = new EventSource(`${API_BASE}/api/status/${jobId}`);
  es.onmessage = (e) => {
    const event: StatusEvent = JSON.parse(e.data);
    onEvent(event);
    if (event.skill === "DONE" || event.status === "complete") {
      es.close();
      onDone();
    }
  };
  es.onerror = () => {
    es.close();
    onDone();
  };
  return () => es.close();
}
