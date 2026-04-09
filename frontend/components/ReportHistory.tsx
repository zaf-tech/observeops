"use client";
import { useEffect, useState, useCallback } from "react";
import { Clock, CheckCircle, XCircle, Loader2, Trash2, FileText, RefreshCw, ChevronRight } from "lucide-react";
import { listReports, deleteReport, type JobSummary } from "@/lib/api";

interface Props {
  onLoad: (jobId: string) => void;
  activeJobId: string | null;
}

export default function ReportHistory({ onLoad, activeJobId }: Props) {
  const [jobs, setJobs]       = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const data = await listReports();
    setJobs(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    // Poll every 5s so running jobs update their status
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
      <div className="flex flex-col items-center justify-center h-24 text-gray-600 gap-2">
        <FileText className="w-6 h-6 opacity-40" />
        <p className="text-sm">No reports yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500">{jobs.length} report{jobs.length !== 1 ? "s" : ""}</span>
        <button
          onClick={refresh}
          className="text-gray-600 hover:text-teal-400 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {jobs.map((job) => (
        <JobRow
          key={job.job_id}
          job={job}
          isActive={job.job_id === activeJobId}
          isDeleting={deleting === job.job_id}
          onLoad={() => onLoad(job.job_id)}
          onDelete={(e) => handleDelete(job.job_id, e)}
        />
      ))}
    </div>
  );
}

function JobRow({
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

  return (
    <div
      onClick={isCompleted ? onLoad : undefined}
      className={`group relative flex items-start gap-3 p-3 rounded-xl border transition-all duration-200
        ${isActive        ? "border-teal-500/50 bg-teal-500/10" :
          isCompleted     ? "border-white/10 bg-white/3 hover:border-teal-500/30 hover:bg-white/5 cursor-pointer" :
          isError         ? "border-red-500/20 bg-red-500/5" :
                            "border-white/10 bg-white/3"}`}
    >
      {/* Status icon */}
      <div className="mt-0.5 flex-shrink-0">
        {isCompleted && <CheckCircle className="w-4 h-4 text-teal-400" />}
        {isRunning   && <Loader2    className="w-4 h-4 text-blue-400 animate-spin" />}
        {isError     && <XCircle    className="w-4 h-4 text-red-400" />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Status + time */}
        <div className="flex items-center gap-2 mb-1">
          <StatusBadge status={job.status} />
          <span className="text-xs text-gray-600 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatDate(job.started_at)}
          </span>
        </div>

        {/* Platforms */}
        {job.platforms.length > 0 && (
          <p className="text-xs text-gray-500 truncate capitalize mb-1">
            {job.platforms.slice(0, 5).join(" · ")}
            {job.platforms.length > 5 && ` +${job.platforms.length - 5}`}
          </p>
        )}

        {/* Severity counts */}
        {isCompleted && job.total > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            {job.critical > 0 && <SevBadge label="C" count={job.critical} color="text-red-400 bg-red-500/10" />}
            {job.high     > 0 && <SevBadge label="H" count={job.high}     color="text-orange-400 bg-orange-500/10" />}
            {job.medium   > 0 && <SevBadge label="M" count={job.medium}   color="text-yellow-400 bg-yellow-500/10" />}
            {job.low      > 0 && <SevBadge label="L" count={job.low}      color="text-green-400 bg-green-500/10" />}
            <span className="text-xs text-gray-600">{job.total} total</span>
          </div>
        )}

        {/* LLM info */}
        <p className="text-xs text-gray-700 mt-1">
          {job.scan_llm} → {job.report_llm}
        </p>

        {/* Error message */}
        {isError && job.error && (
          <p className="text-xs text-red-500/70 mt-1 truncate" title={job.error}>{job.error}</p>
        )}

        {/* Duration */}
        {job.completed_at && (
          <p className="text-xs text-gray-700 mt-0.5">
            Took {duration(job.started_at, job.completed_at)}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        {isCompleted && !isActive && (
          <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-teal-400 transition-colors" />
        )}
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="opacity-0 group-hover:opacity-100 p-1 text-gray-600 hover:text-red-400 transition-all"
          title="Delete report"
        >
          {isDeleting
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Trash2  className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "bg-teal-500/15 text-teal-400 border-teal-500/20",
    running:   "bg-blue-500/15 text-blue-400 border-blue-500/20",
    error:     "bg-red-500/15 text-red-400 border-red-500/20",
  };
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${map[status] ?? map.error}`}>
      {status}
    </span>
  );
}

function SevBadge({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono font-bold ${color}`}>
      {label}:{count}
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function duration(start: string, end: string): string {
  try {
    const ms = new Date(end).getTime() - new Date(start).getTime();
    const s = Math.round(ms / 1000);
    if (s < 60)  return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
    return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  } catch {
    return "";
  }
}
