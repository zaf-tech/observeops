"""GKE plugin — google-cloud-container + kubeconfig. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class GKEPlugin(BasePlugin):
    name = "gke"
    credential_keys = ["GOOGLE_APPLICATION_CREDENTIALS", "GCP_PROJECT_ID"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def get_metadata(self) -> dict:
        return {"platform": self.name, "project": os.getenv("GCP_PROJECT_ID")}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            from google.cloud import container_v1
            client = container_v1.ClusterManagerClient()
            project = os.getenv("GCP_PROJECT_ID")
            parent = f"projects/{project}/locations/-"
            clusters = client.list_clusters(parent=parent).clusters
            for cluster in clusters:
                resource = f"gke/{cluster.name}"
                if not cluster.legacy_abac.enabled is False:
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"GKE cluster '{cluster.name}' has Legacy ABAC enabled",
                        "Disable Legacy ABAC and use RBAC instead",
                    ))
                if cluster.master_auth.username:
                    findings.append(self._finding(
                        resource, "CRITICAL", "security",
                        f"GKE cluster '{cluster.name}' has basic authentication enabled",
                        "Disable basic authentication on the cluster master",
                    ))
        except Exception as exc:
            logger.error("GKE scan failed: %s", exc)
        return findings
