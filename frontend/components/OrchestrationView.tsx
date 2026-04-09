"use client";
import { useEffect, useState, useCallback } from "react";
import { Loader2, CheckCircle2, XCircle, Clock, Cpu, Zap, ChevronRight, Info } from "lucide-react";
import { fetchSkills, type SkillDef, type StatusEvent } from "@/lib/api";
import type { LLMConfig } from "@/components/LLMSelector";

interface AgentState {
  status: "queued" | "running" | "done" | "error" | "skipped";
  messages: string[];
  findings: number;
  startedAt?: number;
  durationMs?: number;
}

interface Props {
  events: StatusEvent[];
  isRunning: boolean;
  scanLlm: LLMConfig;
  reportLlm: LLMConfig;
  credentials: Record<string, string>;
}

const STATUS_COLORS: Record<string, string> = {
  queued:  "text-gray-500 border-gray-700 bg-gray-900/40",
  running: "text-teal-300 border-teal-500/50 bg-teal-500/5",
  done:    "text-green-300 border-green-500/30 bg-green-500/5",
  error:   "text-red-300  border-red-500/30  bg-red-500/5",
  skipped: "text-gray-600 border-gray-800    bg-gray-900/20",
};

const STATUS_ICON = {
  queued:  <Clock className="w-4 h-4 text-gray-600" />,
  running: <Loader2 className="w-4 h-4 text-teal-400 animate-spin" />,
  done:    <CheckCircle2 className="w-4 h-4 text-green-400" />,
  error:   <XCircle className="w-4 h-4 text-red-400" />,
  skipped: <Clock className="w-4 h-4 text-gray-700" />,
};

// Map agent names from SSE events → skill names from YAML
const AGENT_TO_SKILL: Record<string, string> = {
  CloudAuditor:      "CloudAuditor",
  LogAnalyst:        "LogAnalyst",
  SecurityAuditor:   "SecurityAuditor",
  CICDGuard:         "CICDGuard",
  CodeReviewer:      "CodeReviewer",
  ReportSynthesizer: "ReportSynthesizer",
};

function fmt_ms(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

function fmt_usd(n: number): string {
  if (n < 0.001) return `< $0.001`;
  return `$${n.toFixed(4)}`;
}

export default function OrchestrationView({ events, isRunning, scanLlm, reportLlm, credentials }: Props) {
  const [skills, setSkills]         = useState<SkillDef[]>([]);
  const [agentStates, setAgentStates] = useState<Record<string, AgentState>>({});
  const [elapsed, setElapsed]       = useState(0);
  const [startTime, setStartTime]   = useState<number | null>(null);

  // Load skill definitions from backend
  useEffect(() => {
    fetchSkills().then(setSkills);
  }, []);

  // Tick for running elapsed timer
  useEffect(() => {
    if (!isRunning || !startTime) return;
    const id = setInterval(() => setElapsed(Date.now() - startTime), 500);
    return () => clearInterval(id);
  }, [isRunning, startTime]);

  // Process SSE events into per-agent state
  useEffect(() => {
    if (events.length === 0) return;

    setAgentStates((prev) => {
      const next = { ...prev };
      for (const ev of events) {
        const name = AGENT_TO_SKILL[ev.skill] ?? ev.skill;
        const cur = next[name] ?? { status: "queued", messages: [], findings: 0 };

        const now = Date.now();
        if (ev.status === "running" && cur.status !== "running") {
          next[name] = { ...cur, status: "running", startedAt: now };
          if (!startTime) setStartTime(now);
        } else if (ev.status === "done") {
          const dur = cur.startedAt ? now - cur.startedAt : undefined;
          next[name] = { ...cur, status: "done", findings: ev.findings_count, durationMs: dur };
        } else if (ev.status === "error") {
          const dur = cur.startedAt ? now - cur.startedAt : undefined;
          next[name] = { ...cur, status: "error", durationMs: dur };
        } else {
          // Progress message
          next[name] = { ...cur, messages: [...cur.messages.slice(-4), ev.status] };
        }
      }
      return next;
    });
  }, [events, startTime]);

  // Reset on new scan
  useEffect(() => {
    if (isRunning && events.length === 0) {
      setAgentStates({});
      setStartTime(null);
      setElapsed(0);
    }
  }, [isRunning, events.length]);

  // ── Estimates ─────────────────────────────────────────────────────────
  const estimates = useCallback(() => {
    if (!skills.length) return null;

    // Count active plugins per skill
    const activePluginCounts: Record<string, number> = {};
    for (const skill of skills) {
      const count = Object.entries(skill.plugins).filter(([, cfg]) =>
        cfg.credential_keys.some((k) => !!credentials[k])
      ).length;
      activePluginCounts[skill.name] = count;
    }

    // Scan time estimate
    let totalScanSec = 0;
    for (const skill of skills.filter((s) => s.name !== "ReportSynthesizer")) {
      const n = activePluginCounts[skill.name] || 0;
      totalScanSec += n * (skill.estimates?.scan_time_per_plugin_s ?? 20);
    }

    // Token & cost estimate (report synthesizer)
    const rSkill = skills.find((s) => s.name === "ReportSynthesizer");
    if (!rSkill) return null;

    const avgFindings = Object.values(activePluginCounts).reduce((a, b) => a + b * 3, 0);
    const promptTokens = (rSkill.estimates?.base_prompt_tokens ?? 800)
      + avgFindings * (rSkill.estimates?.tokens_per_finding ?? 65);
    const outputTokens = rSkill.estimates?.typical_output_tokens ?? 2500;
    const totalTokens  = promptTokens + outputTokens;

    // Provider info
    const providerKey = reportLlm.provider;
    const provInfo = rSkill.llm_providers?.[providerKey];
    const speed = provInfo?.speed_tokens_per_sec ?? 50;
    const cost  = provInfo?.cost_per_1k_tokens_usd ?? 0;
    const llmSec = Math.round(outputTokens / speed);
    const estCost = (totalTokens / 1000) * cost;

    return { totalScanSec, promptTokens, outputTokens, totalTokens, llmSec, estCost, provInfo };
  }, [skills, credentials, reportLlm]);

  const est = estimates();

  // ── Render ─────────────────────────────────────────────────────────────
  const totalDone = Object.values(agentStates).filter((s) => s.status === "done" || s.status === "error").length;
  const totalAgents = skills.length || 6;
  const progress = totalAgents > 0 ? Math.round((totalDone / totalAgents) * 100) : 0;

  return (
    <div className="space-y-6">

      {/* ── Overall progress ── */}
      {(isRunning || totalDone > 0) && (
        <div className="rounded-2xl border border-teal-500/20 bg-white/3 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-white">
              {isRunning ? "Audit in progress…" : "Audit complete"}
            </span>
            <span className="text-xs text-gray-400 tabular-nums">
              {isRunning ? fmt_ms(elapsed) : `Completed in ${fmt_ms(elapsed)}`}
            </span>
          </div>
          <div className="h-2 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-teal-500 to-electric transition-all duration-500"
              style={{ width: `${isRunning ? Math.max(progress, 5) : 100}%` }}
            />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-xs text-gray-600">{totalDone}/{totalAgents} agents complete</span>
            <span className="text-xs text-gray-600">{progress}%</span>
          </div>
        </div>
      )}

      {/* ── Agent pipeline ── */}
      <div>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Cpu className="w-3.5 h-3.5" /> Agent Pipeline
        </h3>
        <div className="space-y-2">
          {skills.map((skill, idx) => {
            const state = agentStates[skill.name] ?? { status: "queued", messages: [], findings: 0 };
            const lastMsg = state.messages[state.messages.length - 1] ?? "";
            const activePlugins = Object.entries(skill.plugins)
              .filter(([, cfg]) => cfg.credential_keys.some((k) => !!credentials[k]));
            const isReportSkill = skill.name === "ReportSynthesizer";
            const llmForSkill = isReportSkill ? reportLlm : (skill.llm_role === "scanning" ? scanLlm : null);
            const rSkill = skills.find((s) => s.name === "ReportSynthesizer");
            const provInfo = isReportSkill
              ? rSkill?.llm_providers?.[reportLlm.provider]
              : null;

            return (
              <div key={skill.name} className="flex gap-2">
                {/* Connector line */}
                <div className="flex flex-col items-center gap-0.5 pt-3 flex-shrink-0">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2
                    ${state.status === "done" ? "border-green-500 bg-green-500/10 text-green-400" :
                      state.status === "running" ? "border-teal-500 bg-teal-500/10 text-teal-400" :
                      state.status === "error" ? "border-red-500 bg-red-500/10 text-red-400" :
                      "border-gray-700 bg-gray-900/40 text-gray-600"}`}>
                    {state.status === "running" ? <Loader2 className="w-3 h-3 animate-spin" /> : idx + 1}
                  </div>
                  {idx < skills.length - 1 && (
                    <div className={`w-0.5 h-full min-h-[16px] rounded ${state.status === "done" ? "bg-green-500/40" : "bg-white/5"}`} />
                  )}
                </div>

                {/* Agent card */}
                <div className={`flex-1 rounded-xl border p-3 mb-1 transition-all duration-300 ${STATUS_COLORS[state.status]}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-base flex-shrink-0">{skill.icon}</span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-white">{skill.display_name}</span>
                          {STATUS_ICON[state.status]}
                        </div>
                        <p className="text-xs text-gray-500 truncate">{skill.description.slice(0, 80)}…</p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0 text-right">
                      {state.status === "done" && (
                        <span className="text-xs font-semibold text-green-400">
                          {state.findings} finding{state.findings !== 1 ? "s" : ""}
                        </span>
                      )}
                      {state.durationMs !== undefined && (
                        <span className="text-xs text-gray-600">{fmt_ms(state.durationMs)}</span>
                      )}
                    </div>
                  </div>

                  {/* Running message */}
                  {state.status === "running" && lastMsg && (
                    <p className="text-xs text-teal-400/80 mt-1.5 truncate">
                      <ChevronRight className="w-3 h-3 inline mr-0.5" />{lastMsg}
                    </p>
                  )}

                  {/* Plugin pills + LLM info */}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {activePlugins.slice(0, 8).map(([pname, cfg]) => (
                      <span key={pname} className="px-1.5 py-0.5 rounded bg-teal-500/10 border border-teal-500/15 text-xs text-teal-400" title={cfg.description}>
                        {pname}
                      </span>
                    ))}
                    {activePlugins.length === 0 && state.status === "queued" && (
                      <span className="text-xs text-gray-700">no credentials</span>
                    )}
                    {llmForSkill && (
                      <span className="ml-auto px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-xs text-purple-300 flex items-center gap-1">
                        <Zap className="w-2.5 h-2.5" />
                        {provInfo?.display ?? llmForSkill.provider}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Estimates panel ── */}
      {est && (
        <div className="rounded-2xl border border-purple-500/20 bg-white/3 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-2">
            <Info className="w-3.5 h-3.5" /> Pre-Scan Estimates
          </h3>

          <div className="grid grid-cols-2 gap-3">
            <EstCard label="Est. Scan Time" value={
              est.totalScanSec < 60
                ? `~${est.totalScanSec}s`
                : `~${Math.round(est.totalScanSec / 60)}m`
            } sub="based on active plugins" color="teal" />
            <EstCard label="LLM Response Time" value={`~${est.llmSec}s`}
              sub={est.provInfo?.display ?? reportLlm.provider} color="purple" />
            <EstCard label="Est. Prompt Tokens" value={est.promptTokens.toLocaleString()}
              sub={`+ ~${est.outputTokens.toLocaleString()} output`} color="blue" />
            <EstCard label="Est. Cost" value={fmt_usd(est.estCost)}
              sub={est.estCost === 0 ? "free (local model)" : `@ ${est.provInfo?.cost_per_1k_tokens_usd ?? 0}/1K tok`}
              color={est.estCost === 0 ? "green" : "orange"} />
          </div>

          {/* LLM info */}
          <div className="pt-3 border-t border-white/5 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Scan LLM (Skills 1–5)</span>
              <span className="text-gray-300 font-medium">{scanLlm.provider}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Report LLM (Skill 6)</span>
              <span className="text-purple-300 font-medium">
                {est.provInfo?.display ?? reportLlm.provider}
              </span>
            </div>
            {est.provInfo && (
              <>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">Output speed</span>
                  <span className="text-gray-300">{est.provInfo.speed_tokens_per_sec} tok/s</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">Context window</span>
                  <span className="text-gray-300">{est.provInfo.context_window.toLocaleString()} tokens</span>
                </div>
              </>
            )}
          </div>

          <p className="text-xs text-gray-700">
            * Estimates are based on YAML skill definitions and active credential count.
            Actual values depend on platform response times and LLM load.
          </p>
        </div>
      )}

      {/* Empty state */}
      {!isRunning && totalDone === 0 && (
        <div className="rounded-2xl border border-dashed border-white/10 p-10 flex flex-col items-center text-center gap-3">
          <Cpu className="w-10 h-10 text-gray-700" />
          <p className="text-gray-600 text-sm">
            Start a scan to see agent orchestration live.<br />
            Estimates above update as you add credentials.
          </p>
        </div>
      )}
    </div>
  );
}

function EstCard({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  const colorMap: Record<string, string> = {
    teal:   "text-teal-400   bg-teal-500/5   border-teal-500/20",
    purple: "text-purple-400 bg-purple-500/5 border-purple-500/20",
    blue:   "text-blue-400   bg-blue-500/5   border-blue-500/20",
    green:  "text-green-400  bg-green-500/5  border-green-500/20",
    orange: "text-orange-400 bg-orange-500/5 border-orange-500/20",
  };
  return (
    <div className={`rounded-xl border p-3 ${colorMap[color] ?? colorMap.teal}`}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-lg font-bold">{value}</p>
      <p className="text-xs opacity-60 mt-0.5">{sub}</p>
    </div>
  );
}
