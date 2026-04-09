"""SonarQube / SonarCloud plugin — REST API. READ-ONLY."""
import os
import logging

import requests

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class SonarQubePlugin(BasePlugin):
    name = "sonarqube"
    credential_keys = ["SONAR_TOKEN"]

    def is_available(self) -> bool:
        return bool(os.getenv("SONAR_TOKEN"))

    def _base(self) -> str:
        return os.getenv("SONAR_URL", "https://sonarcloud.io").rstrip("/")

    def _headers(self) -> dict:
        import base64
        token = os.getenv("SONAR_TOKEN", "")
        encoded = base64.b64encode(f"{token}:".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def get_metadata(self) -> dict:
        try:
            r = requests.get(f"{self._base()}/api/system/status", headers=self._headers(), timeout=10)
            data = r.json()
            return {"platform": self.name, "url": self._base(), "status": data.get("status")}
        except Exception as exc:
            logger.warning("SonarQube get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            org = os.getenv("SONAR_ORG", "")
            params = {"organization": org, "ps": 100} if org else {"ps": 100}
            r = requests.get(
                f"{self._base()}/api/components/search",
                headers=self._headers(), params={**params, "qualifiers": "TRK"}, timeout=15,
            )
            components = r.json().get("components", [])
            for comp in components:
                findings += self._scan_project(comp)
        except Exception as exc:
            logger.error("SonarQube scan failed: %s", exc)
        return findings

    def _scan_project(self, comp: dict) -> list[dict]:
        findings = []
        key = comp.get("key", "")
        resource = f"sonarqube/{key}"
        try:
            r = requests.get(
                f"{self._base()}/api/measures/component",
                headers=self._headers(),
                params={
                    "component": key,
                    "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,security_hotspots_reviewed",
                },
                timeout=10,
            )
            measures = {m["metric"]: m.get("value") for m in r.json().get("component", {}).get("measures", [])}

            bugs = int(measures.get("bugs", 0) or 0)
            vulns = int(measures.get("vulnerabilities", 0) or 0)
            coverage = float(measures.get("coverage", 100) or 100)
            hotspots = float(measures.get("security_hotspots_reviewed", 100) or 100)

            if bugs > 0:
                findings.append(self._finding(
                    resource, "HIGH" if bugs > 10 else "MEDIUM", "reliability",
                    f"SonarQube reports {bugs} bug(s) in '{key}'",
                    "Review and fix bugs reported by SonarQube",
                    {"bugs": bugs},
                ))
            if vulns > 0:
                findings.append(self._finding(
                    resource, "CRITICAL" if vulns > 5 else "HIGH", "security",
                    f"SonarQube reports {vulns} vulnerability/vulnerabilities in '{key}'",
                    "Remediate all vulnerabilities identified by SonarQube",
                    {"vulnerabilities": vulns},
                ))
            if coverage < 60:
                findings.append(self._finding(
                    resource, "MEDIUM", "reliability",
                    f"Test coverage for '{key}' is {coverage:.1f}% (below 60% threshold)",
                    "Add unit tests to bring coverage above 80%",
                    {"coverage_pct": coverage},
                ))
            if hotspots < 80:
                findings.append(self._finding(
                    resource, "HIGH", "security",
                    f"Only {hotspots:.1f}% of security hotspots reviewed in '{key}'",
                    "Review and triage all security hotspots in SonarQube",
                    {"hotspots_reviewed_pct": hotspots},
                ))
        except Exception as exc:
            logger.warning("SonarQube project scan error for %s: %s", key, exc)
        return findings
