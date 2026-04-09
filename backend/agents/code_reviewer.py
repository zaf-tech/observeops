"""
Skill 5 — Code Reviewer
Scans repos for quality, CVEs, and dependency drift using SonarQube,
Snyk, GitHub, GitLab, Artifactory, Nexus plugins.
Platform-agnostic — no platform-specific code here.
"""
import logging
from typing import Callable

logger = logging.getLogger(__name__)

CODE_PLUGIN_NAMES = {
    "github", "gitlab", "bitbucket",
    "sonarqube", "snyk",
    "artifactory", "nexus",
}


class CodeReviewer:
    def __init__(self, progress_cb: Callable[[str], None] | None = None):
        self._progress = progress_cb or (lambda msg: logger.info(msg))

    def run(self, injected_credentials: dict | None = None) -> list[dict]:
        if injected_credentials:
            import os
            for k, v in injected_credentials.items():
                if v:
                    os.environ[k] = v

        from plugins import discover_plugins
        code_plugins = [p for p in discover_plugins() if p.name in CODE_PLUGIN_NAMES]

        if not code_plugins:
            self._progress("CodeReviewer: no code/quality credentials detected — skipping")
            return []

        findings: list[dict] = []
        for plugin in code_plugins:
            self._progress(f"CodeReviewer: scanning {plugin.name}…")
            try:
                plugin_findings = plugin.run_scan()
                findings.extend(plugin_findings)
                self._progress(f"CodeReviewer: {plugin.name} → {len(plugin_findings)} finding(s)")
            except Exception as exc:
                logger.error("CodeReviewer: plugin %s raised unexpectedly: %s", plugin.name, exc)

        self._progress(f"CodeReviewer: complete — {len(findings)} finding(s) total")
        return findings
