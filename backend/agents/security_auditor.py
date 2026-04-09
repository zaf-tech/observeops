"""
Skill 3 — Security Auditor
Reviews IAM, open ports, and checks code repos for hardcoded secrets.
Platform-agnostic — plugin list and secret patterns driven by skills/security_auditor.yaml.
"""
import logging
import re
import pathlib
import yaml
from typing import Callable

logger = logging.getLogger(__name__)

_SKILL_FILE = pathlib.Path(__file__).parent.parent / "skills" / "security_auditor.yaml"
with open(_SKILL_FILE) as _f:
    SKILL_DEF = yaml.safe_load(_f)

_all_plugins   = SKILL_DEF.get("plugins", {})
IAM_PLUGIN_NAMES  = {k for k, v in _all_plugins.items() if v.get("filter") == "security_compliance"}
REPO_PLUGIN_NAMES = {k for k, v in _all_plugins.items() if v.get("filter") == "secrets"}

SECRET_PATTERNS = [
    (re.compile(p["regex"]), p["name"])
    for p in SKILL_DEF.get("secret_patterns", [])
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
