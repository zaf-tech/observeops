"""Azure plugin — azure-sdk. Covers AKS, ARM, Key Vault, Storage, Compute. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class AzurePlugin(BasePlugin):
    name = "azure"
    credential_keys = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def get_metadata(self) -> dict:
        try:
            sub_id = os.getenv("AZURE_SUBSCRIPTION_ID")
            return {"platform": self.name, "subscription_id": sub_id}
        except Exception as exc:
            logger.warning("Azure get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            from azure.identity import ClientSecretCredential
            cred = ClientSecretCredential(
                tenant_id=os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET"),
            )
            sub_id = os.getenv("AZURE_SUBSCRIPTION_ID")
            findings += self._scan_storage(cred, sub_id)
            findings += self._scan_vms(cred, sub_id)
            findings += self._scan_network(cred, sub_id)
        except Exception as exc:
            logger.error("Azure scan failed: %s", exc)
        return findings

    def _scan_storage(self, cred, sub_id) -> list[dict]:
        findings = []
        try:
            from azure.mgmt.storage import StorageManagementClient
            client = StorageManagementClient(cred, sub_id)
            for account in client.storage_accounts.list():
                resource = f"azure/storage/{account.name}"
                if account.allow_blob_public_access:
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"Storage account '{account.name}' allows public blob access",
                        "Set allowBlobPublicAccess=false on the storage account",
                        {"location": account.location},
                    ))
                if not account.enable_https_traffic_only:
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"Storage account '{account.name}' allows HTTP traffic",
                        "Enable 'Secure transfer required' (HTTPS only)",
                    ))
        except Exception as exc:
            logger.warning("Azure storage scan error: %s", exc)
        return findings

    def _scan_vms(self, cred, sub_id) -> list[dict]:
        findings = []
        try:
            from azure.mgmt.compute import ComputeManagementClient
            client = ComputeManagementClient(cred, sub_id)
            for vm in client.virtual_machines.list_all():
                resource = f"azure/vm/{vm.name}"
                if not vm.tags:
                    findings.append(self._finding(
                        resource, "LOW", "compliance",
                        f"Azure VM '{vm.name}' has no tags",
                        "Apply environment, owner, and cost-center tags to all VMs",
                    ))
        except Exception as exc:
            logger.warning("Azure VM scan error: %s", exc)
        return findings

    def _scan_network(self, cred, sub_id) -> list[dict]:
        findings = []
        try:
            from azure.mgmt.network import NetworkManagementClient
            client = NetworkManagementClient(cred, sub_id)
            for nsg in client.network_security_groups.list_all():
                for rule in (nsg.security_rules or []):
                    if (rule.access == "Allow"
                            and rule.direction == "Inbound"
                            and rule.source_address_prefix in ("*", "Internet", "0.0.0.0/0")):
                        findings.append(self._finding(
                            f"azure/nsg/{nsg.name}/rule/{rule.name}",
                            "HIGH", "security",
                            f"NSG '{nsg.name}' allows inbound traffic from any source on port {rule.destination_port_range}",
                            "Restrict inbound rules to known IP ranges",
                            {"priority": rule.priority, "protocol": rule.protocol},
                        ))
        except Exception as exc:
            logger.warning("Azure network scan error: %s", exc)
        return findings
