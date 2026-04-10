"use client";
import { useState, useCallback, useEffect } from "react";
import { Play, Shield, Activity, Zap, Server, Code2, GitBranch, AlertTriangle, CheckCircle, XCircle, Loader2, RefreshCw, History } from "lucide-react";
import CredentialPanel from "@/components/CredentialPanel";
import LLMSelector, { type LLMConfig } from "@/components/LLMSelector";
import StatusLog from "@/components/StatusLog";
import ReportViewer from "@/components/ReportViewer";
import ReportHistory from "@/components/ReportHistory";
import OrchestrationView from "@/components/OrchestrationView";
import ReportChat from "@/components/ReportChat";
import {
  startAnalysis,
  fetchReport,
  subscribeToStatus,
  healthCheck,
  validateCredentials,
  type StatusEvent,
  type ReportResponse,
  type ValidationResult,
} from "@/lib/api";

const SKILLS = [
  { icon: <Server className="w-5 h-5" />,    label: "Cloud Auditor",     desc: "AWS · Azure · GCP · EKS · AKS · GKE" },
  { icon: <Activity className="w-5 h-5" />,  label: "Log Analyst",       desc: "CloudWatch · Syslog · App logs" },
  { icon: <Shield className="w-5 h-5" />,    label: "Security Auditor",  desc: "IAM · Open ports · Secret scanning" },
  { icon: <GitBranch className="w-5 h-5" />, label: "CI/CD Guard",       desc: "Jenkins · GitHub · ArgoCD · CircleCI" },
  { icon: <Code2 className="w-5 h-5" />,     label: "Code Reviewer",     desc: "SonarQube · Snyk · Dependabot" },
  { icon: <Zap className="w-5 h-5" />,       label: "Report Synthesizer",desc: "Executive PDF report via LLM" },
];

type Phase = "idle" | "validating" | "validated" | "scanning" | "done" | "error";

export default function HomePage() {
  const [credentials, setCredentials]         = useState<Record<string, string>>({});
  const [scanLlm,   setScanLlm]   = useState<LLMConfig>({ provider: "ollama" });
  const [reportLlm, setReportLlm] = useState<LLMConfig>({ provider: "ollama" });
  const [customInstructions, setCustomInstructions] = useState("");
  const [reportName, setReportName] = useState("");
  const [phase,  setPhase]                    = useState<Phase>("idle");
  const [jobId,  setJobId]                    = useState<string | null>(null);
  const [events, setEvents]                   = useState<StatusEvent[]>([]);
  const [report, setReport]                   = useState<ReportResponse | null>(null);
  const [error,  setError]                    = useState<string | null>(null);
  const [backendOk, setBackendOk]             = useState<boolean | null>(null);
  const [validationResults, setValidationResults] = useState<ValidationResult[]>([]);
  const [rightTab, setRightTab]               = useState<"scan" | "orchestration" | "history">("scan");

  useEffect(() => { healthCheck().then(setBackendOk); }, []);

  const handleCredentialChange = useCallback((key: string, value: string) => {
    setCredentials((prev) => ({ ...prev, [key]: value }));
    // Reset validation when credentials change
    setPhase((p) => (p === "validated" ? "idle" : p));
    setValidationResults([]);
  }, []);

  // ── Step 1: Validate connectivity ────────────────────────────────
  const runValidation = async () => {
    setPhase("validating");
    setValidationResults([]);
    setError(null);
    try {
      const res = await validateCredentials(credentials);
      setValidationResults(res.results);
      if (res.ready) {
        setPhase("validated");
      } else {
        setError("No platforms connected. Add valid credentials for at least one platform.");
        setPhase("idle");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Validation request failed");
      setPhase("error");
    }
  };

  // ── Step 2: Run audit (only after validation passes) ─────────────
  const startScan = async () => {
    // Clear previous report immediately and forcefully before anything else
    setReport(null);
    setError(null);
    setEvents([]);
    setJobId(null);
    setPhase("scanning");
    setRightTab("orchestration");

    try {
      const { job_id } = await startAnalysis({
        credentials,
        llm_provider: scanLlm.provider,
        report_llm: reportLlm.provider,
        llm_config: { scan: scanLlm as unknown as Record<string, unknown>, report: reportLlm as unknown as Record<string, unknown> },
        custom_instructions: customInstructions,
        report_name: reportName.trim(),
      });
      setJobId(job_id);

      // Poll with retries — gives backend time to persist the report file
      const fetchWithRetry = async (id: string, attempts = 6): Promise<ReportResponse> => {
        for (let i = 0; i < attempts; i++) {
          try {
            const r = await fetchReport(id);
            return r;
          } catch {
            if (i < attempts - 1) await new Promise((res) => setTimeout(res, 1500));
          }
        }
        throw new Error("Report unavailable after retries — check backend logs.");
      };

      const unsubscribe = subscribeToStatus(
        job_id,
        (evt) => setEvents((prev) => [...prev, evt]),
        async () => {
          try {
            const r = await fetchWithRetry(job_id);
            setReport(r);
            setPhase("done");
            setRightTab("scan");
          } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Report unavailable");
            setPhase("error");
          }
          unsubscribe();
        },
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Scan failed");
      setPhase("error");
    }
  };

  // Load a completed report from history
  const loadFromHistory = useCallback(async (histJobId: string) => {
    setRightTab("scan");
    setError(null);
    setEvents([]);
    try {
      const r = await fetchReport(histJobId);
      setReport(r);
      setJobId(histJobId);
      setPhase("done");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load report");
      setPhase("error");
    }
  }, []);

  const okCount     = validationResults.filter((r) => r.status === "ok").length;
  const failedCount = validationResults.filter((r) => r.status === "failed").length;

  return (
    <div className="relative min-h-screen bg-grid">
      {/* Background blobs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-teal-500/8 rounded-full blur-3xl animate-blob" />
        <div className="absolute top-1/2 right-1/4 w-96 h-96 bg-electric/8 rounded-full blur-3xl animate-blob animation-delay-2000" />
        <div className="absolute bottom-1/4 left-1/2 w-96 h-96 bg-grape/8 rounded-full blur-3xl animate-blob animation-delay-4000" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-12">
        {/* Hero */}
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-teal-500/10 border border-teal-500/20 rounded-full text-teal-400 text-sm mb-6">
            <span className="w-2 h-2 bg-teal-400 rounded-full animate-pulse" />
            Multi-Agent Infrastructure Auditing
          </div>
          <h1 className="text-5xl md:text-6xl font-bold mb-4">
            <span className="gradient-text">ObserveOps</span>
          </h1>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Read-only AI agents scan your cloud, CI/CD pipelines, and code repositories
            to generate an executive-grade security and compliance report.
          </p>
          {backendOk !== null && (
            <div className={`inline-flex items-center gap-2 mt-4 text-xs px-3 py-1 rounded-full ${backendOk ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${backendOk ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
              {backendOk ? "Backend connected" : "Backend offline — start uvicorn on port 8000"}
            </div>
          )}
        </div>

        {/* Skill badges */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-12">
          {SKILLS.map((skill, i) => (
            <div key={i} className="flex flex-col items-center text-center p-4 rounded-2xl border border-teal-500/15 bg-white/3 hover:border-teal-500/30 hover:bg-white/5 transition-all duration-300 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500/20 to-electric/20 flex items-center justify-center text-teal-400 mb-2 group-hover:scale-110 transition-transform">
                {skill.icon}
              </div>
              <p className="text-xs font-semibold text-white">{skill.label}</p>
              <p className="text-xs text-gray-600 mt-0.5">{skill.desc}</p>
            </div>
          ))}
        </div>

        {/* Main grid */}
        <div className="grid lg:grid-cols-[380px_1fr] gap-8">

          {/* ── Left panel ── */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-6">
              <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
                <Shield className="w-5 h-5 text-teal-400" />
                Configure Platforms
              </h2>
              <CredentialPanel credentials={credentials} onChange={handleCredentialChange} />
            </div>

            <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-6 space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-teal-400" />
                AI Model Routing
              </h2>
              <LLMSelector label="Scanning Model (Skills 1–5)" config={scanLlm} onChange={setScanLlm} />
              <LLMSelector label="Report Model (Skill 6)" config={reportLlm} onChange={setReportLlm} />
            </div>

            {/* ── Report Name ── */}
            <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-5 space-y-2">
              <label className="text-sm font-bold text-white flex items-center gap-2">
                <span className="text-teal-400">🏷️</span>
                Report Name
                <span className="text-xs font-normal text-gray-500">(optional)</span>
              </label>
              <input
                type="text"
                value={reportName}
                onChange={(e) => setReportName(e.target.value.slice(0, 80))}
                placeholder="e.g. Q2 2026 AWS Security Review"
                maxLength={80}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-teal-500/40 focus:bg-white/8 transition-colors"
              />
            </div>

            {/* ── Custom Instructions ── */}
            <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-6 space-y-3">
              <div className="flex items-start justify-between">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="text-teal-400">📋</span>
                  Custom Report Instructions
                  <span className="text-xs font-normal text-gray-500">(optional)</span>
                </h2>
                <span className={`text-xs tabular-nums ${customInstructions.length > 900 ? "text-orange-400" : "text-gray-600"}`}>
                  {customInstructions.length}/1000
                </span>
              </div>
              <textarea
                value={customInstructions}
                onChange={(e) => setCustomInstructions(e.target.value.slice(0, 1000))}
                placeholder={
                  "Add specific focus areas for this report, e.g.:\n" +
                  "• Include estimated AWS billing forecast for next month\n" +
                  "• Highlight all IAM roles with admin privileges\n" +
                  "• Flag any public S3 buckets storing user data\n" +
                  "• Check compliance with SOC2 access control requirements"
                }
                rows={5}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 resize-none focus:outline-none focus:border-teal-500/40 focus:bg-white/8 transition-colors"
              />
              <p className="text-xs text-gray-600">
                The AI will incorporate these requirements into the executive report alongside standard findings.
              </p>
            </div>

            {/* ── Step 1: Validate button ── */}
            <button
              onClick={runValidation}
              disabled={phase === "validating" || phase === "scanning"}
              className="w-full flex items-center justify-center gap-3 py-3 px-8 bg-white/5 border border-teal-500/30 text-teal-300 font-semibold rounded-full hover:bg-teal-500/10 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
            >
              {phase === "validating" ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Validating connectivity…</>
              ) : (
                <><RefreshCw className="w-4 h-4" /> Test Platform Connections</>
              )}
            </button>

            {/* Validation results */}
            {validationResults.length > 0 && (
              <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-4 space-y-2">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Connection Results</p>
                  <div className="flex gap-2 text-xs">
                    {okCount > 0 && <span className="text-green-400">{okCount} connected</span>}
                    {failedCount > 0 && <span className="text-red-400">{failedCount} failed</span>}
                  </div>
                </div>
                {validationResults.filter((r) => r.status !== "skipped").map((r) => (
                  <ValidationRow key={r.platform} result={r} />
                ))}
                {validationResults.filter((r) => r.status === "skipped").length > 0 && (
                  <p className="text-xs text-gray-600 pt-1">
                    {validationResults.filter((r) => r.status === "skipped").length} platform(s) skipped — no credentials provided
                  </p>
                )}
              </div>
            )}

            {/* ── Step 2: Launch audit (only enabled after validation) ── */}
            <button
              onClick={startScan}
              disabled={phase !== "validated" || !backendOk}
              className="w-full flex items-center justify-center gap-3 py-4 px-8 bg-gradient-to-r from-teal-500 to-electric text-white font-bold text-lg rounded-full hover:from-teal-400 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300 hover:scale-[1.02] glow-teal"
            >
              {phase === "scanning" ? (
                <><span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />Scanning…</>
              ) : (
                <><Play className="w-5 h-5" />Generate Audit Report</>
              )}
            </button>

            {phase !== "validated" && phase !== "scanning" && phase !== "done" && (
              <p className="text-center text-xs text-gray-600">
                Run <span className="text-teal-400">Test Platform Connections</span> first to validate credentials
              </p>
            )}
          </div>

          {/* ── Right panel ── */}
          <div className="space-y-6" id="status">

            {/* Tab bar */}
            <div className="flex gap-1 p-1 bg-white/5 rounded-xl border border-white/10">
              <TabBtn active={rightTab === "scan"}          onClick={() => setRightTab("scan")}
                icon={<Activity  className="w-4 h-4" />} label="Scan & Report" />
              <TabBtn active={rightTab === "orchestration"} onClick={() => setRightTab("orchestration")}
                icon={<Server    className="w-4 h-4" />} label="Orchestration" />
              <TabBtn active={rightTab === "history"}       onClick={() => setRightTab("history")}
                icon={<History   className="w-4 h-4" />} label="Report History" />
            </div>

            {/* ── Scan tab ── */}
            {rightTab === "scan" && (
              <>
                {/* Status log */}
                <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      <Activity className="w-5 h-5 text-teal-400" />
                      Scan Progress
                    </h2>
                    {jobId && <span className="text-xs text-gray-600 font-mono">Job: {jobId.slice(0, 8)}…</span>}
                  </div>
                  <StatusLog events={events} isRunning={phase === "scanning"} />
                </div>

                {/* Error */}
                {error && (
                  <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-red-300">Error</p>
                      <p className="text-xs text-red-400 mt-1">{error}</p>
                    </div>
                  </div>
                )}

                {/* Report */}
                {report && phase === "done" && (
                  <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-6" id="report">
                    <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
                      <Shield className="w-5 h-5 text-teal-400" />
                      Audit Report
                    </h2>
                    <ReportViewer report={report} />
                  </div>
                )}

                {/* Idle */}
                {(phase === "idle" || phase === "validated") && !report && (
                  <div className="rounded-2xl border border-dashed border-teal-500/20 p-12 flex flex-col items-center justify-center text-center">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-teal-500/10 to-electric/10 flex items-center justify-center mb-4">
                      <Shield className="w-8 h-8 text-teal-400/50" />
                    </div>
                    <p className="text-gray-500 text-sm">
                      {phase === "validated"
                        ? <><span className="text-teal-400 font-semibold">{okCount} platform{okCount !== 1 ? "s" : ""} ready.</span> Click <strong className="text-white">Generate Audit Report</strong> to start.</>
                        : <>Add credentials and click <strong className="text-teal-400">Test Platform Connections</strong> first.</>
                      }
                    </p>
                  </div>
                )}
              </>
            )}

            {/* ── Orchestration tab ── */}
            {rightTab === "orchestration" && (
              <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-6">
                <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
                  <Server className="w-5 h-5 text-teal-400" />
                  Agent Orchestration
                </h2>
                <OrchestrationView
                  events={events}
                  isRunning={phase === "scanning"}
                  scanLlm={scanLlm}
                  reportLlm={reportLlm}
                  credentials={credentials}
                />
              </div>
            )}

            {/* ── History tab ── */}
            {rightTab === "history" && (
              <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-6">
                <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
                  <History className="w-5 h-5 text-teal-400" />
                  Report History
                </h2>
                <ReportHistory onLoad={loadFromHistory} activeJobId={jobId} />
              </div>
            )}
          </div>
        </div>

      {/* ── Report Chat Agent — shown whenever a completed report is loaded ── */}
      {report && phase === "done" && jobId && (
        <ReportChat
          jobId={jobId}
          reportName={report.report_name ?? reportName}
          llmProvider={reportLlm.provider}
          llmConfig={reportLlm}
        />
      )}

        {/* Footer */}
        <footer className="mt-20 text-center text-xs text-gray-600 border-t border-white/5 pt-8">
          <p>
            ObserveOps — Built by{" "}
            <a href="https://zaftech.ca" className="text-teal-400 hover:text-teal-300" target="_blank" rel="noopener noreferrer">ZafTech</a>
            {" "}· All scans are read-only · Credentials are never stored
          </p>
        </footer>
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-sm font-medium transition-all duration-200
        ${active ? "bg-teal-500/20 text-teal-300 border border-teal-500/30" : "text-gray-500 hover:text-gray-300"}`}
    >
      {icon}
      {label}
    </button>
  );
}

function ValidationRow({ result }: { result: ValidationResult }) {
  const isOk     = result.status === "ok";
  const isFailed = result.status === "failed";
  return (
    <div className={`flex items-start gap-2 p-2 rounded-lg text-xs ${isOk ? "bg-green-500/10" : "bg-red-500/10"}`}>
      {isOk
        ? <CheckCircle className="w-3.5 h-3.5 text-green-400 flex-shrink-0 mt-0.5" />
        : <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />}
      <div className="flex-1 min-w-0">
        <span className={`font-semibold capitalize ${isOk ? "text-green-300" : "text-red-300"}`}>{result.platform}</span>
        <span className={`ml-2 ${isOk ? "text-green-400/70" : "text-red-400/70"}`}>{result.message}</span>
        {isFailed && result.detail && (
          <p className="text-red-500/70 mt-0.5 truncate" title={result.detail}>{result.detail}</p>
        )}
      </div>
    </div>
  );
}
