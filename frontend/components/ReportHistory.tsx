"use client";
import { useEffect, useState, useCallback } from "react";
import {
  Clock, CheckCircle, XCircle, Loader2, Trash2, FileText,
  RefreshCw, ChevronRight, Calendar, Cpu, AlertCircle,
} from "lucide-react";
import { listReports, deleteReport, type JobSummary } from "@/lib/api";

interface Props {
  onLoad: (jobId: string) => void;
  activeJobId: string | null;
}

const PLATFORM_ICONS: Record<string, string> = {
  github: "🐙", gitlab: "🦊", aws: "☁️", azure: "🔷",
  gcp: "🌐", jenkins: "🏗️", sonarqube: "📊", snyk: "🛡️",
  argocd: "🚀", circleci: "⭕",
};

/** Group jobs by relative date bucket */
function groupByDate(jobs: JobSummary[]): { label: string; jobs: JobSummary[] }[] {
  const now    = new Date();
  const today  = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yest   = new Date(today); yest.setDate(yest.getDate() - 1);
  const week   = new Date(today); week.setDate(week.getDate() - 7);
  const month  = new Date(today); month.setDate(month.getDate() - 30);

  const buckets: Record<string, JobSummary[]> = {
    Today: [], Yesterday: [], "This Week": [], "This Month": [], Older: [],
  };

  for (const job of jobs) {
    const d = new Date(job.started_at);
    if      (d >= today) buckets["Today"].push(job);
    else if (d >= yest)  buckets["Yesterday"].push(job);
    else if (d >= week)  buckets["This Week"].push(job);
    else if (d >= month) buckets["This Month"].push(job);
    else                 buckets["Older"].push(job);
  }

  return Object.entries(buckets)
    .filter(([, jobs]) => jobs.length > 0)
    .map(([label, jobs]) => ({ label, jobs }));
}

export default function ReportHistory({ onLoad, activeJobId }: Props) {
  const [jobs, setJobs]         = useState<JobSummary[]>([]);
  const [loading, setLoading]   = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [search, setSearch]     = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    const data = await listReports();
    setJobs(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const handleDelete = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleting(jobId);
    await deleteReport(jobId);
    setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
    setDeleting(null);
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-gray-600 gap-2">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">Loading history…</span>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-600 gap-3">
        <FileText className="w-10 h-10 opacity-20" />
        <p className="text-sm">No reports generated yet</p>
        <p className="text-xs text-gray-700">Run an audit to see results here</p>
      </div>
    );
  }

  // Filter by search query (name, platforms, job_id)
  const filtered = search
    ? jobs.filter((j) =>
        (j.report_name ?? "").toLowerCase().includes(search.toLowerCase()) ||
        j.platforms.some((p) => p.toLowerCase().includes(search.toLowerCase())) ||
        j.job_id.startsWith(search)
      )
    : jobs;

  const grouped = groupByDate(filtered);
  const completedCount = jobs.filter((j) => j.status === "completed").length;
  const runningCount   = jobs.filter((j) => j.status === "running").length;

  return (
    <div className="space-y-4">
      {/* Header stats + refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <FileText className="w-3.5 h-3.5" />
            {completedCount} completed
          </span>
          {runningCount > 0 && (
            <span className="flex items-center gap-1 text-blue-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {runningCount} running
            </span>
          )}
        </div>
        <button
          onClick={refresh}
          className="text-gray-600 hover:text-teal-400 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Search */}
      {jobs.length > 3 && (
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, platform, or ID…"
          className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-300 placeholder-gray-600 focus:outline-none focus:border-teal-500/40 transition-colors"
        />
      )}

      {/* Grouped list */}
      {grouped.length === 0 ? (
        <p className="text-center text-sm text-gray-600 py-4">No results match "{search}"</p>
      ) : (
        grouped.map(({ label, jobs: groupJobs }) => (
          <div key={label}>
            {/* Date group header */}
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-3.5 h-3.5 text-gray-600" />
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{label}</span>
              <div className="flex-1 h-px bg-white/5" />
              <span className="text-xs text-gray-700">{groupJobs.length}</span>
            </div>

            <div className="space-y-2">
              {groupJobs.map((job) => (
                <JobCard
                  key={job.job_id}
                  job={job}
                  isActive={job.job_id === activeJobId}
                  isDeleting={deleting === job.job_id}
                  onLoad={() => { onLoad(job.job_id); }}
                  onDelete={(e) => handleDelete(job.job_id, e)}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function JobCard({
  job, isActive, isDeleting, onLoad, onDelete,
}: {
  job: JobSummary;
  isActive: boolean;
  isDeleting: boolean;
  onLoad: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  const isCompleted = job.status === "completed";
  const isRunning   = job.status === "running";
  const isError     = job.status === "error";
  const hasName     = !!(job as JobSummary & { report_name?: string }).report_name;
  const reportName  = (job as JobSummary & { report_name?: string }).report_name ?? "";

  const totalFindings = job.total ?? 0;
  const maxSev = job.critical > 0 ? "critical" : job.high > 0 ? "high" : job.medium > 0 ? "medium" : job.low > 0 ? "low" : "none";

  const borderColor = isActive ? "border-teal-500/50" :
    isError    ? "border-red-500/20" :
    maxSev === "critical" ? "border-red-500/25" :
    maxSev === "high"     ? "border-orange-500/20" :
    "border-white/8";

  return (
    <div
      onClick={isCompleted ? onLoad : undefined}
      className={`group relative rounded-xl border transition-all duration-200 overflow-hidden
        ${isActive    ? "bg-teal-500/8" : isError ? "bg-red-500/5" : "bg-white/3"}
        ${borderColor}
        ${isCompleted ? "hover:border-teal-500/40 hover:bg-white/5 cursor-pointer" : ""}`}
    >
      {/* Left accent bar */}
      <div className={`absolute left-0 top-0 bottom-0 w-0.5 rounded-l
        ${isActive ? "bg-teal-500" :
          isRunning ? "bg-blue-500 animate-pulse" :
          isError   ? "bg-red-500" :
          maxSev === "critical" ? "bg-red-500" :
          maxSev === "high"     ? "bg-orange-500" :
          maxSev === "medium"   ? "bg-yellow-500" :
          "bg-teal-500/30"}`}
      />

      <div className="pl-4 pr-3 py-3">
        {/* Row 1: Name + status icon */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {isCompleted && <CheckCircle className="w-3.5 h-3.5 text-teal-400 flex-shrink-0" />}
            {isRunning   && <Loader2    className="w-3.5 h-3.5 text-blue-400 animate-spin flex-shrink-0" />}
            {isError     && <XCircle    className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />}
            <div className="min-w-0">
              <p className={`text-sm font-semibold truncate ${hasName ? "text-white" : "text-gray-400"}`}>
                {hasName ? reportName : `Audit ${job.job_id.slice(0, 8)}`}
              </p>
              <p className="text-xs text-gray-600 flex items-center gap-1 mt-0.5">
                <Clock className="w-2.5 h-2.5" />
                {formatDate(job.started_at)}
                {job.completed_at && (
                  <span className="text-gray-700">· {duration(job.started_at, job.completed_at)}</span>
                )}
              </p>
            </div>
          </div>

          {/* Delete button */}
          <button
            onClick={onDelete}
            disabled={isDeleting}
            className="opacity-0 group-hover:opacity-100 p-1 text-gray-600 hover:text-red-400 transition-all flex-shrink-0"
            title="Delete report"
          >
            {isDeleting
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <Trash2  className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Row 2: Platform icons */}
        {job.platforms.length > 0 && (
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {job.platforms.slice(0, 6).map((p) => (
              <span key={p} className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white/5 border border-white/8 text-xs text-gray-400" title={p}>
                <span>{PLATFORM_ICONS[p] ?? "📦"}</span>
                <span className="capitalize">{p}</span>
              </span>
            ))}
            {job.platforms.length > 6 && (
              <span className="text-xs text-gray-600">+{job.platforms.length - 6}</span>
            )}
          </div>
        )}

        {/* Row 3: Severity mini-bar + totals */}
        {isCompleted && totalFindings > 0 && (
          <div className="mt-2.5 space-y-1">
            {/* Mini severity bar */}
            <div className="flex h-1.5 rounded-full overflow-hidden gap-0.5">
              {job.critical > 0 && <div className="bg-red-500 rounded-full" style={{ flex: job.critical }} />}
              {job.high     > 0 && <div className="bg-orange-500 rounded-full" style={{ flex: job.high }} />}
              {job.medium   > 0 && <div className="bg-yellow-500 rounded-full" style={{ flex: job.medium }} />}
              {job.low      > 0 && <div className="bg-green-500 rounded-full" style={{ flex: job.low }} />}
              {job.info     > 0 && <div className="bg-blue-500 rounded-full" style={{ flex: job.info }} />}
            </div>
            {/* Counts */}
            <div className="flex items-center gap-2 flex-wrap">
              {job.critical > 0 && <SevBadge label="Critical" count={job.critical} cls="text-red-400 bg-red-500/10 border-red-500/15" />}
              {job.high     > 0 && <SevBadge label="High"     count={job.high}     cls="text-orange-400 bg-orange-500/10 border-orange-500/15" />}
              {job.medium   > 0 && <SevBadge label="Med"      count={job.medium}   cls="text-yellow-400 bg-yellow-500/10 border-yellow-500/15" />}
              {job.low      > 0 && <SevBadge label="Low"      count={job.low}      cls="text-green-400 bg-green-500/10 border-green-500/15" />}
              <span className="text-xs text-gray-600 ml-auto">{totalFindings} total</span>
            </div>
          </div>
        )}

        {/* LLM + open arrow */}
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-700 flex items-center gap-1">
            <Cpu className="w-2.5 h-2.5" />
            {job.report_llm}
          </span>
          {isCompleted && (
            <ChevronRight className="w-3.5 h-3.5 text-gray-700 group-hover:text-teal-400 transition-colors" />
          )}
          {isError && job.error && (
            <span className="text-xs text-red-500/70 flex items-center gap-1 truncate max-w-[60%]" title={job.error}>
              <AlertCircle className="w-2.5 h-2.5 flex-shrink-0" />
              {job.error.slice(0, 50)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function SevBadge({ label, count, cls }: { label: string; count: number; cls: string }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${cls}`}>
      {label}: {count}
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function duration(start: string, end: string): string {
  try {
    const s = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000);
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
    return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  } catch { return ""; }
}
