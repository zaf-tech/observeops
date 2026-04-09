# Plugin Template

Use this template when generating a new plugin file.

```python
"""
{Platform} plugin for ObserverAI.
Category: {category}
Library:  {library}
"""

import os
import logging
from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class {ClassName}Plugin(BasePlugin):
    name = "{name}"
    credential_keys = [{credential_keys}]  # env vars that activate this plugin

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def get_metadata(self) -> dict:
        try:
            # TODO: return platform version, account/org info, region, etc.
            return {
                "platform": self.name,
                "version": "unknown",
            }
        except Exception as exc:
            logger.warning("get_metadata failed: %s", exc)
            return {"platform": self.name}

    # ------------------------------------------------------------------
    # Scan  (READ-ONLY — never write, delete, or modify anything)
    # ------------------------------------------------------------------
    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            client = self._build_client()
            # TODO: call read-only APIs and populate findings
            # findings.append(self._finding(...))
        except Exception as exc:
            logger.error("Scan failed for %s: %s", self.name, exc)
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_client(self):
        """Initialise and return the SDK client using env-var credentials."""
        # TODO: build & return read-only SDK client
        raise NotImplementedError

    def _finding(
        self,
        resource: str,
        severity: str,
        category: str,
        finding: str,
        recommendation: str,
        evidence: dict | None = None,
    ) -> dict:
        return {
            "platform": self.name,
            "resource": resource,
            "severity": severity,       # CRITICAL / HIGH / MEDIUM / LOW / INFO
            "category": category,       # security / cost / reliability / performance / compliance
            "finding": finding,
            "recommendation": recommendation,
            "evidence": evidence or {},
        }
```
