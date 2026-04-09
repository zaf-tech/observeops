"""GCP plugin — google-cloud-sdk. Covers GKE, GCS, IAM, Cloud Build. READ-ONLY.

Supports two credential modes:
  1. GCP_SERVICE_ACCOUNT_JSON — raw JSON string of a service account key file
     (preferred; works in Docker without file-path mounting)
  2. GOOGLE_APPLICATION_CREDENTIALS + GCP_PROJECT_ID — legacy file-path mode
"""
import json
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


def _get_gcp_credentials():
    """
    Return (credentials, project_id) or raise if neither mode is configured.
    Prefers GCP_SERVICE_ACCOUNT_JSON; falls back to GOOGLE_APPLICATION_CREDENTIALS.
    """
    sa_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if sa_json:
        from google.oauth2 import service_account
        info = json.loads(sa_json)
        project_id = os.getenv("GCP_PROJECT_ID") or info.get("project_id", "")
        scopes = [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/cloud-platform.read-only",
        ]
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        return creds, project_id

    # Legacy file-path mode
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.getenv("GCP_PROJECT_ID", "")
    if not creds_path or not project_id:
        raise RuntimeError("No GCP credentials configured")

    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(creds_path)
    return creds, project_id


class GCPPlugin(BasePlugin):
    name = "gcp"
    credential_keys = ["GCP_SERVICE_ACCOUNT_JSON", "GCP_PROJECT_ID"]

    def is_available(self) -> bool:
        # Mode 1: JSON string uploaded via UI
        if os.getenv("GCP_SERVICE_ACCOUNT_JSON"):
            return True
        # Mode 2: file path + project ID
        return bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and os.getenv("GCP_PROJECT_ID"))

    def get_metadata(self) -> dict:
        try:
            _, project_id = _get_gcp_credentials()
            return {"platform": self.name, "project_id": project_id}
        except Exception:
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            creds, project_id = _get_gcp_credentials()
            findings += self._scan_storage(creds, project_id)
            findings += self._scan_iam(creds, project_id)
        except Exception as exc:
            logger.error("GCP scan failed: %s", exc)
        return findings

    def _scan_storage(self, creds, project_id: str) -> list[dict]:
        findings = []
        try:
            from google.cloud import storage
            client = storage.Client(project=project_id, credentials=creds)
            for bucket in client.list_buckets():
                resource = f"gcs://{bucket.name}"
                if not bucket.iam_configuration.uniform_bucket_level_access_enabled:
                    findings.append(self._finding(
                        resource, "MEDIUM", "security",
                        f"GCS bucket '{bucket.name}' does not have uniform bucket-level access enabled",
                        "Enable uniform bucket-level access to simplify permission management",
                    ))
                if bucket.iam_configuration.public_access_prevention != "enforced":
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"GCS bucket '{bucket.name}' does not enforce public access prevention",
                        "Set publicAccessPrevention to 'enforced'",
                    ))
        except Exception as exc:
            logger.warning("GCS scan error: %s", exc)
        return findings

    def _scan_iam(self, creds, project_id: str) -> list[dict]:
        findings = []
        try:
            from google.cloud import resourcemanager_v3
            client = resourcemanager_v3.ProjectsClient(credentials=creds)
            policy = client.get_iam_policy(resource=f"projects/{project_id}")
            for binding in policy.bindings:
                if binding.role in ("roles/owner", "roles/editor"):
                    for member in binding.members:
                        if member.startswith("user:"):
                            findings.append(self._finding(
                                f"gcp/iam/project/{project_id}",
                                "HIGH", "security",
                                f"User '{member}' has broad role '{binding.role}' on project",
                                "Apply least-privilege: replace owner/editor with specific roles",
                                {"role": binding.role, "member": member},
                            ))
        except Exception as exc:
            logger.warning("GCP IAM scan error: %s", exc)
        return findings
