"use client";
import { useEffect, useRef, useState } from "react";
import { CheckCircle, XCircle, Loader2, Terminal } from "lucide-react";
import { StatusEvent } from "@/lib/api";

interface Props {
  events: StatusEvent[];
  isRunning: boolean;
}

const SKILL_LABELS: Record<string, string> = {
  CloudAuditor:      "☁️  Cloud Auditor",
  LogAnalyst:        "📋 Log Analyst",
  SecurityAuditor:   "🔒 Security Auditor",
  CICDGuard:         "🔄 CI/CD Guard",
  CodeReviewer:      "💻 Code Reviewer",
  ReportSynthesizer: "📊 Report Synthesizer",
  DONE:              "✅ Audit Complete",
};

export default function StatusLog({ events, isRunning }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [dots, setDots] = useState(".");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  useEffect(() => {
    if (!isRunning) return;
    const t = setInterval(() => setDots((d) => (d.length >= 3 ? "." : d + ".")), 500);
    return () => clearInterval(t);
  }, [isRunning]);

  if (events.length === 0 && !isRunning) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-gray-600">
        <Terminal className="w-8 h-8 mb-2 opacity-50" />
        <p className="text-sm">Audit log will appear here</p>
      </div>
    );
  }

  return (
    <div className="font-mono text-sm space-y-1 max-h-72 overflow-y-auto pr-2">
      {events.map((evt, i) => (
        <LogLine key={i} event={evt} />
      ))}
      {isRunning && (
        <div className="flex items-center gap-2 text-teal-400 animate-pulse">
          <Loader2 className="w-3 h-3 animate-spin" />
          <span>Processing{dots}</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}

function LogLine({ event }: { event: StatusEvent }) {
  const label = SKILL_LABELS[event.skill] ?? event.skill;

  if (event.skill === "DONE") {
    return (
      <div className="flex items-center gap-2 text-teal-400 font-semibold py-1 border-t border-teal-500/20 mt-2">
        <CheckCircle className="w-4 h-4" />
        <span>{label}</span>
      </div>
    );
  }

  const isDone  = event.status === "done";
  const isError = event.status === "error";
  const isRun   = event.status === "running";

  return (
    <div className={`flex items-center gap-2 py-0.5 ${isDone ? "text-gray-300" : isError ? "text-red-400" : "text-teal-300"}`}>
      {isDone  && <CheckCircle className="w-3.5 h-3.5 text-teal-400 flex-shrink-0" />}
      {isError && <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />}
      {isRun   && <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />}
      <span className="flex-1">{label}</span>
      {isDone && (
        <span className="text-xs text-gray-500">
          {event.findings_count} finding{event.findings_count !== 1 ? "s" : ""}
        </span>
      )}
      {isError && <span className="text-xs text-red-500">error</span>}
    </div>
  );
}
