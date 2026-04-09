"""
Skill 2 — Log Analyst
Parses system/application logs (local files or CloudWatch) and summarises
anomalies using an LLM. Platform-agnostic — uses available cloud SDKs.
"""
import logging
import os
import pathlib
from typing import Callable

logger = logging.getLogger(__name__)

LOG_PATTERNS = [
    "error", "exception", "fatal", "critical", "traceback",
    "out of memory", "oom", "connection refused", "timeout",
    "disk full", "permission denied", "segfault",
]


class LogAnalyst:
    def __init__(self, progress_cb: Callable[[str], None] | None = None, scan_llm: str | None = None):
        self._progress = progress_cb or (lambda msg: logger.info(msg))
        self._scan_llm = scan_llm

    def run(self, log_paths: list[str] | None = None) -> list[dict]:
        findings: list[dict] = []
        self._progress("LogAnalyst: scanning log sources…")

        # Local file logs
        paths = log_paths or self._default_log_paths()
        for path_str in paths:
            path = pathlib.Path(path_str)
            if path.exists() and path.is_file():
                findings += self._scan_log_file(path)

        # CloudWatch logs (if AWS credentials available)
        findings += self._scan_cloudwatch()

        self._progress(f"LogAnalyst: {len(findings)} anomaly/anomalies found")
        return findings

    # ------------------------------------------------------------------
    def _default_log_paths(self) -> list[str]:
        candidates = [
            "/var/log/syslog", "/var/log/messages", "/var/log/auth.log",
            "/var/log/nginx/error.log", "/var/log/apache2/error.log",
        ]
        return [p for p in candidates if pathlib.Path(p).exists()]

    def _scan_log_file(self, path: pathlib.Path) -> list[dict]:
        findings = []
        try:
            lines = path.read_text(errors="ignore").splitlines()
            anomalies = [
                line for line in lines
                if any(pat in line.lower() for pat in LOG_PATTERNS)
            ]
            if not anomalies:
                return []
            # Use LLM to summarise
            summary = self._summarise_anomalies(anomalies[:100], str(path))
            findings.append({
                "platform": "logs",
                "resource": str(path),
                "severity": "HIGH" if any("error" in a.lower() or "fatal" in a.lower() for a in anomalies) else "MEDIUM",
                "category": "reliability",
                "finding": f"Log file '{path.name}' contains {len(anomalies)} anomalous lines",
                "recommendation": summary,
                "evidence": {"sample_lines": anomalies[:5]},
            })
        except Exception as exc:
            logger.warning("LogAnalyst file scan error %s: %s", path, exc)
        return findings

    def _scan_cloudwatch(self) -> list[dict]:
        if not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
            return []
        findings = []
        try:
            import boto3
            from datetime import datetime, timezone, timedelta
            logs = boto3.client("logs", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
            groups = logs.describe_log_groups(limit=10).get("logGroups", [])
            cutoff = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp() * 1000)
            for group in groups:
                gname = group["logGroupName"]
                try:
                    resp = logs.filter_log_events(
                        logGroupName=gname,
                        startTime=cutoff,
                        filterPattern="?ERROR ?FATAL ?Exception",
                        limit=50,
                    )
                    events = resp.get("events", [])
                    if events:
                        findings.append({
                            "platform": "cloudwatch",
                            "resource": f"cloudwatch/log-group/{gname}",
                            "severity": "HIGH",
                            "category": "reliability",
                            "finding": f"CloudWatch log group '{gname}' has {len(events)} error event(s) in the last 24 hours",
                            "recommendation": "Investigate error events in CloudWatch Logs Insights",
                            "evidence": {"sample": [e.get("message", "")[:200] for e in events[:3]]},
                        })
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("CloudWatch log scan error: %s", exc)
        return findings

    def _summarise_anomalies(self, lines: list[str], source: str) -> str:
        try:
            from config import get_scan_llm
            llm = get_scan_llm(self._scan_llm)
            prompt = (
                f"You are an SRE. Summarise these log anomalies from '{source}' in one paragraph "
                f"and suggest the most likely root cause and fix:\n\n" + "\n".join(lines[:20])
            )
            result = llm.invoke(prompt)
            return str(result) if result else "Review log file for errors and exceptions."
        except Exception:
            return "Review log file for errors and exceptions."
