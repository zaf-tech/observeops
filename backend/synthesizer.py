"""
Top-level Synthesizer — orchestrates all 6 skills and produces the final report.
Called by the /api/analyze router via background task.
"""
import logging
import json
import pathlib
import asyncio
import os
from typing import Callable

logger = logging.getLogger(__name__)

REPORTS_DIR = pathlib.Path("reports")

# Every env key any plugin can read — wiped clean before each scan
# so previous scan credentials never bleed into the next scan.
_ALL_CREDENTIAL_KEYS = [
    # AWS
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION",
    "AWS_SESSION_TOKEN",
    # Azure
    "AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
    "AZURE_SUBSCRIPTION_ID",
    # GCP
    "GOOGLE_APPLICATION_CREDENTIALS", "GCP_PROJECT_ID",
    "GCP_SERVICE_ACCOUNT_JSON",
    # GitHub
    "GITHUB_TOKEN", "GITHUB_ORG",
    # GitLab
    "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_GROUP",
    # Bitbucket
    "BITBUCKET_USERNAME", "BITBUCKET_APP_PASSWORD", "BITBUCKET_WORKSPACE",
    # Jenkins
    "JENKINS_URL", "JENKINS_USER", "JENKINS_TOKEN",
    # Azure DevOps
    "AZURE_DEVOPS_TOKEN", "AZURE_DEVOPS_ORG",
    # CircleCI
    "CIRCLECI_TOKEN",
    # ArgoCD
    "ARGOCD_URL", "ARGOCD_TOKEN",
    # SonarQube
    "SONAR_TOKEN", "SONAR_URL", "SONAR_ORG",
    # Snyk
    "SNYK_TOKEN", "SNYK_ORG",
    # Artifactory
    "ARTIFACTORY_URL", "ARTIFACTORY_TOKEN",
    # Nexus
    "NEXUS_URL", "NEXUS_USER", "NEXUS_PASSWORD",
    # Tekton / k8s
    "KUBECONFIG",
]


def _apply_credentials(credentials: dict) -> dict:
    """
    Wipe ALL known credential env vars, then inject only the ones provided
    for this scan. Returns the saved originals for restore.
    """
    saved = {}
    # First clear everything so previous scan state is gone
    for key in _ALL_CREDENTIAL_KEYS:
        saved[key] = os.environ.get(key)
        os.environ.pop(key, None)
    # Now set only what this scan provides
    for k, v in credentials.items():
        if v:
            saved.setdefault(k, os.environ.get(k))
            os.environ[k] = str(v)
    return saved


def _restore_credentials(saved: dict) -> None:
    """Restore env to pre-scan state."""
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


async def run_audit(
    job_id: str,
    credentials: dict,
    scan_llm: str,
    report_llm: str,
    llm_config: dict,
    custom_instructions: str,
    report_name: str,
    progress_cb: Callable[[str, str, int], None],
) -> None:
    """
    Orchestrate all 6 skills asynchronously.
    Credentials are isolated per-scan — no bleed between consecutive scans.
    """
    REPORTS_DIR.mkdir(exist_ok=True)
    all_findings: list[dict] = []
    plugin_audit: list[dict] = []

    def _record_plugin(name: str, status: str, count: int):
        plugin_audit.append({"plugin": name, "status": status, "findings": count})

    def make_cb(skill_name: str):
        def cb(msg: str):
            logger.info("[%s] %s", skill_name, msg)
            progress_cb(skill_name, msg, len(all_findings))
        return cb

    # ── Isolate credentials for this scan ─────────────────────────────
    saved_env = _apply_credentials(credentials)
    logger.info("Job %s: injected %d credential(s): %s",
                job_id,
                len([v for v in credentials.values() if v]),
                [k for k, v in credentials.items() if v])

    try:
        # Record plugin availability after injecting credentials
        try:
            from plugins import all_plugins
            for plugin in all_plugins():
                if plugin.is_available():
                    _record_plugin(plugin.name, "available", 0)
                    logger.info("Job %s: plugin '%s' is AVAILABLE", job_id, plugin.name)
                else:
                    _record_plugin(plugin.name, "skipped", 0)
        except Exception as exc:
            logger.warning("Plugin availability check failed: %s", exc)

        # ── Skill 1 — Cloud Auditor ───────────────────────────────────
        progress_cb("CloudAuditor", "running", 0)
        try:
            from agents.cloud_auditor import CloudAuditor
            findings = await asyncio.to_thread(CloudAuditor(make_cb("CloudAuditor")).run, credentials)
            all_findings.extend(findings)
            progress_cb("CloudAuditor", "done", len(findings))
        except Exception as exc:
            logger.error("CloudAuditor failed: %s", exc)
            progress_cb("CloudAuditor", "error", 0)

        # ── Skill 2 — Log Analyst ─────────────────────────────────────
        progress_cb("LogAnalyst", "running", 0)
        try:
            from agents.log_analyst import LogAnalyst
            findings = await asyncio.to_thread(
                LogAnalyst(make_cb("LogAnalyst"), scan_llm=scan_llm).run)
            all_findings.extend(findings)
            progress_cb("LogAnalyst", "done", len(findings))
        except Exception as exc:
            logger.error("LogAnalyst failed: %s", exc)
            progress_cb("LogAnalyst", "error", 0)

        # ── Skill 3 — Security Auditor ────────────────────────────────
        progress_cb("SecurityAuditor", "running", 0)
        try:
            from agents.security_auditor import SecurityAuditor
            findings = await asyncio.to_thread(
                SecurityAuditor(make_cb("SecurityAuditor")).run, credentials)
            all_findings.extend(findings)
            progress_cb("SecurityAuditor", "done", len(findings))
        except Exception as exc:
            logger.error("SecurityAuditor failed: %s", exc)
            progress_cb("SecurityAuditor", "error", 0)

        # ── Skill 4 — CI/CD Guard ─────────────────────────────────────
        progress_cb("CICDGuard", "running", 0)
        try:
            from agents.cicd_guard import CICDGuard
            findings = await asyncio.to_thread(
                CICDGuard(make_cb("CICDGuard")).run, credentials)
            all_findings.extend(findings)
            progress_cb("CICDGuard", "done", len(findings))
        except Exception as exc:
            logger.error("CICDGuard failed: %s", exc)
            progress_cb("CICDGuard", "error", 0)

        # ── Skill 5 — Code Reviewer ───────────────────────────────────
        progress_cb("CodeReviewer", "running", 0)
        try:
            from agents.code_reviewer import CodeReviewer
            findings = await asyncio.to_thread(
                CodeReviewer(make_cb("CodeReviewer")).run, credentials)
            all_findings.extend(findings)
            progress_cb("CodeReviewer", "done", len(findings))
        except Exception as exc:
            logger.error("CodeReviewer failed: %s", exc)
            progress_cb("CodeReviewer", "error", 0)

        # ── Collect platform stats (while credentials still active) ───
        platform_stats: dict[str, dict] = {}
        try:
            from plugins import discover_plugins
            for plugin in discover_plugins():
                try:
                    meta = plugin.get_metadata()
                    if meta:
                        platform_stats[plugin.name] = meta
                        logger.info("Job %s: collected stats for plugin '%s'", job_id, plugin.name)
                except Exception as meta_exc:
                    logger.warning("Job %s: get_metadata failed for %s: %s", job_id, plugin.name, meta_exc)
        except Exception as exc:
            logger.warning("Job %s: platform stats collection failed: %s", job_id, exc)

        # ── Billing data (when user requests it and AWS is available) ──
        try:
            from billing_collector import should_collect_billing, collect_billing_data
            if custom_instructions and should_collect_billing(custom_instructions):
                logger.info("Job %s: billing keywords detected — fetching AWS Cost Explorer data", job_id)
                billing = collect_billing_data()
                if billing:
                    platform_stats["_billing"] = billing
                    logger.info("Job %s: billing data collected (%d historical months)",
                                job_id, len(billing.get("historical_months", [])))
                else:
                    logger.info("Job %s: billing collection returned no data", job_id)
        except Exception as exc:
            logger.warning("Job %s: billing collection failed: %s", job_id, exc)

        # ── Skill 6 — Report Synthesizer ──────────────────────────────
        progress_cb("ReportSynthesizer", "running", len(all_findings))
        try:
            from agents.report_synthesizer import ReportSynthesizer
            result = await asyncio.to_thread(
                ReportSynthesizer(
                    make_cb("ReportSynthesizer"),
                    report_llm=report_llm,
                    llm_config=llm_config.get("report", {}),
                    custom_instructions=custom_instructions,
                    platform_stats=platform_stats,
                ).run,
                all_findings,
            )
            _save_report(job_id, result, all_findings, plugin_audit, platform_stats,
                        result.get("token_usage", {}), report_name)
            from job_store import complete_job
            complete_job(job_id, result.get("summary", {}))
            progress_cb("ReportSynthesizer", "done", len(all_findings))
        except Exception as exc:
            logger.error("ReportSynthesizer failed: %s", exc)
            progress_cb("ReportSynthesizer", "error", 0)
            _save_report(job_id,
                         {"markdown": "Report generation failed.", "summary": {}},
                         all_findings, plugin_audit, platform_stats, {}, report_name)
            from job_store import fail_job
            fail_job(job_id, str(exc))

    finally:
        # Always restore env — even if a skill crashes
        _restore_credentials(saved_env)
        logger.info("Job %s: credentials restored", job_id)


def _save_report(job_id: str, result: dict,
                 findings: list[dict],
                 plugin_audit: list[dict] | None = None,
                 platform_stats: dict | None = None,
                 token_usage: dict | None = None,
                 report_name: str = "") -> None:
    report_path = REPORTS_DIR / f"{job_id}.json"
    payload = {
        "job_id":          job_id,
        "report_name":     report_name,
        "markdown":        result.get("markdown", ""),
        "summary":         result.get("summary", {}),
        "findings":        findings,
        "plugin_audit":    plugin_audit or [],
        "platform_stats":  platform_stats or {},
        "token_usage":     token_usage or {},
    }
    report_path.write_text(json.dumps(payload, indent=2, default=str))
    logger.info("Report saved: %s", report_path)


def load_report(job_id: str) -> dict | None:
    report_path = REPORTS_DIR / f"{job_id}.json"
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text())
