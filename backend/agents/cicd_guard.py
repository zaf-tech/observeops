"""
Skill 4 — CI/CD Guard
Audits pipeline health across GitHub Actions, Jenkins, Azure DevOps,
CircleCI, ArgoCD, Tekton. Platform-agnostic — plugin list driven by skills/cicd_guard.yaml.
"""
import logging
import pathlib
import yaml
from typing import Callable

logger = logging.getLogger(__name__)

_SKILL_FILE = pathlib.Path(__file__).parent.parent / "skills" / "cicd_guard.yaml"
with open(_SKILL_FILE) as _f:
    SKILL_DEF = yaml.safe_load(_f)

CICD_PLUGIN_NAMES = set(SKILL_DEF.get("plugins", {}).keys())
_CICD_KEYWORDS  = SKILL_DEF.get("cicd_keywords", ["action", "pipeline", "ci", "workflow"])


class CICDGuard:
    def __init__(self, progress_cb: Callable[[str], None] | None = None):
        self._progress = progress_cb or (lambda msg: logger.info(msg))

    def run(self, injected_credentials: dict | None = None) -> list[dict]:
        if injected_credentials:
            import os
            for k, v in injected_credentials.items():
                if v:
                    os.environ[k] = v

        from plugins import discover_plugins
        cicd_plugins = [p for p in discover_plugins() if p.name in CICD_PLUGIN_NAMES]

        if not cicd_plugins:
            self._progress("CICDGuard: no CI/CD credentials detected — skipping")
            return []

        findings: list[dict] = []
        for plugin in cicd_plugins:
            self._progress(f"CICDGuard: scanning {plugin.name}…")
            try:
                plugin_findings = plugin.run_scan()
                # For GitHub/GitLab include only CI/CD related findings
                if plugin.name in ("github", "gitlab"):
                    plugin_findings = [
                        f for f in plugin_findings
                        if any(kw in f.get("finding", "").lower() for kw in _CICD_KEYWORDS)
                    ]
                findings.extend(plugin_findings)
                self._progress(f"CICDGuard: {plugin.name} → {len(plugin_findings)} finding(s)")
            except Exception as exc:
                logger.error("CICDGuard: plugin %s raised unexpectedly: %s", plugin.name, exc)

        self._progress(f"CICDGuard: complete — {len(findings)} finding(s) total")
        return findings
