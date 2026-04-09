# ObserveOps — Master Build Specification
> Single source of truth. Synthesized from CLAUDE.md + full_instructions.md + Phase 1–4.
> Use this file to generate the entire application top-to-bottom.

---

## 1. What We Are Building

**ObserveOps** — a platform-agnostic, multi-agent infrastructure auditing system.
- Read-only agents scan whatever platforms the client has configured
- A Synthesizer agent aggregates all findings into a prioritized executive report
- A Next.js dashboard lets users enter credentials, trigger scans, and download reports

---

## 2. Non-Negotiable Rules

1. **READ-ONLY IMMUTABILITY** — No code may ever perform write, delete, or modify operations on any cloud resource or repository.
2. **KEY SECURITY** — API keys/credentials live in `.env` (backend) or in-memory only (frontend form state). Never log them, persist them to a database, or include them in any response body.
3. **PLUGIN ISOLATION** — Agents contain zero platform-specific code. Each platform is a plugin loaded dynamically based on detected credentials. Adding a platform = one new plugin file, zero agent changes.
4. **MODULARITY** — Each Skill/Agent is a standalone Python module testable in isolation.
5. **COST EFFICIENCY** — Use the smallest viable model for scanning; reserve high-reasoning models for the final synthesis step only.
6. **GRACEFUL DEGRADATION** — Every plugin returns `[]` on error; the system runs with whatever plugins are available.

---

## 3. Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15+, Tailwind CSS, Lucide Icons |
| Backend | Python 3.12+, FastAPI, Uvicorn |
| AI Orchestration | CrewAI / LangGraph (multi-agent swarm) |
| Scan LLMs | Gemini 2.0 Flash-Lite or DeepSeek V3 (low-cost) |
| Synthesis LLM | Claude Sonnet (configurable via env) |
| Local LLM | Ollama llama3.2 (default / offline mode) |
| Cloud SDKs | boto3, azure-sdk, google-cloud-sdk, PyGithub, python-gitlab |

---

## 4. Directory Structure

```
observerops/
├── frontend/                     # Next.js 15 app  (port 3000)
│   ├── app/
│   │   ├── page.tsx              # Connection Dashboard (tabs: AWS / Azure / GCP / GitHub / ...)
│   │   ├── report/page.tsx       # Report viewer + PDF download
│   │   └── layout.tsx
│   ├── components/
│   │   ├── CredentialPanel.tsx   # Per-platform credential input form
│   │   ├── LLMSelector.tsx       # OpenAI / Ollama / Bedrock selector
│   │   ├── StatusLog.tsx         # Real-time skill progress log
│   │   └── ReportViewer.tsx      # Markdown renderer + PDF export button
│   ├── lib/
│   │   └── api.ts                # fetch wrapper for /api/* endpoints
│   └── tailwind.config.ts
│
├── backend/                      # FastAPI app  (port 8000)
│   ├── main.py                   # App entrypoint, CORS, router registration
│   ├── config.py                 # LLM provider routing (never hardcode model names)
│   ├── base_plugin.py            # Abstract BasePlugin class
│   ├── run_audit.py              # CLI entrypoint: discover + execute available plugins
│   ├── synthesizer.py            # Skill 6: aggregates findings → executive report
│   │
│   ├── agents/                   # The 6 Agentic Skills (platform-agnostic)
│   │   ├── cloud_auditor.py      # Skill 1: loads all cloud + k8s plugins
│   │   ├── log_analyst.py        # Skill 2: parses logs, summarizes anomalies
│   │   ├── security_auditor.py   # Skill 3: IAM, open ports, secret scanning
│   │   ├── cicd_guard.py         # Skill 4: loads all CI/CD plugins
│   │   ├── code_reviewer.py      # Skill 5: loads all code repo + artifact plugins
│   │   └── report_synthesizer.py # Skill 6: calls synthesizer.py, exports PDF/MD
│   │
│   ├── plugins/                  # One file per platform — zero agent changes needed
│   │   ├── __init__.py
│   │   │
│   │   # Cloud & Kubernetes
│   │   ├── aws_plugin.py         # boto3 → EC2/S3/IAM/RDS/VPC/Lambda
│   │   ├── azure_plugin.py       # azure-sdk → AKS/ARM/Key Vault
│   │   ├── gcp_plugin.py         # google-cloud-sdk → GKE/GCS/IAM/Cloud Build
│   │   ├── openshift_plugin.py   # k8s client + OpenShift REST
│   │   ├── eks_plugin.py         # boto3 EKS + kubeconfig
│   │   ├── aks_plugin.py         # azure-sdk AKS + kubeconfig
│   │   ├── gke_plugin.py         # google-cloud-container + kubeconfig
│   │   ├── cloudformation_plugin.py  # boto3 CloudFormation template scanner
│   │   │
│   │   # Code & Artifact Repositories
│   │   ├── github_plugin.py      # PyGithub → repos/PRs/commits/Actions
│   │   ├── gitlab_plugin.py      # python-gitlab → repos + GitLab CI
│   │   ├── bitbucket_plugin.py   # atlassian-python-api
│   │   ├── artifactory_plugin.py # jFrog REST → artifact CVE scanning
│   │   ├── nexus_plugin.py       # Nexus REST → package vulnerability check
│   │   │
│   │   # CI/CD Pipelines
│   │   ├── jenkins_plugin.py     # Jenkins REST API
│   │   ├── azure_devops_plugin.py # azure-devops SDK
│   │   ├── circleci_plugin.py    # CircleCI v2 REST
│   │   ├── argocd_plugin.py      # ArgoCD REST
│   │   ├── tekton_plugin.py      # Kubernetes CRD reads
│   │   │
│   │   # Code Quality & Security
│   │   ├── sonarqube_plugin.py   # SonarQube/SonarCloud REST
│   │   ├── snyk_plugin.py        # Snyk REST (read findings only)
│   │   │
│   │   # Infrastructure as Code
│   │   ├── terraform_plugin.py   # parse .tfstate + .tf (static analysis)
│   │   ├── helm_plugin.py        # parse Chart.yaml + values.yaml
│   │   └── k8s_manifest_plugin.py # scan Kubernetes YAML for misconfigs
│   │
│   ├── routers/
│   │   ├── analyze.py            # POST /api/analyze
│   │   ├── status.py             # GET  /api/status/{job_id}  (SSE stream)
│   │   └── report.py             # GET  /api/report/{job_id}  (MD + PDF)
│   │
│   ├── reports/                  # Generated MD/PDF output files (gitignored)
│   ├── requirements.txt
│   └── .env.example
│
├── BUILD_SPEC.md                 # ← this file
└── CLAUDE.md                     # project rules (checked in)
```

---

## 5. Plugin Interface (Every Plugin MUST Implement)

```python
# backend/base_plugin.py
from abc import ABC, abstractmethod

class BasePlugin(ABC):
    name: str = ""                   # e.g. "aws", "sonarqube"
    credential_keys: list[str] = []  # env vars that activate this plugin

    @abstractmethod
    def is_available(self) -> bool:
        """Return True only if ALL credential_keys exist in env."""

    @abstractmethod
    def run_scan(self) -> list[dict]:
        """Return list of Finding dicts. NEVER raises — returns [] on any error."""

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return platform version, account/org/region info."""
```

---

## 6. Finding Format (Every Plugin Returns This Schema)

```python
{
    "platform":       str,   # plugin name, e.g. "aws"
    "resource":       str,   # unique resource identifier, e.g. "s3://my-bucket"
    "severity":       str,   # CRITICAL | HIGH | MEDIUM | LOW | INFO
    "category":       str,   # security | cost | reliability | performance | compliance
    "finding":        str,   # short human-readable description
    "recommendation": str,   # actionable fix
    "evidence":       dict,  # raw API data supporting the finding
}
```

---

## 7. The 6 Agentic Skills

| # | Agent Class | Loads Plugins | Purpose |
|---|-------------|--------------|---------|
| 1 | `CloudAuditor` | all cloud + k8s plugins | Orphaned assets, idle VMs, cost waste, misconfigs |
| 2 | `LogAnalyst` | (file/CloudWatch/Stackdriver) | Parse logs, summarize anomalies in plain English |
| 3 | `SecurityAuditor` | cloud IAM + code repo plugins | Open ports, over-privileged IAM, hardcoded secrets |
| 4 | `CICDGuard` | all CI/CD plugins | Pipeline health, failed builds, risky job configs |
| 5 | `CodeReviewer` | code repo + artifact plugins | Quality, CVEs, test coverage, dependency drift |
| 6 | `ReportSynthesizer` | (receives all findings) | Executive MD/PDF report, prioritized by severity |

---

## 8. LLM Provider Routing (config.py — never hardcode model names)

```python
# backend/config.py
import os

def get_scan_llm():
    """Low-cost model for Skills 1-5."""
    provider = os.getenv("SCAN_LLM", "ollama")
    return _build_llm(provider)

def get_report_llm():
    """High-reasoning model for Skill 6 synthesis."""
    provider = os.getenv("REPORT_LLM", "ollama")
    return _build_llm(provider)

def _build_llm(provider: str):
    if provider == "ollama":
        from langchain_ollama import OllamaLLM
        return OllamaLLM(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
    if provider == "bedrock-haiku":
        import boto3
        from langchain_aws import BedrockLLM
        return BedrockLLM(
            model_id=os.getenv("BEDROCK_HAIKU_MODEL_ID"),
            client=boto3.client("bedrock-runtime"),
        )
    if provider == "sonnet":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("CLAUDE_MODEL_ID", "claude-sonnet-4-6"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    raise ValueError(f"Unknown LLM provider: {provider}")
```

---

## 9. FastAPI Backend — Key Endpoints

```
POST /api/analyze
  Body: { credentials: {...}, llm_provider: "ollama"|"gemini"|"sonnet", ... }
  Returns: { job_id: "uuid" }
  Action: validates credentials in-memory, fires agent swarm as background task

GET  /api/status/{job_id}           (Server-Sent Events)
  Stream: skill progress events → { skill: "CloudAuditor", status: "running"|"done", findings_count: N }

GET  /api/report/{job_id}
  Returns: { markdown: "...", pdf_url: "/api/report/{job_id}/pdf" }

GET  /api/report/{job_id}/pdf
  Returns: application/pdf download
```

---

## 10. Frontend — Key Components

### Connection Dashboard (`app/page.tsx`)
- Tab bar: AWS | Azure | GCP | GitHub | GitLab | Jenkins | SonarQube | ...
- Each tab renders `<CredentialPanel platform="aws" />` with the right input fields
- LLM selector: Ollama (local) / Gemini Flash / DeepSeek / Claude Sonnet
- **"Generate Report"** button: POST to `/api/analyze`, store `job_id`

### Status Log (`components/StatusLog.tsx`)
- Opens SSE connection to `/api/status/{job_id}`
- Displays real-time lines: `✓ CloudAuditor — 14 findings` / `⟳ SecurityAuditor running...`

### Report Viewer (`app/report/page.tsx`)
- Fetches `/api/report/{job_id}`
- Renders Markdown with severity badges (CRITICAL=red, HIGH=orange, ...)
- **"Download PDF"** button hits `/api/report/{job_id}/pdf`

---

## 11. Credential Env Template (`.env.example`)

```bash
# ── LLM Routing ─────────────────────────────
SCAN_LLM=ollama               # ollama | gemini | deepseek | bedrock-haiku
REPORT_LLM=ollama             # ollama | sonnet
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
ANTHROPIC_API_KEY=
CLAUDE_MODEL_ID=claude-sonnet-4-6
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.0-flash-lite
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat

# ── AWS ─────────────────────────────────────
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# ── Azure ────────────────────────────────────
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_SUBSCRIPTION_ID=

# ── GCP ──────────────────────────────────────
GOOGLE_APPLICATION_CREDENTIALS=

# ── GitHub ───────────────────────────────────
GITHUB_TOKEN=

# ── GitLab ───────────────────────────────────
GITLAB_TOKEN=
GITLAB_URL=https://gitlab.com

# ── SonarQube ────────────────────────────────
SONAR_TOKEN=
SONAR_URL=https://sonarcloud.io

# ── Snyk ─────────────────────────────────────
SNYK_TOKEN=

# ── Jenkins ──────────────────────────────────
JENKINS_URL=
JENKINS_USER=
JENKINS_TOKEN=
```

---

## 12. Build Order (Phase-by-Phase)

### Phase 1 — Foundation
1. `backend/base_plugin.py` — BasePlugin ABC
2. `backend/config.py` — LLM routing
3. `backend/main.py` — FastAPI app with CORS, health check `GET /`
4. `backend/requirements.txt`
5. `frontend/` — Next.js init with Tailwind
6. Verify: `GET http://localhost:8000/` ↔ `http://localhost:3000/` handshake

### Phase 2 — Backend Skeleton
1. `backend/plugins/__init__.py` + plugin discovery utility
2. `backend/agents/cloud_auditor.py` — mock version scanning AWS S3 + Azure Resource Groups
3. `backend/routers/analyze.py` — `POST /api/analyze` returns `{ job_id }`
4. `backend/routers/status.py` — SSE stream of skill progress
5. Tests: `pytest backend/`

### Phase 3 — Frontend & Keys
1. `frontend/components/CredentialPanel.tsx`
2. `frontend/components/LLMSelector.tsx`
3. `frontend/app/page.tsx` — Connection Dashboard with tabs
4. `frontend/components/StatusLog.tsx` — SSE consumer
5. Wire **Generate Report** button → `/api/analyze`

### Phase 4 — Real Agent Skills
Build each skill in order, one at a time:
1. **Skill 1** `cloud_auditor.py` — real AWS/Azure/GCP plugins
2. **Skill 3** `security_auditor.py` — IAM audit + secret scanning
3. **Skill 4** `cicd_guard.py` — GitHub Actions + Jenkins
4. **Skill 5** `code_reviewer.py` — repo quality + CVEs
5. **Skill 2** `log_analyst.py` — CloudWatch / file logs
6. **Skill 6** `report_synthesizer.py` — LLM synthesis → MD + PDF export

### Phase 5 — Polish
1. PDF export (`reportlab` or `weasyprint`)
2. `frontend/app/report/page.tsx` — Markdown viewer + PDF download
3. Docker Compose (`frontend` + `backend` services)
4. End-to-end test with mock credentials

---

## 13. Essential Commands

```bash
# Install
npm install --prefix frontend
pip install -r backend/requirements.txt

# Run
npm run dev --prefix frontend          # http://localhost:3000
uvicorn main:app --reload --app-dir backend  # http://localhost:8000

# Test
pytest backend/

# Lint plugin
# use /validate-plugin skill in Claude Code
```

---

## 14. Generation Instructions for Claude

When building any component, follow this sequence:

1. **PLAN** — state what you will build and which file(s) will change. Stop.
2. **SECURITY CHECK** — confirm no write ops, no hardcoded credentials.
3. **BUILD** — generate exactly the files listed in the plan, one at a time.
4. **STATUS** — every long-running operation emits progress events the frontend can consume.

**Never** generate code that:
- Writes, deletes, or modifies any cloud resource
- Logs or returns credentials in any response
- Hardcodes model names (always call `config.get_scan_llm()` / `config.get_report_llm()`)
- Puts platform-specific logic inside an agent class
- Crashes instead of returning `[]`
