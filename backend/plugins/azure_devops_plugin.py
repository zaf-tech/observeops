"""Azure DevOps plugin — azure-devops SDK. Covers pipelines and repos. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class AzureDevOpsPlugin(BasePlugin):
    name = "azure_devops"
    credential_keys = ["AZURE_DEVOPS_TOKEN", "AZURE_DEVOPS_ORG"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def _get_connection(self):
        from azure.devops.connection import Connection
        from msrest.authentication import BasicAuthentication
        org = os.getenv("AZURE_DEVOPS_ORG", "")
        token = os.getenv("AZURE_DEVOPS_TOKEN", "")
        creds = BasicAuthentication("", token)
        return Connection(base_url=f"https://dev.azure.com/{org}", creds=creds)

    def get_metadata(self) -> dict:
        try:
            conn = self._get_connection()
            core_client = conn.clients.get_core_client()
            projects = core_client.get_projects()
            return {"platform": self.name, "org": os.getenv("AZURE_DEVOPS_ORG"), "project_count": len(list(projects))}
        except Exception as exc:
            logger.warning("Azure DevOps get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            conn = self._get_connection()
            core_client = conn.clients.get_core_client()
            build_client = conn.clients.get_build_client()
            projects = list(core_client.get_projects())
            for proj in projects:
                findings += self._scan_pipelines(build_client, proj.name)
        except Exception as exc:
            logger.error("Azure DevOps scan failed: %s", exc)
        return findings

    def _scan_pipelines(self, build_client, project: str) -> list[dict]:
        findings = []
        try:
            builds = build_client.get_builds(project, top=50)
            failed = [b for b in builds if b.result == "failed"]
            if failed:
                findings.append(self._finding(
                    f"azure_devops/{project}/pipelines",
                    "HIGH", "reliability",
                    f"{len(failed)} Azure DevOps pipeline build(s) failed in project '{project}'",
                    "Investigate failed builds in Azure DevOps",
                    {"failed_count": len(failed)},
                ))
        except Exception as exc:
            logger.warning("Azure DevOps pipeline scan error for %s: %s", project, exc)
        return findings
