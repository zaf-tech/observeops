"""EKS plugin — boto3 EKS + kubeconfig. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class EKSPlugin(BasePlugin):
    name = "eks"
    credential_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def get_metadata(self) -> dict:
        return {"platform": self.name, "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1")}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            import boto3
            region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            eks = boto3.client("eks", region_name=region)
            clusters = eks.list_clusters().get("clusters", [])
            for cluster_name in clusters:
                cluster = eks.describe_cluster(name=cluster_name)["cluster"]
                resource = f"eks/{cluster_name}"
                # Logging disabled
                log_config = cluster.get("logging", {}).get("clusterLogging", [])
                enabled_logs = [lc for lc in log_config if lc.get("enabled")]
                if not enabled_logs:
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"EKS cluster '{cluster_name}' has no control plane logging enabled",
                        "Enable API server, audit, and authenticator logs in EKS cluster settings",
                    ))
                # Public endpoint
                if cluster.get("resourcesVpcConfig", {}).get("endpointPublicAccess"):
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"EKS cluster '{cluster_name}' has a public API endpoint",
                        "Disable public endpoint access or restrict to known CIDRs",
                        {"public_cidrs": cluster.get("resourcesVpcConfig", {}).get("publicAccessCidrs", [])},
                    ))
                # Outdated Kubernetes version
                version = cluster.get("version", "")
                if version and float(version) < 1.28:
                    findings.append(self._finding(
                        resource, "HIGH", "reliability",
                        f"EKS cluster '{cluster_name}' is running Kubernetes {version} (outdated)",
                        "Upgrade to a supported Kubernetes version",
                        {"current_version": version},
                    ))
        except Exception as exc:
            logger.error("EKS scan failed: %s", exc)
        return findings
