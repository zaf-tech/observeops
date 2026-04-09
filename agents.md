# ObserveOps — Agents & LLM Architecture

## Where Agents Are Stored

Agents (the orchestrating skills) live in `backend/agents/`. Each agent is a single Python file that coordinates one phase of the audit. Agents contain **no platform-specific code** — they load plugins dynamically at runtime based on which credentials are detected in the environment.

| File | Skill | Role |
|------|-------|------|
| `cloud_auditor.py`    | Skill 1 | Loads AWS / Azure / GCP / Kubernetes plugins and runs cloud infrastructure scans |
| `log_analyst.py`      | Skill 2 | Parses CloudWatch, syslog, and application log files for anomalies |
| `security_auditor.py` | Skill 3 | Audits IAM roles, open ports, secret scanning, and compliance controls |
| `cicd_guard.py`       | Skill 4 | Scans Jenkins, ArgoCD, CircleCI, GitHub Actions, and Azure DevOps pipelines |
| `code_reviewer.py`    | Skill 5 | Reviews GitHub, GitLab, SonarQube, and Snyk for code quality and CVEs |
| `report_synthesizer.py` | Skill 6 | Aggregates all findings and generates the executive report via LLM |

---

## Where Plugins Are Stored

Plugins (platform-specific scan logic) live in `backend/plugins/`. Each file handles one platform. To add a new platform, you only ever add one plugin file — no agent code changes.

### Cloud & Kubernetes
| Plugin | Covers |
|--------|--------|
| `aws_plugin.py` | EC2, S3, IAM, RDS, VPC, Lambda |
| `azure_plugin.py` | AKS, ARM, Key Vault, Azure DevOps |
| `gcp_plugin.py` | GKE, GCS, IAM, Cloud Build |
| `eks_plugin.py` | EKS + kubeconfig |
| `aks_plugin.py` | Azure AKS + kubeconfig |
| `gke_plugin.py` | Google GKE + kubeconfig |
| `cloudformation_plugin.py` | CloudFormation template scanner |

### Code & Artifact Repositories
| Plugin | Covers |
|--------|--------|
| `github_plugin.py` | Repos, branch protection, Dependabot, GitHub Actions |
| `gitlab_plugin.py` | Repos, GitLab CI pipelines |
| `bitbucket_plugin.py` | Repos and pipelines |
| `artifactory_plugin.py` | JFrog artifact CVE scanning |
| `nexus_plugin.py` | Nexus package vulnerability check |

### CI/CD Pipelines
| Plugin | Covers |
|--------|--------|
| `jenkins_plugin.py` | Jenkins REST API |
| `azure_devops_plugin.py` | Pipelines and repos |
| `circleci_plugin.py` | CircleCI v2 REST API |
| `argocd_plugin.py` | ArgoCD REST API |
| `tekton_plugin.py` | Kubernetes CRD reads |

### Code Quality & Security
| Plugin | Covers |
|--------|--------|
| `sonarqube_plugin.py` | SonarQube / SonarCloud REST API |
| `snyk_plugin.py` | Snyk REST API (read findings only) |

### Infrastructure as Code
| Plugin | Covers |
|--------|--------|
| `terraform_plugin.py` | `.tfstate` and `.tf` file static analysis |
| `helm_plugin.py` | `Chart.yaml` and `values.yaml` parsing |
| `k8s_manifest_plugin.py` | Kubernetes YAML misconfiguration scanning |

---

## How Findings Are Stored

Every plugin returns a list of **Finding dicts** using this standard schema:

```python
{
  "platform":       "github",             # plugin name
  "resource":       "github/my-org/repo", # specific resource scanned
  "severity":       "HIGH",               # CRITICAL | HIGH | MEDIUM | LOW | INFO
  "category":       "security",           # security | cost | reliability | performance | compliance
  "finding":        "Default branch has no branch protection rules",
  "recommendation": "Enable branch protection: require PR reviews and status checks",
  "evidence":       {}                    # raw supporting data from the API
}
```

Completed scan results are persisted as JSON at `backend/reports/<job_id>.json`. Each file contains:
- `markdown` — the AI-generated report text
- `summary` — counts by severity, platform, and category
- `findings` — the full list of finding dicts
- `plugin_audit` — which plugins ran vs. were skipped
- `platform_stats` — live statistics collected during the scan (repo counts, commit activity, etc.)

---

## LLM Report Generation (Skill 6)

### Does the program use an LLM?

Yes. Skill 6 (`ReportSynthesizer`) invokes a configurable LLM to write the executive report. The LLM provider is selected per-scan via the **Report Model** dropdown in the UI. Supported providers:

| Provider | Notes |
|----------|-------|
| Ollama (local) | Default. Requires Ollama running on the host at `http://host.docker.internal:11434` |
| OpenAI | Requires API key; default model `gpt-4o-mini` |
| Anthropic Claude | Claude Sonnet — best report quality |
| Google Gemini | Requires Google API key |
| AWS Bedrock | Haiku model — low cost per scan |
| Groq | Fast inference, free tier available |
| Mistral AI | European-hosted LLM |
| DeepSeek | Low cost alternative |
| Azure OpenAI | Enterprise deployments |
| Cohere | Command R model |

LLM provider routing is configured in `backend/config.py`. Model names are never hardcoded in agent code.

### Fallback behaviour

If the LLM call fails or returns fewer than 100 characters, `ReportSynthesizer` logs:

```
ReportSynthesizer: LLM invocation failed — falling back to structured template.
```

and produces a plain structured template report instead of an AI-written narrative.

---

## LLM Prompt Structure

The prompt sent to the LLM is built in `backend/agents/report_synthesizer.py` → `_build_prompt()`. It has the following structure:

```
You are a senior cloud security consultant writing an executive
infrastructure audit report for a CTO/CISO audience.

SCAN RESULTS:
- Platforms scanned: github
- Total findings: 12
- CRITICAL: 0 | HIGH: 3 | MEDIUM: 6 | LOW: 2 | INFO: 1

PLATFORM STATISTICS (collected live during scan):
[GITHUB]
  login: my-username
  total_repos: 37 (12 public, 25 private)
  repos_with_actions: 8
  total_workflows: 14
  commits_last_90_days: 203
  merged_prs_last_90_days: 41
  top_contributors: @alice (87), @bob (54), @carol (31)

ADDITIONAL REQUIREMENTS FROM CLIENT:        ← user's Custom Instructions box
  Include estimated billing forecast for next month.
  Highlight all IAM roles with admin privileges.

FINDINGS (JSON):
[ top 15 CRITICAL + HIGH findings ]
[ top 10 MEDIUM + LOW findings ]

Write a professional executive report in Markdown with these sections:

## Platform Overview
  For each platform: what was found (with real counts from statistics above),
  overall health status, standout observations.

## Executive Summary
  2-3 sentences summarising overall security posture and most critical risks.

## Critical & High Priority Issues
  What was found, why it matters, specific remediation step.

## Medium & Low Priority Issues
  Grouped by platform. Brief description and fix.

## Risk Breakdown Table
  | Platform | Critical | High | Medium | Low | Total |

## Recommended Action Plan
  Top 5-10 remediation actions ordered by risk.
  Address any additional client requirements here.

## Positive Observations
  Platforms or controls that appear well-configured.
```

### Rules enforced in the prompt

- Be specific — use actual resource names from the findings
- Use professional security language
- Keep recommendations actionable and concrete
- Do NOT include generic boilerplate — only reference what was actually found
- Integrate any custom client requirements naturally into relevant sections

---

## Orchestration Flow

```
Browser UI
    │  credentials + LLM config + custom instructions
    ▼
POST /api/analyze
    │
    ▼
synthesizer.py → run_audit()
    ├── _apply_credentials()   wipe all known env vars, inject this scan's creds only
    │
    ├── Skill 1  CloudAuditor     → cloud + k8s plugins
    ├── Skill 2  LogAnalyst       → log file plugins
    ├── Skill 3  SecurityAuditor  → security plugins
    ├── Skill 4  CICDGuard        → CI/CD pipeline plugins
    ├── Skill 5  CodeReviewer     → code repo + quality plugins
    │
    ├── platform stats collection (get_metadata() on all active plugins)
    │
    ├── Skill 6  ReportSynthesizer
    │       ├── _build_prompt(findings, summary, platform_stats, custom_instructions)
    │       ├── llm.invoke(prompt)         ← LLM call
    │       ├── _extract_llm_text(result)  ← handles AIMessage / plain string
    │       └── _format_report(llm_text)  or fallback _template_report()
    │
    ├── _save_report()  → reports/<job_id>.json
    └── _restore_credentials()  ← always runs, even on crash
```

---

## Adding a New Platform

1. Create `backend/plugins/<platform>_plugin.py`
2. Implement `BasePlugin`: `name`, `credential_keys`, `is_available()`, `run_scan()`, `get_metadata()`
3. Add the credential env var names to `_ALL_CREDENTIAL_KEYS` in `backend/synthesizer.py`
4. Add the platform to the UI credential panel in `frontend/components/CredentialPanel.tsx`

No agent files need to change.
