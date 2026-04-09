"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, AlertTriangle, AlertCircle, Info, CheckCircle, TrendingUp, CheckSquare, MinusSquare, XSquare, DollarSign } from "lucide-react";
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

// ── Multi-cloud billing types ────────────────────────────────────────
interface BillingMonth { month: string; amount: number; unit?: string; }
interface BillingService { service: string; amount: number; unit?: string; }
interface BillingBudget { name: string; budget: number | null; currency?: string; }
interface ProviderBilling {
  currency?: string;
  historical_months?: BillingMonth[];
  current_month?: string;
  current_mtd?: { amount: number; unit?: string };
  forecast?: { amount: number; unit?: string };
  top_services?: BillingService[];
  budgets?: BillingBudget[];
  project_id?: string;
  billing_account?: string;
  note?: string;
}
type BillingByProvider = Record<string, ProviderBilling>;

const PROVIDER_META: Record<string, { icon: string; color: string; accent: string; label: string }> = {
  aws:   { icon: "☁️",  color: "border-orange-500/30 bg-orange-500/5",  accent: "#f97316", label: "AWS"   },
  azure: { icon: "🔷",  color: "border-blue-500/30 bg-blue-500/5",      accent: "#3b82f6", label: "Azure" },
  gcp:   { icon: "🌐",  color: "border-yellow-500/30 bg-yellow-500/5",  accent: "#eab308", label: "GCP"   },
};

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toFixed(2)}`;
}

function fmtFull(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function MiniSparkBar({ months, accent, mtd, forecast }: {
  months: BillingMonth[];
  accent: string;
  mtd?: { amount: number };
  forecast?: { amount: number };
}) {
  const bars: { label: string; amount: number; type: "hist" | "mtd" | "forecast" }[] = [
    ...months.map(m => ({ label: m.month, amount: m.amount, type: "hist" as const })),
    ...(mtd ? [{ label: "MTD", amount: mtd.amount, type: "mtd" as const }] : []),
    ...(forecast ? [{ label: "Forecast", amount: forecast.amount, type: "forecast" as const }] : []),
  ];
  const max = Math.max(...bars.map(b => b.amount), 1);

  return (
    <div className="flex items-end gap-1 h-20 mt-2">
      {bars.map((b, i) => {
        const pct = Math.max((b.amount / max) * 100, 3);
        const color = b.type === "forecast"
          ? "bg-orange-500/60 border border-orange-400/40 border-dashed"
          : b.type === "mtd"
          ? "bg-blue-500/60 border border-blue-400/30"
          : "bg-teal-500/40 border border-teal-500/20";
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-0.5 min-w-0 group relative">
            {/* Tooltip */}
            <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:flex bg-gray-900 text-white text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap z-10 border border-white/10">
              {b.label}: {fmtFull(b.amount)}
            </div>
            <span className="text-[8px] text-gray-500 tabular-nums truncate w-full text-center">{fmt(b.amount)}</span>
            <div className={`w-full rounded-t-sm cursor-pointer ${color}`} style={{ height: `${pct}%` }} />
            <span className="text-[7px] text-gray-600 truncate w-full text-center leading-tight">
              {b.type === "forecast" ? "Fcst" : b.type === "mtd" ? "MTD" : b.label.replace(/\s\d{4}/, "")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ServiceBreakdown({ services, accent }: { services: BillingService[]; accent: string }) {
  const top = services.slice(0, 8);
  const maxAmt = top[0]?.amount || 1;
  return (
    <div className="space-y-1.5 mt-3">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Top Services This Month</p>
      {top.map((svc) => {
        const pct = (svc.amount / maxAmt) * 100;
        return (
          <div key={svc.service} className="flex items-center gap-2">
            <span className="text-[10px] text-gray-400 w-36 truncate flex-shrink-0" title={svc.service}>{svc.service}</span>
            <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: accent + "99" }} />
            </div>
            <span className="text-[10px] text-gray-300 tabular-nums w-14 text-right flex-shrink-0">{fmtFull(svc.amount)}</span>
          </div>
        );
      })}
    </div>
  );
}

function ProviderBillingCard({ provider, data }: { provider: string; data: ProviderBilling }) {
  const meta    = PROVIDER_META[provider] ?? { icon: "💰", color: "border-teal-500/20 bg-teal-500/5", accent: "#14b8a6", label: provider.toUpperCase() };
  const hist    = data.historical_months ?? [];
  const hasCost = hist.length > 0 || data.current_mtd;

  // Month-over-month trend
  let trendPct: number | null = null;
  if (hist.length >= 2) {
    const prev = hist[hist.length - 2].amount;
    const curr = hist[hist.length - 1].amount;
    if (prev > 0) trendPct = ((curr - prev) / prev) * 100;
  }

  const totalSpend = hist.reduce((s, m) => s + m.amount, 0);

  return (
    <div className={`rounded-xl border p-4 ${meta.color}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xl">{meta.icon}</span>
          <div>
            <p className="text-sm font-bold text-white">{meta.label}</p>
            {data.project_id && <p className="text-[10px] text-gray-500">Project: {data.project_id}</p>}
            {data.billing_account && <p className="text-[10px] text-gray-500">Acct: {data.billing_account}</p>}
          </div>
        </div>
        <div className="text-right">
          {data.current_mtd && (
            <p className="text-lg font-bold text-white tabular-nums">{fmtFull(data.current_mtd.amount)}</p>
          )}
          {data.current_mtd && <p className="text-[9px] text-gray-500">{data.current_month} MTD</p>}
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-3 gap-2 mt-3">
        <div className="rounded-lg bg-white/5 p-2 text-center">
          <p className="text-xs font-bold text-white tabular-nums">{fmt(totalSpend)}</p>
          <p className="text-[9px] text-gray-500">6-month total</p>
        </div>
        <div className="rounded-lg bg-white/5 p-2 text-center">
          {data.forecast ? (
            <>
              <p className="text-xs font-bold text-orange-300 tabular-nums">{fmt(data.forecast.amount)}</p>
              <p className="text-[9px] text-gray-500">Month forecast</p>
            </>
          ) : (
            <>
              <p className="text-xs font-bold text-gray-500">—</p>
              <p className="text-[9px] text-gray-600">No forecast</p>
            </>
          )}
        </div>
        <div className="rounded-lg bg-white/5 p-2 text-center">
          {trendPct !== null ? (
            <>
              <p className={`text-xs font-bold tabular-nums ${trendPct > 10 ? "text-red-400" : trendPct < -5 ? "text-green-400" : "text-gray-300"}`}>
                {trendPct > 0 ? "+" : ""}{trendPct.toFixed(1)}%
              </p>
              <p className="text-[9px] text-gray-500">MoM trend</p>
            </>
          ) : (
            <>
              <p className="text-xs font-bold text-gray-500">—</p>
              <p className="text-[9px] text-gray-600">MoM trend</p>
            </>
          )}
        </div>
      </div>

      {/* Spark bar chart */}
      {hasCost && (
        <MiniSparkBar months={hist} accent={meta.accent} mtd={data.current_mtd} forecast={data.forecast} />
      )}

      {/* Legend */}
      {hasCost && (
        <div className="flex gap-3 mt-1">
          <span className="text-[8px] text-gray-600 flex items-center gap-1">
            <span className="inline-block w-2 h-1.5 rounded-sm bg-teal-500/40" /> Historical
          </span>
          {data.current_mtd && (
            <span className="text-[8px] text-gray-600 flex items-center gap-1">
              <span className="inline-block w-2 h-1.5 rounded-sm bg-blue-500/60" /> MTD
            </span>
          )}
          {data.forecast && (
            <span className="text-[8px] text-gray-600 flex items-center gap-1">
              <span className="inline-block w-2 h-1.5 rounded-sm border border-orange-400/40 bg-orange-500/30" /> Forecast
            </span>
          )}
        </div>
      )}

      {/* Historical cost table */}
      {hist.length > 0 && (
        <div className="mt-3 rounded-lg overflow-hidden border border-white/5">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="bg-white/5">
                <th className="px-2 py-1 text-left text-gray-400 font-semibold">Month</th>
                <th className="px-2 py-1 text-right text-gray-400 font-semibold">Cost</th>
                <th className="px-2 py-1 text-right text-gray-400 font-semibold">vs Prev</th>
              </tr>
            </thead>
            <tbody>
              {hist.map((m, i) => {
                const prev = hist[i - 1]?.amount;
                const diff = prev != null && prev > 0 ? ((m.amount - prev) / prev) * 100 : null;
                return (
                  <tr key={m.month} className="border-t border-white/5 hover:bg-white/3">
                    <td className="px-2 py-1 text-gray-300">{m.month}</td>
                    <td className="px-2 py-1 text-right text-white font-medium tabular-nums">{fmtFull(m.amount)}</td>
                    <td className={`px-2 py-1 text-right tabular-nums ${diff == null ? "text-gray-600" : diff > 10 ? "text-red-400" : diff < -5 ? "text-green-400" : "text-gray-400"}`}>
                      {diff == null ? "—" : `${diff > 0 ? "+" : ""}${diff.toFixed(1)}%`}
                    </td>
                  </tr>
                );
              })}
              {data.current_mtd && (
                <tr className="border-t border-blue-500/20 bg-blue-500/5">
                  <td className="px-2 py-1 text-blue-300">{data.current_month} (MTD)</td>
                  <td className="px-2 py-1 text-right text-blue-200 font-medium tabular-nums">{fmtFull(data.current_mtd.amount)}</td>
                  <td className="px-2 py-1 text-right text-gray-600">—</td>
                </tr>
              )}
              {data.forecast && (
                <tr className="border-t border-orange-500/20 bg-orange-500/5">
                  <td className="px-2 py-1 text-orange-300 italic">{data.current_month} (forecast)</td>
                  <td className="px-2 py-1 text-right text-orange-200 font-bold tabular-nums">{fmtFull(data.forecast.amount)}</td>
                  <td className="px-2 py-1 text-right text-gray-600">—</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Budgets (GCP) */}
      {data.budgets && data.budgets.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-1.5">Configured Budgets</p>
          <div className="space-y-1">
            {data.budgets.map((b) => (
              <div key={b.name} className="flex justify-between text-[10px]">
                <span className="text-gray-400 truncate">{b.name}</span>
                <span className="text-yellow-300 font-medium tabular-nums ml-2">
                  {b.budget != null ? fmtFull(b.budget) : "Unlimited"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GCP note when no detailed data */}
      {data.note && (
        <p className="mt-3 text-[10px] text-yellow-500/80 italic border border-yellow-500/20 rounded-lg p-2 bg-yellow-500/5">
          {data.note}
        </p>
      )}

      {/* Top services */}
      {data.top_services && data.top_services.length > 0 && (
        <ServiceBreakdown services={data.top_services} accent={meta.accent} />
      )}
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
      {report.platform_stats && Object.keys(report.platform_stats).filter(k => k !== "_billing").length > 0 && (
        <div>
          <h3 className="text-sm text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Platform Overview
          </h3>
          <div className="space-y-3">
            {Object.entries(report.platform_stats)
              .filter(([pname]) => pname !== "_billing")
              .map(([pname, meta]) => (
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

      {/* Multi-cloud Billing Dashboard */}
      {report.platform_stats?._billing && (() => {
        const billing = report.platform_stats._billing as unknown as BillingByProvider;
        const providers = Object.entries(billing).filter(([, d]) => d && typeof d === "object");
        if (!providers.length) return null;

        // Aggregate total MTD across all providers
        const totalMtd = providers.reduce((sum, [, d]) => sum + ((d as ProviderBilling).current_mtd?.amount ?? 0), 0);
        const totalForecast = providers.reduce((sum, [, d]) => sum + ((d as ProviderBilling).forecast?.amount ?? 0), 0);
        const total6mo = providers.reduce((sum, [, d]) => sum + ((d as ProviderBilling).historical_months ?? []).reduce((s, m) => s + m.amount, 0), 0);

        return (
          <div>
            <h3 className="text-sm text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <DollarSign className="w-4 h-4" /> Cloud Billing Dashboard
              <span className="text-[10px] font-normal normal-case text-teal-500 ml-1">· Live data from Cost APIs</span>
            </h3>

            {/* Aggregate KPI strip */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="rounded-xl border border-white/10 bg-white/3 p-3 text-center">
                <p className="text-lg font-bold text-white tabular-nums">{fmtFull(totalMtd)}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">Total Cloud Spend (MTD)</p>
              </div>
              <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-3 text-center">
                <p className="text-lg font-bold text-orange-300 tabular-nums">{totalForecast > 0 ? fmtFull(totalForecast) : "—"}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">Projected This Month</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/3 p-3 text-center">
                <p className="text-lg font-bold text-teal-300 tabular-nums">{fmtFull(total6mo)}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">Last 6 Months Total</p>
              </div>
            </div>

            {/* Per-provider cards */}
            <div className="grid gap-4 md:grid-cols-2">
              {providers.map(([provider, data]) => (
                <ProviderBillingCard key={provider} provider={provider} data={data as ProviderBilling} />
              ))}
            </div>
          </div>
        );
      })()}

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
