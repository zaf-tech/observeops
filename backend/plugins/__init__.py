"""Plugin registry — discovers and returns all available plugins."""
import importlib
import logging
import pathlib

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)

_PLUGIN_MODULES = [
    # Cloud & Kubernetes
    "plugins.aws_plugin",
    "plugins.azure_plugin",
    "plugins.gcp_plugin",
    "plugins.eks_plugin",
    "plugins.aks_plugin",
    "plugins.gke_plugin",
    "plugins.cloudformation_plugin",
    # Code & Artifact Repositories
    "plugins.github_plugin",
    "plugins.gitlab_plugin",
    "plugins.bitbucket_plugin",
    "plugins.artifactory_plugin",
    "plugins.nexus_plugin",
    # CI/CD
    "plugins.jenkins_plugin",
    "plugins.azure_devops_plugin",
    "plugins.circleci_plugin",
    "plugins.argocd_plugin",
    # Code Quality & Security
    "plugins.sonarqube_plugin",
    "plugins.snyk_plugin",
    # IaC
    "plugins.terraform_plugin",
    "plugins.helm_plugin",
    "plugins.k8s_manifest_plugin",
]


def all_plugins() -> list[BasePlugin]:
    """Return one instance of every registered plugin."""
    instances: list[BasePlugin] = []
    for module_path in _PLUGIN_MODULES:
        try:
            mod = importlib.import_module(module_path)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                    and attr.__module__ == mod.__name__
                ):
                    instances.append(attr())
        except Exception as exc:
            logger.warning("Could not load plugin module %s: %s", module_path, exc)
    return instances


def discover_plugins() -> list[BasePlugin]:
    """Return only plugins whose credentials are available in the environment."""
    return [p for p in all_plugins() if p.is_available()]
