"""ArgoCD plugin — REST API. READ-ONLY."""
import os
import logging

import requests

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class ArgoCDPlugin(BasePlugin):
    name = "argocd"
    credential_keys = ["ARGOCD_URL", "ARGOCD_TOKEN"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def _base(self) -> str:
        return os.getenv("ARGOCD_URL", "").rstrip("/")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {os.getenv('ARGOCD_TOKEN', '')}"}

    def get_metadata(self) -> dict:
        try:
            r = requests.get(f"{self._base()}/api/v1/version", headers=self._headers(), timeout=10, verify=False)
            data = r.json()
            return {"platform": self.name, "version": data.get("Version"), "url": self._base()}
        except Exception as exc:
            logger.warning("ArgoCD get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            r = requests.get(
                f"{self._base()}/api/v1/applications",
                headers=self._headers(), timeout=15, verify=False,
            )
            apps = r.json().get("items", [])
            for app in apps:
                findings += self._scan_app(app)
        except Exception as exc:
            logger.error("ArgoCD scan failed: %s", exc)
        return findings

    def _scan_app(self, app: dict) -> list[dict]:
        findings = []
        name = app.get("metadata", {}).get("name", "unknown")
        resource = f"argocd/app/{name}"
        health = app.get("status", {}).get("health", {}).get("status", "Unknown")
        sync = app.get("status", {}).get("sync", {}).get("status", "Unknown")

        if health in ("Degraded", "Missing"):
            findings.append(self._finding(
                resource, "HIGH", "reliability",
                f"ArgoCD application '{name}' health is '{health}'",
                "Investigate and resolve the degraded application state",
                {"health": health, "sync": sync},
            ))
        if sync == "OutOfSync":
            findings.append(self._finding(
                resource, "MEDIUM", "reliability",
                f"ArgoCD application '{name}' is out of sync with its Git source",
                "Sync the application or investigate drift between desired and live state",
                {"sync_status": sync},
            ))
        return findings
