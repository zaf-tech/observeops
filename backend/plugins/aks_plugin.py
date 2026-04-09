"""AKS plugin — azure-sdk AKS + kubeconfig. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class AKSPlugin(BasePlugin):
    name = "aks"
    credential_keys = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def get_metadata(self) -> dict:
        return {"platform": self.name, "subscription": os.getenv("AZURE_SUBSCRIPTION_ID")}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.containerservice import ContainerServiceClient
            cred = ClientSecretCredential(
                tenant_id=os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET"),
            )
            sub_id = os.getenv("AZURE_SUBSCRIPTION_ID")
            client = ContainerServiceClient(cred, sub_id)
            for cluster in client.managed_clusters.list():
                resource = f"aks/{cluster.name}"
                if not cluster.enable_rbac:
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"AKS cluster '{cluster.name}' does not have RBAC enabled",
                        "Enable RBAC on the AKS cluster",
                    ))
                if cluster.kubernetes_version and float(".".join(cluster.kubernetes_version.split(".")[:2])) < 1.28:
                    findings.append(self._finding(
                        resource, "HIGH", "reliability",
                        f"AKS cluster '{cluster.name}' runs Kubernetes {cluster.kubernetes_version} (outdated)",
                        "Upgrade to a supported Kubernetes version",
                    ))
        except Exception as exc:
            logger.error("AKS scan failed: %s", exc)
        return findings
