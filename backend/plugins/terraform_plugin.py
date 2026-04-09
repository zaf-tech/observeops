"""Terraform plugin — static analysis of .tf and .tfstate files. READ-ONLY."""
import os
import json
import logging
import pathlib

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)

TERRAFORM_PATH = os.getenv("TERRAFORM_PATH", ".")


class TerraformPlugin(BasePlugin):
    name = "terraform"
    credential_keys = []  # no credentials needed — reads local files

    def is_available(self) -> bool:
        root = pathlib.Path(TERRAFORM_PATH)
        return any(root.rglob("*.tf")) or any(root.rglob("*.tfstate"))

    def get_metadata(self) -> dict:
        root = pathlib.Path(TERRAFORM_PATH)
        tf_files = list(root.rglob("*.tf"))
        state_files = list(root.rglob("*.tfstate"))
        return {"platform": self.name, "tf_files": len(tf_files), "state_files": len(state_files)}

    def run_scan(self) -> list[dict]:
        findings = []
        try:
            root = pathlib.Path(TERRAFORM_PATH)
            for tf_file in root.rglob("*.tf"):
                findings += self._scan_tf_file(tf_file)
            for state_file in root.rglob("*.tfstate"):
                findings += self._scan_state_file(state_file)
        except Exception as exc:
            logger.error("Terraform scan failed: %s", exc)
        return findings

    def _scan_tf_file(self, path: pathlib.Path) -> list[dict]:
        findings = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            resource = str(path)
            # Hardcoded secrets check
            secret_patterns = ["password", "secret", "private_key", "access_key", "api_key"]
            for pattern in secret_patterns:
                lines = [i + 1 for i, line in enumerate(content.splitlines())
                         if pattern in line.lower() and "var." not in line and "#" not in line.split(pattern)[0]]
                if lines:
                    findings.append(self._finding(
                        resource, "CRITICAL", "security",
                        f"Possible hardcoded secret '{pattern}' found in Terraform file",
                        "Move secrets to variables or a secrets manager; never hardcode in .tf files",
                        {"lines": lines[:5]},
                    ))
            # Backend not configured
            if "terraform {" in content and "backend" not in content:
                findings.append(self._finding(
                    resource, "HIGH", "reliability",
                    "Terraform configuration has no remote backend configured",
                    "Configure a remote backend (S3, Azure Blob, GCS) for state management",
                ))
        except Exception as exc:
            logger.warning("Terraform file scan error %s: %s", path, exc)
        return findings

    def _scan_state_file(self, path: pathlib.Path) -> list[dict]:
        findings = []
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            resource = str(path)
            # State file should not be committed
            findings.append(self._finding(
                resource, "HIGH", "security",
                f"Terraform state file found at '{path}' — may be committed to source control",
                "Add *.tfstate to .gitignore and use a remote backend for state storage",
            ))
            # Check for sensitive values in state
            state_str = json.dumps(state).lower()
            for keyword in ["password", "secret", "private_key"]:
                if keyword in state_str:
                    findings.append(self._finding(
                        resource, "CRITICAL", "security",
                        f"Terraform state file may contain sensitive value '{keyword}'",
                        "Use encrypted remote state storage and restrict access to state files",
                    ))
                    break
        except Exception as exc:
            logger.warning("Terraform state scan error %s: %s", path, exc)
        return findings
