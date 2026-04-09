"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, AlertTriangle, AlertCircle, Info, CheckCircle, TrendingUp, CheckSquare, MinusSquare, XSquare } from "lucide-react";
import type { ReportResponse } from "@/lib/api";
import { getPdfUrl } from "@/lib/api";

interface Props {
  report: ReportResponse;
}

const SEVERITY_CONFIG = {
  CRITICAL: { label: "Critical",  color: "badge-critical", icon: <AlertCircle className="w-3.5 h-3.5" /> },
  HIGH:     { label: "High",      color: "badge-high",     icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  MEDIUM:   { label: "Medium",    color: "badge-medium",   icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  LOW:      { label: "Low",       color: "badge-low",      icon: <CheckCircle className="w-3.5 h-3.5" /> },
  INFO:     { label: "Info",      color: "badge-info",     icon: <Info className="w-3.5 h-3.5" /> },
};

const PLATFORM_ICONS: Record<string, string> = {
  github: "🐙", gitlab: "🦊", aws: "☁️", azure: "🔷",
  gcp: "🌐", jenkins: "🏗️", sonarqube: "📊", snyk: "🛡️",
  argocd: "🚀", circleci: "⭕", bitbucket: "🧑‍💻",
};

function GitHubStatsCard({ meta }: { meta: Record<string, unknown> }) {
  const contributors = (meta.top_contributors as Array<{ login: string; contributions: number }>) ?? [];
  const s = (v: unknown) => String(v ?? "");
  return (
    <div className="space-y-2">
      {!!meta.login && (
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Account</span>
          <span className="text-gray-200">@{s(meta.login)}{meta.org ? ` · Org: ${s(meta.org)}` : ""}</span>
        </div>
      )}
      {meta.total_repos != null && (
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Repositories</span>
          <span className="text-gray-200">
            <span className="text-white font-bold">{s(meta.total_repos)}</span> total —{" "}
            <span className="text-teal-400">{s(meta.public_repos)} public</span>,{" "}
            <span className="text-gray-400">{s(meta.private_repos)} private</span>
          </span>
        </div>
      )}
      {meta.repos_with_actions != null && (
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">GitHub Actions</span>
          <span className="text-gray-200">
            <span className="text-white font-bold">{s(meta.repos_with_actions)}</span> repos,{" "}
            <span className="text-white font-bold">{s(meta.total_workflows)}</span> workflows
          </span>
        </div>
      )}
      {meta.commits_last_90_days != null && (
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Commits (90 days)</span>
          <span className="text-white font-bold">{s(meta.commits_last_90_days)}</span>
        </div>
      )}
      {meta.merged_prs_last_90_days != null && (
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Merged PRs (90 days)</span>
          <span className="text-white font-bold">{s(meta.merged_prs_last_90_days)}</span>
        </div>
      )}
      {meta.total_members != null && (
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Org Members</span>
          <span className="text-white font-bold">{s(meta.total_members)}</span>
        </div>
      )}
      {contributors.length > 0 && (
        <div className="pt-1 border-t border-white/5">
          <p className="text-xs text-gray-400 mb-1.5">Top Contributors</p>
          <div className="flex flex-wrap gap-1.5">
            {contributors.map((c) => (
              <span key={c.login} className="px-2 py-0.5 rounded-full bg-teal-500/10 border border-teal-500/20 text-xs text-teal-300">
                @{c.login} <span className="text-gray-500">({c.contributions})</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GenericStatsCard({ meta }: { meta: Record<string, unknown> }) {
  const skip = new Set(["platform", "login", "org"]);
  const entries = Object.entries(meta).filter(([k]) => !skip.has(k));
  return (
    <div className="space-y-2">
      {entries.map(([key, val]) => (
        <div key={key} className="flex justify-between text-xs">
          <span className="text-gray-400 capitalize">{key.replace(/_/g, " ")}</span>
          <span className="text-gray-200 text-right max-w-[60%] truncate">
            {Array.isArray(val) ? val.slice(0, 3).join(", ") : String(val)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function ReportViewer({ report }: Props) {
  const { summary, markdown, job_id } = report;
  const counts = summary?.by_severity ?? {};

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] as const).map((sev) => {
          const cfg = SEVERITY_CONFIG[sev];
          const count = counts[sev] ?? 0;
          return (
            <div
              key={sev}
              className={`rounded-xl border p-3 text-center ${cfg.color} bg-current bg-opacity-5`}
            >
              <div className="flex justify-center mb-1 opacity-80">{cfg.icon}</div>
              <div className="text-2xl font-bold">{count}</div>
              <div className="text-xs opacity-80">{cfg.label}</div>
            </div>
          );
        })}
      </div>

      {/* Platform breakdown */}
      {summary?.by_platform && Object.keys(summary.by_platform).length > 0 && (
        <div>
          <h3 className="text-sm text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Findings by Platform
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(summary.by_platform).map(([platform, count]) => (
              <div key={platform} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/5 border border-white/10">
                <span className="text-xs text-gray-300 capitalize">{platform}</span>
                <span className="text-sm font-semibold text-teal-400">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Platform Overview — live stats */}
      {report.platform_stats && Object.keys(report.platform_stats).length > 0 && (
        <div>
          <h3 className="text-sm text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Platform Overview
          </h3>
          <div className="space-y-3">
            {Object.entries(report.platform_stats).map(([pname, meta]) => (
              <div key={pname} className="rounded-xl border border-teal-500/20 bg-white/3 overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-slate-900 to-slate-800 border-b border-white/5">
                  <span className="text-lg">{PLATFORM_ICONS[pname] ?? "📦"}</span>
                  <span className="text-sm font-bold text-teal-400 uppercase tracking-wide">{pname}</span>
                  {!!(meta as Record<string, unknown>).org && (
                    <span className="text-xs text-gray-500 ml-1">· {String((meta as Record<string, unknown>).org)}</span>
                  )}
                </div>
                <div className="px-4 py-3">
                  {pname === "github"
                    ? <GitHubStatsCard meta={meta as Record<string, unknown>} />
                    : <GenericStatsCard meta={meta as Record<string, unknown>} />}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plugin audit trail */}
      {report.plugin_audit && report.plugin_audit.length > 0 && (
        <div>
          <h3 className="text-sm text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <CheckSquare className="w-4 h-4" /> Scan Coverage
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {report.plugin_audit.map((entry) => {
              const isAvailable = entry.status === "available";
              const isSkipped   = entry.status === "skipped";
              return (
                <div
                  key={entry.plugin}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs
                    ${isAvailable ? "bg-teal-500/10 border-teal-500/20" :
                      isSkipped   ? "bg-white/5 border-white/5 opacity-50" :
                                    "bg-red-500/10 border-red-500/20"}`}
                >
                  {isAvailable
                    ? <CheckSquare className="w-3.5 h-3.5 text-teal-400 flex-shrink-0" />
                    : isSkipped
                    ? <MinusSquare className="w-3.5 h-3.5 text-gray-600 flex-shrink-0" />
                    : <XSquare    className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium capitalize truncate ${isAvailable ? "text-teal-300" : "text-gray-500"}`}>
                      {entry.plugin.replace(/_/g, " ")}
                    </p>
                    {isAvailable && (
                      <p className="text-gray-500">{entry.findings} finding{entry.findings !== 1 ? "s" : ""}</p>
                    )}
                    {isSkipped && <p className="text-gray-600">no credentials</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* PDF download */}
      <div className="flex justify-end">
        <a
          href={getPdfUrl(job_id)}
          download={`observeops-report-${job_id.slice(0, 8)}.pdf`}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-500 to-electric text-white font-semibold rounded-full text-sm hover:from-teal-400 hover:to-blue-500 transition-all duration-300 hover:scale-105 glow-teal"
        >
          <Download className="w-4 h-4" />
          Download PDF Report
        </a>
      </div>

      {/* Markdown report */}
      <div className="prose prose-invert prose-sm max-w-none rounded-2xl border border-teal-500/10 bg-white/5 p-6">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => (
              <h1 className="text-2xl font-bold gradient-text mb-4">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-xl font-bold text-teal-400 mt-8 mb-3 border-b border-teal-500/20 pb-2">{children}</h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-lg font-semibold text-blue-400 mt-6 mb-2">{children}</h3>
            ),
            table: ({ children }) => (
              <div className="overflow-x-auto my-4">
                <table className="w-full text-sm">{children}</table>
              </div>
            ),
            th: ({ children }) => (
              <th className="bg-white/10 px-4 py-2 text-left text-teal-300 font-semibold">{children}</th>
            ),
            td: ({ children }) => (
              <td className="border-b border-white/5 px-4 py-2 text-gray-300">{children}</td>
            ),
            code: ({ children }) => (
              <code className="bg-white/10 px-1.5 py-0.5 rounded text-teal-300 text-xs">{children}</code>
            ),
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-teal-500 pl-4 text-gray-400 italic">{children}</blockquote>
            ),
          }}
        >
          {markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
