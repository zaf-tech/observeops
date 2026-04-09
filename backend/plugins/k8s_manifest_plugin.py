"""Kubernetes manifest plugin — scan YAML files for security misconfigurations. READ-ONLY."""
import os
import logging
import pathlib

import yaml

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)

K8S_PATH = os.getenv("K8S_MANIFEST_PATH", ".")


class K8sManifestPlugin(BasePlugin):
    name = "k8s_manifest"
    credential_keys = []

    def is_available(self) -> bool:
        root = pathlib.Path(K8S_PATH)
        return any(
            ("kind:" in f.read_text(errors="ignore"))
            for f in root.rglob("*.yaml")
            if f.stat().st_size < 1_000_000
        )

    def get_metadata(self) -> dict:
        return {"platform": self.name, "scan_path": K8S_PATH}

    def run_scan(self) -> list[dict]:
        findings = []
        try:
            for yaml_file in pathlib.Path(K8S_PATH).rglob("*.yaml"):
                if yaml_file.stat().st_size > 1_000_000:
                    continue
                findings += self._scan_file(yaml_file)
        except Exception as exc:
            logger.error("K8s manifest scan failed: %s", exc)
        return findings

    def _scan_file(self, path: pathlib.Path) -> list[dict]:
        findings = []
        try:
            for doc in yaml.safe_load_all(path.read_text()):
                if not isinstance(doc, dict):
                    continue
                kind = doc.get("kind", "")
                name = (doc.get("metadata") or {}).get("name", str(path))
                resource = f"k8s/{kind}/{name}"
                if kind in ("Deployment", "DaemonSet", "StatefulSet", "Pod"):
                    findings += self._check_workload(resource, doc, path)
        except Exception as exc:
            logger.warning("K8s manifest parse error %s: %s", path, exc)
        return findings

    def _check_workload(self, resource: str, doc: dict, path: pathlib.Path) -> list[dict]:
        findings = []
        spec = doc.get("spec", {})
        template = spec.get("template", {})
        containers = (template.get("spec") or spec).get("containers", [])

        for container in containers:
            cname = container.get("name", "unknown")
            sec_ctx = container.get("securityContext") or {}

            # runAsRoot
            if sec_ctx.get("runAsUser") == 0:
                findings.append(self._finding(
                    resource, "CRITICAL", "security",
                    f"Container '{cname}' in '{path.name}' runs as root (UID 0)",
                    "Set securityContext.runAsNonRoot=true and runAsUser to a non-zero UID",
                ))

            # Privileged container
            if sec_ctx.get("privileged"):
                findings.append(self._finding(
                    resource, "CRITICAL", "security",
                    f"Container '{cname}' in '{path.name}' runs in privileged mode",
                    "Remove privileged: true from securityContext",
                ))

            # No resource limits
            resources = container.get("resources") or {}
            if not (resources.get("limits") or {}).get("cpu") or not (resources.get("limits") or {}).get("memory"):
                findings.append(self._finding(
                    resource, "MEDIUM", "reliability",
                    f"Container '{cname}' in '{path.name}' has no CPU/memory limits",
                    "Set resources.limits.cpu and resources.limits.memory",
                ))

            # Image with latest tag
            image = container.get("image", "")
            if image.endswith(":latest") or ":" not in image:
                findings.append(self._finding(
                    resource, "HIGH", "reliability",
                    f"Container '{cname}' uses 'latest' or untagged image: '{image}'",
                    "Pin the image to a specific digest or version tag",
                    {"image": image},
                ))

            # readOnlyRootFilesystem
            if not sec_ctx.get("readOnlyRootFilesystem"):
                findings.append(self._finding(
                    resource, "LOW", "security",
                    f"Container '{cname}' does not set readOnlyRootFilesystem=true",
                    "Set securityContext.readOnlyRootFilesystem=true to reduce attack surface",
                ))

        return findings
