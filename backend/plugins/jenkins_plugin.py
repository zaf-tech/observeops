"""Jenkins plugin — REST API. READ-ONLY."""
import os
import logging

import requests
from requests.auth import HTTPBasicAuth

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class JenkinsPlugin(BasePlugin):
    name = "jenkins"
    credential_keys = ["JENKINS_URL", "JENKINS_USER", "JENKINS_TOKEN"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def _auth(self):
        return HTTPBasicAuth(os.getenv("JENKINS_USER"), os.getenv("JENKINS_TOKEN"))

    def _base(self) -> str:
        return os.getenv("JENKINS_URL", "").rstrip("/")

    def get_metadata(self) -> dict:
        try:
            r = requests.get(f"{self._base()}/api/json", auth=self._auth(), timeout=10)
            data = r.json()
            return {"platform": self.name, "url": self._base(), "mode": data.get("mode")}
        except Exception as exc:
            logger.warning("Jenkins get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            r = requests.get(
                f"{self._base()}/api/json?tree=jobs[name,color,lastBuild[result,duration,timestamp]]",
                auth=self._auth(), timeout=15,
            )
            jobs = r.json().get("jobs", [])
            for job in jobs:
                findings += self._scan_job(job)
            # CSRF check
            findings += self._check_csrf()
        except Exception as exc:
            logger.error("Jenkins scan failed: %s", exc)
        return findings

    def _scan_job(self, job: dict) -> list[dict]:
        findings = []
        name = job.get("name", "unknown")
        resource = f"jenkins/job/{name}"
        color = job.get("color", "")
        # Failing jobs
        if "red" in color:
            findings.append(self._finding(
                resource, "HIGH", "reliability",
                f"Jenkins job '{name}' is currently failing",
                "Investigate and fix the failing build",
                {"color": color},
            ))
        # Disabled jobs
        if "disabled" in color:
            findings.append(self._finding(
                resource, "LOW", "cost",
                f"Jenkins job '{name}' is disabled",
                "Remove or archive disabled jobs to reduce clutter",
            ))
        # Long-running builds
        last = job.get("lastBuild") or {}
        duration_ms = last.get("duration", 0)
        if duration_ms > 30 * 60 * 1000:  # 30 minutes
            findings.append(self._finding(
                resource, "MEDIUM", "performance",
                f"Jenkins job '{name}' last build took {duration_ms // 60000} minutes",
                "Optimise build steps; consider parallelisation or caching",
                {"duration_min": duration_ms // 60000},
            ))
        return findings

    def _check_csrf(self) -> list[dict]:
        try:
            r = requests.get(f"{self._base()}/crumbIssuer/api/json", auth=self._auth(), timeout=10)
            if r.status_code != 200:
                return [self._finding(
                    "jenkins/security", "HIGH", "security",
                    "Jenkins CSRF protection (crumb issuer) appears to be disabled",
                    "Enable CSRF protection in Jenkins security settings",
                )]
        except Exception:
            pass
        return []
