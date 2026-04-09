"""Snyk plugin — REST API (read findings only). READ-ONLY."""
import os
import logging

import requests

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)

SNYK_API = "https://api.snyk.io/rest"
SNYK_V1  = "https://snyk.io/api/v1"


class SnykPlugin(BasePlugin):
    name = "snyk"
    credential_keys = ["SNYK_TOKEN"]

    def is_available(self) -> bool:
        return bool(os.getenv("SNYK_TOKEN"))

    def _headers(self) -> dict:
        return {"Authorization": f"token {os.getenv('SNYK_TOKEN')}"}

    def get_metadata(self) -> dict:
        try:
            r = requests.get(f"{SNYK_V1}/user/me", headers=self._headers(), timeout=10)
            data = r.json()
            return {"platform": self.name, "username": data.get("username"), "email": data.get("email")}
        except Exception as exc:
            logger.warning("Snyk get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            orgs = self._get_orgs()
            for org in orgs[:5]:  # limit to 5 orgs
                findings += self._scan_org(org)
        except Exception as exc:
            logger.error("Snyk scan failed: %s", exc)
        return findings

    def _get_orgs(self) -> list[dict]:
        try:
            r = requests.get(f"{SNYK_V1}/orgs", headers=self._headers(), timeout=10)
            return r.json().get("orgs", [])
        except Exception:
            return []

    def _scan_org(self, org: dict) -> list[dict]:
        findings = []
        org_id = org.get("id", "")
        org_name = org.get("name", org_id)
        try:
            r = requests.post(
                f"{SNYK_V1}/org/{org_id}/issues",
                headers=self._headers(),
                json={"filters": {"severities": ["critical", "high", "medium"], "types": ["vuln"]}},
                timeout=15,
            )
            issues = r.json().get("results", [])
            crit = sum(1 for i in issues if i.get("severity") == "critical")
            high = sum(1 for i in issues if i.get("severity") == "high")
            med  = sum(1 for i in issues if i.get("severity") == "medium")
            if crit:
                findings.append(self._finding(
                    f"snyk/org/{org_name}", "CRITICAL", "security",
                    f"Snyk found {crit} critical vulnerability/vulnerabilities in org '{org_name}'",
                    "Upgrade or patch the affected dependencies immediately",
                    {"critical": crit, "high": high, "medium": med},
                ))
            elif high:
                findings.append(self._finding(
                    f"snyk/org/{org_name}", "HIGH", "security",
                    f"Snyk found {high} high-severity vulnerability/vulnerabilities in org '{org_name}'",
                    "Review and remediate high-severity dependency issues",
                    {"high": high, "medium": med},
                ))
        except Exception as exc:
            logger.warning("Snyk org scan error for %s: %s", org_name, exc)
        return findings
