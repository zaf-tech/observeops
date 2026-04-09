# ObserverAI — CLAUDE.md

## What we're building
A platform-agnostic, multi-agent infrastructure auditing system.
Read-only agents scan whatever platforms the client has, then
the Synthesizer produces a unified executive health report.

## Core design rule — PLUGIN SYSTEM, NOT HARDCODED PLATFORMS
Agents do NOT contain platform-specific code.
Platforms are PLUGINS that agents load dynamically based on
which credentials are detected in the environment.
Adding a new platform = adding a new plugin file. Zero agent changes.

## Plugin categories

### Cloud & Kubernetes
- aws_plugin.py       → boto3, covers EC2/S3/IAM/RDS/VPC/Lambda
- azure_plugin.py     → azure-sdk, covers AKS/ARM/Key Vault/Azure DevOps
- gcp_plugin.py       → google-cloud-sdk, covers GKE/GCS/IAM/Cloud Build
- openshift_plugin.py → kubernetes python client + OpenShift REST API
- eks_plugin.py       → boto3 EKS + kubeconfig
- aks_plugin.py       → azure-sdk AKS + kubeconfig
- gke_plugin.py       → google-cloud-container + kubeconfig
- cloudformation_plugin.py → boto3 CloudFormation template scanner

### Code & Artifact Repositories
- github_plugin.py       → PyGithub, scans repos/PRs/commits/Actions
- gitlab_plugin.py       → python-gitlab, repos + GitLab CI
- bitbucket_plugin.py    → atlassian-python-api
- artifactory_plugin.py  → jfrog REST API, artifact CVE scanning
- nexus_plugin.py        → Nexus REST API, package vulnerability check

### CI/CD Pipelines
- jenkins_plugin.py      → Jenkins REST API
- azure_devops_plugin.py → azure-devops SDK, pipelines + repos
- circleci_plugin.py     → CircleCI v2 REST API
- argocd_plugin.py       → ArgoCD REST API
- tekton_plugin.py       → Kubernetes CRD reads via k8s client

### Code Quality & Security
- sonarqube_plugin.py    → SonarQube/SonarCloud REST API
- snyk_plugin.py         → Snyk REST API (read findings only)

### Infrastructure as Code
- terraform_plugin.py    → parse .tfstate and .tf files (static analysis)
- helm_plugin.py         → parse Chart.yaml and values.yaml
- k8s_manifest_plugin.py → scan any Kubernetes YAML for misconfigs

## Plugin interface — every plugin MUST implement this
class BasePlugin:
    name: str                    # e.g. "aws", "sonarqube"
    credential_keys: list[str]   # env vars that signal this plugin is available
    
    def is_available(self) -> bool   # check if credentials exist
    def run_scan(self) -> list[dict] # return list of Finding dicts
    def get_metadata(self) -> dict   # platform version, account info etc.

## Finding format — every plugin returns this structure
{
  "platform": "aws",           # plugin name
  "resource": "s3://my-bucket",
  "severity": "CRITICAL",      # CRITICAL / HIGH / MEDIUM / LOW / INFO
  "category": "security",      # security / cost / reliability / performance / compliance
  "finding": "Bucket is publicly readable",
  "recommendation": "Enable Block Public Access settings",
  "evidence": {}               # raw data that supports the finding
}

## Agent structure (platform-agnostic)
- CloudAuditor    → loads all cloud + k8s plugins that are available
- CodeReviewer    → loads all code repo + artifact plugins available
- CICDGuard       → loads all CI/CD pipeline plugins available
- ArtifactInspector → loads Artifactory, Nexus, package plugins
- Synthesizer     → receives all findings, generates unified report

## LLM provider routing
- Scanning/parsing: Ollama llama3.2 (free, local)
- Analysis/reasoning: Bedrock Haiku (~$0.001/run)
- Final report: configurable (default Ollama, upgrade to Claude Sonnet for clients)
- NEVER hardcode model names in agent code — always use config.py

## Rules — never break these
1. ALL platform access is READ-ONLY. No write, delete, or modify operations ever.
2. Credentials come from .env only. Never hardcoded, never logged.
3. Each plugin must handle missing/invalid credentials gracefully.
4. Plugins return empty list [] if scan finds nothing — never crash.
5. The Synthesizer must work with ANY combination of plugin outputs.
6. Adding a platform = adding one plugin file only. No other files change.