"""Helm plugin — parse Chart.yaml and values.yaml for misconfigurations. READ-ONLY."""
import os
import logging
import pathlib

import yaml

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)

HELM_PATH = os.getenv("HELM_PATH", ".")


class HelmPlugin(BasePlugin):
    name = "helm"
    credential_keys = []

    def is_available(self) -> bool:
        root = pathlib.Path(HELM_PATH)
        return any(root.rglob("Chart.yaml"))

    def get_metadata(self) -> dict:
        charts = list(pathlib.Path(HELM_PATH).rglob("Chart.yaml"))
        return {"platform": self.name, "chart_count": len(charts)}

    def run_scan(self) -> list[dict]:
        findings = []
        try:
            for chart_file in pathlib.Path(HELM_PATH).rglob("Chart.yaml"):
                findings += self._scan_chart(chart_file.parent)
        except Exception as exc:
            logger.error("Helm scan failed: %s", exc)
        return findings

    def _scan_chart(self, chart_dir: pathlib.Path) -> list[dict]:
        findings = []
        resource = str(chart_dir)
        try:
            chart = yaml.safe_load((chart_dir / "Chart.yaml").read_text())
            values_file = chart_dir / "values.yaml"
            values = yaml.safe_load(values_file.read_text()) if values_file.exists() else {}
            chart_name = chart.get("name", str(chart_dir))
            # Deprecated API versions
            for tmpl in (chart_dir / "templates").glob("*.yaml") if (chart_dir / "templates").exists() else []:
                content = tmpl.read_text()
                for deprecated in ["extensions/v1beta1", "apps/v1beta1", "apps/v1beta2"]:
                    if deprecated in content:
                        findings.append(self._finding(
                            resource, "HIGH", "reliability",
                            f"Helm chart '{chart_name}' uses deprecated Kubernetes API '{deprecated}'",
                            f"Migrate to the stable API version (apps/v1 or networking.k8s.io/v1)",
                            {"template": tmpl.name},
                        ))
            # Resource limits
            if not _nested_get(values, "resources", "limits"):
                findings.append(self._finding(
                    resource, "MEDIUM", "reliability",
                    f"Helm chart '{chart_name}' values.yaml does not define resource limits",
                    "Set resources.limits.cpu and resources.limits.memory to prevent resource contention",
                ))
            # Image tag latest
            image_tag = _nested_get(values, "image", "tag") or ""
            if str(image_tag).lower() in ("latest", ""):
                findings.append(self._finding(
                    resource, "HIGH", "reliability",
                    f"Helm chart '{chart_name}' uses 'latest' or unspecified image tag",
                    "Pin image tags to a specific version for reproducible deployments",
                ))
        except Exception as exc:
            logger.warning("Helm chart scan error %s: %s", chart_dir, exc)
        return findings


def _nested_get(d: dict, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d
