"""JFrog Artifactory plugin — REST API. READ-ONLY."""
import os
import logging

import requests

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class ArtifactoryPlugin(BasePlugin):
    name = "artifactory"
    credential_keys = ["ARTIFACTORY_URL", "ARTIFACTORY_TOKEN"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {os.getenv('ARTIFACTORY_TOKEN', '')}"}

    def _base(self) -> str:
        return os.getenv("ARTIFACTORY_URL", "").rstrip("/")

    def get_metadata(self) -> dict:
        try:
            r = requests.get(f"{self._base()}/artifactory/api/system/ping", headers=self._headers(), timeout=10)
            return {"platform": self.name, "url": self._base(), "status": r.text.strip()}
        except Exception as exc:
            logger.warning("Artifactory get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            r = requests.get(
                f"{self._base()}/artifactory/api/repositories",
                headers=self._headers(), timeout=10,
            )
            repos = r.json() if isinstance(r.json(), list) else []
            for repo in repos:
                key = repo.get("key", "")
                rtype = repo.get("type", "")
                if rtype == "LOCAL" and not repo.get("xrayIndex"):
                    findings.append(self._finding(
                        f"artifactory/{key}", "HIGH", "security",
                        f"Artifactory repository '{key}' does not have Xray scanning enabled",
                        "Enable JFrog Xray scanning on all local repositories",
                    ))
        except Exception as exc:
            logger.error("Artifactory scan failed: %s", exc)
        return findings
