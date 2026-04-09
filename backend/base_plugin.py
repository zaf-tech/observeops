"""Abstract base class that every ObserverAI platform plugin must inherit from."""
import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    name: str = ""
    credential_keys: list[str] = []

    @abstractmethod
    def is_available(self) -> bool:
        """Return True only if ALL credential_keys are present in the environment."""

    @abstractmethod
    def run_scan(self) -> list[dict]:
        """
        Execute a read-only scan and return a list of Finding dicts.
        MUST never raise — return [] on any error.
        """

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return platform version, account/org/region info."""

    # ------------------------------------------------------------------
    # Shared helper — all plugins should use this to build findings
    # ------------------------------------------------------------------
    def _finding(
        self,
        resource: str,
        severity: str,
        category: str,
        finding: str,
        recommendation: str,
        evidence: dict | None = None,
    ) -> dict:
        """
        Build a Finding dict that conforms to the ObserveOps schema.

        severity  : CRITICAL | HIGH | MEDIUM | LOW | INFO
        category  : security | cost | reliability | performance | compliance
        """
        return {
            "platform": self.name,
            "resource": resource,
            "severity": severity,
            "category": category,
            "finding": finding,
            "recommendation": recommendation,
            "evidence": evidence or {},
        }
