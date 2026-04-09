"""GitLab plugin — python-gitlab. Covers repos and GitLab CI. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class GitLabPlugin(BasePlugin):
    name = "gitlab"
    credential_keys = ["GITLAB_TOKEN"]

    def is_available(self) -> bool:
        return bool(os.getenv("GITLAB_TOKEN"))

    def get_metadata(self) -> dict:
        try:
            import gitlab
            gl = gitlab.Gitlab(os.getenv("GITLAB_URL", "https://gitlab.com"), private_token=os.getenv("GITLAB_TOKEN"))
            gl.auth()
            return {"platform": self.name, "user": gl.users.get(gl.user.id).username}
        except Exception as exc:
            logger.warning("GitLab get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            import gitlab
            gl = gitlab.Gitlab(os.getenv("GITLAB_URL", "https://gitlab.com"), private_token=os.getenv("GITLAB_TOKEN"))
            gl.auth()
            group_name = os.getenv("GITLAB_GROUP")
            if group_name:
                group = gl.groups.get(group_name)
                projects = group.projects.list(all=True)
            else:
                projects = gl.projects.list(owned=True, all=True)[:50]
            for proj in projects:
                findings += self._scan_project(gl, proj)
        except Exception as exc:
            logger.error("GitLab scan failed: %s", exc)
        return findings

    def _scan_project(self, gl, proj) -> list[dict]:
        findings = []
        resource = f"gitlab/{proj.path_with_namespace}"
        try:
            full = gl.projects.get(proj.id)
            # Visibility
            if full.visibility == "public":
                findings.append(self._finding(
                    resource, "INFO", "security",
                    f"GitLab project '{proj.path_with_namespace}' is public",
                    "Confirm this project should be public",
                ))
            # Protected branches
            protected = full.protectedbranches.list()
            if not protected:
                findings.append(self._finding(
                    resource, "HIGH", "security",
                    f"GitLab project '{proj.path_with_namespace}' has no protected branches",
                    "Protect the default branch to require merge request approvals",
                ))
            # CI/CD — check for exposed secrets in .gitlab-ci.yml
            try:
                ci_file = full.files.get(".gitlab-ci.yml", ref=full.default_branch)
                content = ci_file.decode().decode("utf-8")
                for keyword in ["password", "secret", "api_key", "token", "AWS_SECRET"]:
                    if keyword.lower() in content.lower():
                        findings.append(self._finding(
                            resource, "CRITICAL", "security",
                            f"Possible hardcoded secret keyword '{keyword}' found in .gitlab-ci.yml",
                            "Use GitLab CI/CD variables for all secrets; never hardcode them",
                        ))
                        break
            except Exception:
                pass
        except Exception as exc:
            logger.warning("GitLab project scan error for %s: %s", proj.path_with_namespace, exc)
        return findings
