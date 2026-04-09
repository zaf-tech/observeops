"""GitHub plugin — PyGithub. Scans repos, PRs, Actions, branch protection. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class GitHubPlugin(BasePlugin):
    name = "github"
    credential_keys = ["GITHUB_TOKEN"]

    def is_available(self) -> bool:
        return bool(os.getenv("GITHUB_TOKEN"))

    def get_metadata(self) -> dict:
        try:
            from github import Github
            from datetime import datetime, timezone, timedelta

            g = Github(os.getenv("GITHUB_TOKEN"))
            user = g.get_user()
            org_name = os.getenv("GITHUB_ORG", "")
            since_90d = datetime.now(timezone.utc) - timedelta(days=90)

            stats: dict = {
                "platform": self.name,
                "login": user.login,
                "org": org_name,
            }

            # Repo counts — use API user/org attributes first (no iteration needed)
            repos_sample: list = []
            if org_name:
                try:
                    org = g.get_organization(org_name)
                    stats["total_repos"]   = org.public_repos + (org.total_private_repos or 0)
                    stats["public_repos"]  = org.public_repos
                    stats["private_repos"] = org.total_private_repos or 0
                    try:
                        stats["total_members"] = org.get_members().totalCount
                    except Exception:
                        pass
                    repos_sample = list(org.get_repos())[:25]
                except Exception:
                    org_name = ""  # fall through below

            if not org_name:
                stats["total_repos"]   = user.public_repos + (user.total_private_repos or 0)
                stats["public_repos"]  = user.public_repos
                stats["private_repos"] = user.total_private_repos or 0
                repos_sample = list(user.get_repos())[:25]

            # Deep stats sampled over first N repos to respect rate limits
            total_workflows      = 0
            repos_with_actions   = 0
            commits_last_90d     = 0
            merged_prs_last_90d  = 0
            contributor_counts: dict[str, int] = {}

            for repo in repos_sample[:15]:
                # GitHub Actions workflows
                try:
                    wfs = list(repo.get_workflows())
                    if wfs:
                        repos_with_actions += 1
                        total_workflows += len(wfs)
                except Exception:
                    pass

                # Commits in last 90 days
                try:
                    commits = list(repo.get_commits(since=since_90d))
                    commits_last_90d += len(commits)
                except Exception:
                    pass

                # Contributors (top across sample)
                try:
                    for contrib in list(repo.get_contributors())[:10]:
                        contributor_counts[contrib.login] = (
                            contributor_counts.get(contrib.login, 0) + contrib.contributions
                        )
                except Exception:
                    pass

                # Merged PRs in last 90 days
                try:
                    for pr in list(repo.get_pulls(state="closed", sort="updated", direction="desc"))[:30]:
                        if pr.merged_at and pr.merged_at.replace(tzinfo=timezone.utc) > since_90d:
                            merged_prs_last_90d += 1
                        elif pr.updated_at and pr.updated_at.replace(tzinfo=timezone.utc) < since_90d:
                            break
                except Exception:
                    pass

            top_contributors = sorted(
                [{"login": l, "contributions": c} for l, c in contributor_counts.items()],
                key=lambda x: x["contributions"],
                reverse=True,
            )[:5]

            stats.update({
                "total_workflows":        total_workflows,
                "repos_with_actions":     repos_with_actions,
                "commits_last_90_days":   commits_last_90d,
                "merged_prs_last_90_days": merged_prs_last_90d,
                "top_contributors":       top_contributors,
                "stats_sampled_repos":    len(repos_sample[:15]),
            })

            logger.info(
                "GitHub metadata: %d repos (%d public, %d private), "
                "%d workflows, %d commits/90d, %d merged PRs/90d",
                stats.get("total_repos", 0), stats.get("public_repos", 0),
                stats.get("private_repos", 0), total_workflows,
                commits_last_90d, merged_prs_last_90d,
            )
            return stats
        except Exception as exc:
            logger.warning("GitHub get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            from github import Github
            g = Github(os.getenv("GITHUB_TOKEN"))
            org_name = os.getenv("GITHUB_ORG")
            if org_name:
                try:
                    repos = list(g.get_organization(org_name).get_repos())[:100]
                    logger.info("GitHub: loaded %d repos from org '%s'", len(repos), org_name)
                except Exception as org_exc:
                    logger.warning(
                        "GitHub: org '%s' lookup failed (%s) — falling back to user repos",
                        org_name, org_exc,
                    )
                    findings.append(self._finding(
                        f"github/org/{org_name}", "MEDIUM", "security",
                        f"GitHub organisation '{org_name}' is not accessible with this token",
                        "Check GITHUB_ORG value and ensure the token has 'read:org' scope",
                    ))
                    org_name = None  # fall through to user repos below

            if not org_name:
                # get_repos() without type filter returns owned + member repos
                try:
                    repos = list(g.get_user().get_repos())[:50]
                except Exception:
                    # Fine-grained tokens may need authenticated user repos
                    repos = list(g.get_user().get_repos(affiliation="owner,collaborator"))[:50]

            if not repos:
                findings.append(self._finding(
                    "github/user", "INFO", "security",
                    "No repositories accessible with the provided token",
                    "Ensure the token has 'repo' scope (classic) or repository access (fine-grained)",
                ))
                return findings

            for repo in repos:
                findings += self._scan_repo(repo)
        except Exception as exc:
            logger.error("GitHub scan failed: %s", exc)
            findings.append(self._finding(
                "github/user", "HIGH", "security",
                f"GitHub scan failed: {exc}",
                "Verify the token has sufficient permissions (repo, read:org, security_events scopes)",
            ))
        return findings

    def _scan_repo(self, repo) -> list[dict]:
        findings = []
        resource = f"github/{repo.full_name}"
        try:
            # Public repo check
            if not repo.private:
                findings.append(self._finding(
                    resource, "INFO", "security",
                    f"Repository '{repo.full_name}' is public",
                    "Confirm this repository should be public; sensitive repos should be private",
                ))
            # Branch protection on default branch
            try:
                branch = repo.get_branch(repo.default_branch)
                if not branch.protected:
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        f"Default branch '{repo.default_branch}' has no branch protection rules",
                        "Enable branch protection: require PR reviews and status checks before merging",
                    ))
            except Exception:
                pass
            # Dependabot alerts — get_vulnerability_alert() returns bool (enabled/disabled)
            try:
                alerts_enabled = repo.get_vulnerability_alert()
                if not alerts_enabled and not repo.private:
                    findings.append(self._finding(
                        resource, "MEDIUM", "security",
                        f"Dependabot vulnerability alerts are disabled on '{repo.full_name}'",
                        "Enable Dependabot alerts in repository Security settings",
                    ))
            except Exception:
                pass
            # Secrets scanning (check if enabled)
            try:
                if not repo.private and not getattr(repo, "security_and_analysis", None):
                    findings.append(self._finding(
                        resource, "MEDIUM", "security",
                        "Secret scanning status could not be verified",
                        "Enable secret scanning and push protection in repository settings",
                    ))
            except Exception:
                pass
            # Stale repo (no commits in 6 months)
            from datetime import timezone, datetime, timedelta
            if repo.pushed_at and (datetime.now(timezone.utc) - repo.pushed_at) > timedelta(days=180):
                findings.append(self._finding(
                    resource, "LOW", "cost",
                    f"Repository '{repo.full_name}' has had no pushes in over 6 months",
                    "Archive or delete stale repositories to reduce maintenance overhead",
                    {"last_push": repo.pushed_at.isoformat()},
                ))
        except Exception as exc:
            logger.warning("GitHub repo scan error for %s: %s", repo.full_name, exc)
        return findings
