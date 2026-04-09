"use client";
import { Suspense } from "react";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2, ArrowLeft, AlertTriangle } from "lucide-react";
import Link from "next/link";
import ReportViewer from "@/components/ReportViewer";
import { fetchReport, type ReportResponse } from "@/lib/api";

function ReportContent() {
  const params = useSearchParams();
  const jobId = params.get("job_id");
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) { setError("No job ID provided."); setLoading(false); return; }
    fetchReport(jobId)
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  return (
    <>
      <div className="mb-8">
        <Link href="/" className="inline-flex items-center gap-2 text-teal-400 hover:text-teal-300 text-sm mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>
        <h1 className="text-3xl font-bold gradient-text">Audit Report</h1>
        {jobId && <p className="text-xs text-gray-600 font-mono mt-1">Job: {jobId}</p>}
      </div>

      {loading && (
        <div className="flex items-center justify-center h-48 gap-3 text-teal-400">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading report…</span>
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-300">Failed to load report</p>
            <p className="text-xs text-red-400 mt-1">{error}</p>
          </div>
        </div>
      )}

      {report && <ReportViewer report={report} />}
    </>
  );
}

export default function ReportPage() {
  return (
    <div className="min-h-screen bg-grid px-6 py-12 max-w-5xl mx-auto">
      <Suspense fallback={
        <div className="flex items-center justify-center h-48 gap-3 text-teal-400">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading…</span>
        </div>
      }>
        <ReportContent />
      </Suspense>
    </div>
  );
}
