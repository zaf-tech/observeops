"""Bitbucket plugin — atlassian-python-api. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class BitbucketPlugin(BasePlugin):
    name = "bitbucket"
    credential_keys = ["BITBUCKET_USERNAME", "BITBUCKET_APP_PASSWORD", "BITBUCKET_WORKSPACE"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def get_metadata(self) -> dict:
        return {"platform": self.name, "workspace": os.getenv("BITBUCKET_WORKSPACE")}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            from atlassian import Bitbucket
            bb = Bitbucket(
                url="https://api.bitbucket.org",
                username=os.getenv("BITBUCKET_USERNAME"),
                password=os.getenv("BITBUCKET_APP_PASSWORD"),
            )
            workspace = os.getenv("BITBUCKET_WORKSPACE", "")
            repos = bb.get_repositories(workspace)
            for repo in repos:
                slug = repo.get("slug", "")
                is_private = repo.get("is_private", True)
                resource = f"bitbucket/{workspace}/{slug}"
                if not is_private:
                    findings.append(self._finding(
                        resource, "INFO", "security",
                        f"Bitbucket repository '{slug}' is public",
                        "Confirm this repository should be public",
                    ))
        except Exception as exc:
            logger.error("Bitbucket scan failed: %s", exc)
        return findings
