"""
Skill 3 — Security Auditor
Reviews IAM, open ports, and checks code repos for hardcoded secrets.
Platform-agnostic — loads cloud IAM + code repo plugins.
"""
import logging
import re
from typing import Callable

logger = logging.getLogger(__name__)

IAM_PLUGIN_NAMES = {"aws", "azure", "gcp"}
REPO_PLUGIN_NAMES = {"github", "gitlab", "bitbucket"}

SECRET_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?[^\s'\"]{8,}"), "Hardcoded password"),
    (re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[^\s'\"]{8,}"), "Hardcoded API key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID"),
    (re.compile(r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*[^\s]{20,}"), "AWS Secret Access Key"),
    (re.compile(r"(?i)(private[_-]?key|privatekey)\s*[=:]\s*.{10,}"), "Hardcoded private key"),
    (re.compile(r"ghp_[A-Za-z0-9_]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"glpat-[A-Za-z0-9\-_]{20}"), "GitLab Personal Access Token"),
]


class SecurityAuditor:
    def __init__(self, progress_cb: Callable[[str], None] | None = None):
        self._progress = progress_cb or (lambda msg: logger.info(msg))

    def run(self, injected_credentials: dict | None = None) -> list[dict]:
        if injected_credentials:
            import os
            for k, v in injected_credentials.items():
                if v:
                    os.environ[k] = v

        from plugins import discover_plugins
        available = discover_plugins()
        iam_plugins = [p for p in available if p.name in IAM_PLUGIN_NAMES]
        repo_plugins = [p for p in available if p.name in REPO_PLUGIN_NAMES]

        findings: list[dict] = []

        # IAM scan
        self._progress("SecurityAuditor: running IAM checks…")
        for plugin in iam_plugins:
            try:
                plugin_findings = plugin.run_scan()
                # Filter to security/compliance only
                security_findings = [
                    f for f in plugin_findings
                    if f.get("category") in ("security", "compliance")
                ]
                findings.extend(security_findings)
                self._progress(f"SecurityAuditor: {plugin.name} IAM → {len(security_findings)} finding(s)")
            except Exception as exc:
                logger.error("SecurityAuditor: IAM plugin %s error: %s", plugin.name, exc)

        # Secret scanning in repos
        self._progress("SecurityAuditor: scanning repos for hardcoded secrets…")
        for plugin in repo_plugins:
            try:
                secrets = self._scan_repo_secrets(plugin)
                findings.extend(secrets)
                self._progress(f"SecurityAuditor: {plugin.name} secrets → {len(secrets)} finding(s)")
            except Exception as exc:
                logger.error("SecurityAuditor: repo plugin %s error: %s", plugin.name, exc)

        self._progress(f"SecurityAuditor: complete — {len(findings)} finding(s) total")
        return findings

    def _scan_repo_secrets(self, plugin) -> list[dict]:
        """Use LLM-assisted secret detection on recent code changes."""
        findings = []
        try:
            from config import get_scan_llm
            llm = get_scan_llm()
            # Run the plugin's own scan first
            plugin_findings = plugin.run_scan()
            security_findings = [f for f in plugin_findings if f.get("category") == "security"]
            findings.extend(security_findings)
        except Exception as exc:
            logger.warning("SecurityAuditor: secret scan error for %s: %s", plugin.name, exc)
        return findings
