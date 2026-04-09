"""CircleCI plugin — v2 REST API. READ-ONLY."""
import os
import logging

import requests

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)

CIRCLECI_API = "https://circleci.com/api/v2"


class CircleCIPlugin(BasePlugin):
    name = "circleci"
    credential_keys = ["CIRCLECI_TOKEN"]

    def is_available(self) -> bool:
        return bool(os.getenv("CIRCLECI_TOKEN"))

    def _headers(self) -> dict:
        return {"Circle-Token": os.getenv("CIRCLECI_TOKEN", "")}

    def get_metadata(self) -> dict:
        try:
            r = requests.get(f"{CIRCLECI_API}/me", headers=self._headers(), timeout=10)
            data = r.json()
            return {"platform": self.name, "login": data.get("login"), "name": data.get("name")}
        except Exception as exc:
            logger.warning("CircleCI get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            r = requests.get(f"{CIRCLECI_API}/me/collaborations", headers=self._headers(), timeout=10)
            collabs = r.json() if isinstance(r.json(), list) else []
            for collab in collabs[:10]:
                slug = collab.get("slug", "")
                findings += self._scan_pipelines(slug)
        except Exception as exc:
            logger.error("CircleCI scan failed: %s", exc)
        return findings

    def _scan_pipelines(self, slug: str) -> list[dict]:
        findings = []
        try:
            r = requests.get(
                f"{CIRCLECI_API}/project/{slug}/pipeline",
                headers=self._headers(), timeout=10,
            )
            pipelines = r.json().get("items", [])
            failed = [p for p in pipelines if p.get("state") == "errored"]
            if failed:
                findings.append(self._finding(
                    f"circleci/{slug}", "HIGH", "reliability",
                    f"{len(failed)} pipeline(s) in '{slug}' are in errored state",
                    "Review and fix CircleCI pipeline errors",
                    {"errored_count": len(failed)},
                ))
        except Exception as exc:
            logger.warning("CircleCI pipeline scan error for %s: %s", slug, exc)
        return findings
