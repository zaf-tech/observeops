"""
Skill 1 — Cloud Auditor
Loads all cloud + Kubernetes plugins dynamically and runs their scans.
Contains ZERO platform-specific code. Plugin list driven by skills/cloud_auditor.yaml.
"""
import logging
import pathlib
import yaml
from typing import Callable

logger = logging.getLogger(__name__)

_SKILL_FILE = pathlib.Path(__file__).parent.parent / "skills" / "cloud_auditor.yaml"
with open(_SKILL_FILE) as _f:
    SKILL_DEF = yaml.safe_load(_f)

CLOUD_PLUGIN_NAMES = set(SKILL_DEF.get("plugins", {}).keys())


class CloudAuditor:
    """Platform-agnostic agent that delegates to whichever cloud plugins are available."""

    def __init__(self, progress_cb: Callable[[str], None] | None = None):
        self._progress = progress_cb or (lambda msg: logger.info(msg))

    def run(self, injected_credentials: dict | None = None) -> list[dict]:
        """
        Execute all available cloud/k8s plugins.

        injected_credentials: optional dict of env-key → value pairs passed in from
        the frontend (stored in-memory only, never persisted).
        """
        if injected_credentials:
            import os
            for k, v in injected_credentials.items():
                if v:
                    os.environ[k] = v

        from plugins import discover_plugins
        cloud_plugins = [p for p in discover_plugins() if p.name in CLOUD_PLUGIN_NAMES]

        if not cloud_plugins:
            self._progress("CloudAuditor: no cloud credentials detected — skipping")
            return []

        all_findings: list[dict] = []
        for plugin in cloud_plugins:
            self._progress(f"CloudAuditor: scanning {plugin.name}…")
            try:
                findings = plugin.run_scan()
                all_findings.extend(findings)
                self._progress(f"CloudAuditor: {plugin.name} → {len(findings)} finding(s)")
            except Exception as exc:
                logger.error("CloudAuditor: plugin %s raised unexpectedly: %s", plugin.name, exc)

        return all_findings
