"""Nexus Repository plugin — REST API. READ-ONLY."""
import os
import logging

import requests
from requests.auth import HTTPBasicAuth

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class NexusPlugin(BasePlugin):
    name = "nexus"
    credential_keys = ["NEXUS_URL", "NEXUS_USER", "NEXUS_PASSWORD"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def _auth(self):
        return HTTPBasicAuth(os.getenv("NEXUS_USER"), os.getenv("NEXUS_PASSWORD"))

    def _base(self) -> str:
        return os.getenv("NEXUS_URL", "").rstrip("/")

    def get_metadata(self) -> dict:
        try:
            r = requests.get(f"{self._base()}/service/rest/v1/status", auth=self._auth(), timeout=10)
            return {"platform": self.name, "url": self._base(), "status": r.status_code}
        except Exception as exc:
            logger.warning("Nexus get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            r = requests.get(f"{self._base()}/service/rest/v1/repositories", auth=self._auth(), timeout=10)
            repos = r.json() if isinstance(r.json(), list) else []
            for repo in repos:
                name = repo.get("name", "")
                if repo.get("type") == "hosted" and not repo.get("cleanup"):
                    findings.append(self._finding(
                        f"nexus/{name}", "LOW", "cost",
                        f"Nexus repository '{name}' has no cleanup policy configured",
                        "Configure a cleanup policy to remove old artifacts and free disk space",
                    ))
        except Exception as exc:
            logger.error("Nexus scan failed: %s", exc)
        return findings
