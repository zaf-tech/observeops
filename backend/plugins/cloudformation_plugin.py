"""CloudFormation plugin — boto3. Scans stacks and templates. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class CloudFormationPlugin(BasePlugin):
    name = "cloudformation"
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
            cfn = boto3.client("cloudformation", region_name=region)
            paginator = cfn.get_paginator("list_stacks")
            for page in paginator.paginate(StackStatusFilter=["CREATE_FAILED", "ROLLBACK_FAILED", "UPDATE_ROLLBACK_FAILED", "UPDATE_COMPLETE", "CREATE_COMPLETE"]):
                for stack in page["StackSummaries"]:
                    findings += self._scan_stack(cfn, stack)
        except Exception as exc:
            logger.error("CloudFormation scan failed: %s", exc)
        return findings

    def _scan_stack(self, cfn, stack: dict) -> list[dict]:
        findings = []
        name = stack["StackName"]
        status = stack["StackStatus"]
        resource = f"cloudformation/stack/{name}"
        if "FAILED" in status or "ROLLBACK" in status:
            findings.append(self._finding(
                resource, "HIGH", "reliability",
                f"CloudFormation stack '{name}' is in failed/rollback state: {status}",
                "Review stack events in CloudFormation console and resolve the root cause",
                {"status": status},
            ))
        # Check termination protection
        try:
            detail = cfn.describe_stacks(StackName=name)["Stacks"][0]
            if not detail.get("EnableTerminationProtection"):
                findings.append(self._finding(
                    resource, "MEDIUM", "reliability",
                    f"CloudFormation stack '{name}' does not have termination protection enabled",
                    "Enable termination protection on production stacks to prevent accidental deletion",
                ))
        except Exception:
            pass
        return findings
