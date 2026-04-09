# ObserveOps — Agentic Infrastructure Auditor

> Built by [ZafTech](https://zaftech.ca) · Read-only · Multi-agent · Platform-agnostic

A multi-agent AI system that audits your cloud infrastructure, CI/CD pipelines, and code repositories, then generates a prioritized executive security report — all without ever writing to or modifying your resources.

---

## How it works

Six specialized AI agents run in sequence:

| # | Agent | What it scans |
|---|-------|--------------|
| 1 | **Cloud Auditor** | AWS, Azure, GCP, EKS, AKS, GKE, CloudFormation |
| 2 | **Log Analyst** | CloudWatch, syslog, application logs |
| 3 | **Security Auditor** | IAM policies, open ports, hardcoded secrets |
| 4 | **CI/CD Guard** | Jenkins, GitHub Actions, ArgoCD, CircleCI, Azure DevOps |
| 5 | **Code Reviewer** | SonarQube, Snyk, Dependabot, Artifactory, Nexus |
| 6 | **Report Synthesizer** | Aggregates all findings → executive PDF/Markdown report |

Platform credentials are entered in the browser and held **in-memory only** — never stored, never logged.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, Tailwind CSS, Lucide Icons |
| Backend | Python 3.12, FastAPI, Uvicorn |
| AI Models | Ollama (local) · Gemini Flash · DeepSeek · Claude Sonnet (UI-selectable) |
| PDF Export | WeasyPrint / ReportLab |
| Container | Docker + Docker Compose |

---

## Quick start — Docker (recommended)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/observerops.git
cd observerops

cp backend/.env.example backend/.env
```

### 2. Edit `backend/.env` — add only the API keys for LLMs you want to use

```bash
# Ollama (local, free) — no key needed, just set model
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Anthropic — only if you pick "Claude Sonnet" in the UI
ANTHROPIC_API_KEY=sk-ant-...

# Google — only if you pick "Gemini Flash-Lite" in the UI
GOOGLE_API_KEY=AIza...

# DeepSeek — only if you pick "DeepSeek V3" in the UI
DEEPSEEK_API_KEY=...
```

> **Platform credentials (AWS, Azure, GitHub, etc.) are entered in the web UI — do NOT put them in `.env`.**

### 3. Build and run

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend dashboard | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

### 4. Stop

```bash
docker compose down
```

---

## Quick start — Local development

### Prerequisites

- Python 3.12+
- Node.js 20+
- (Optional) [Ollama](https://ollama.com) for local LLM

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — add LLM API keys only

uvicorn main:app --reload
# Running at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Running at http://localhost:3000
```

### Run audit from CLI (no frontend needed)

```bash
cd backend
python run_audit.py
# Prints the full report to stdout and saves to backend/reports/
```

---

## Using the dashboard

1. Open **http://localhost:3000**
2. **Configure Platforms** — expand any platform accordion and enter its credentials
3. **AI Model Routing** — pick your scan model and report model from the dropdowns
4. Click **Generate Audit Report**
5. Watch the real-time skill progress log
6. When complete, read the report inline or click **Download PDF**

### LLM provider guide

| Provider | Best for | Requires |
|----------|----------|---------|
| Ollama (local) | Privacy, free, offline | Ollama running locally |
| Gemini Flash-Lite | Fast low-cost scanning | `GOOGLE_API_KEY` in `.env` |
| DeepSeek V3 | High quality, low cost | `DEEPSEEK_API_KEY` in `.env` |
| AWS Bedrock Haiku | AWS-native deployments | AWS credentials in UI |
| Claude Sonnet | Best executive reports | `ANTHROPIC_API_KEY` in `.env` |

**Recommended combination:** Gemini Flash-Lite for scanning + Claude Sonnet for the final report.

---

## Supported platforms

### Cloud & Kubernetes
`AWS` `Azure` `GCP` `EKS` `AKS` `GKE` `CloudFormation`

### Code Repositories
`GitHub` `GitLab` `Bitbucket`

### CI/CD Pipelines
`Jenkins` `Azure DevOps` `CircleCI` `ArgoCD`

### Code Quality & Security
`SonarQube` `SonarCloud` `Snyk` `Artifactory` `Nexus`

### Infrastructure as Code
`Terraform` `Helm` `Kubernetes YAML`

---

## API reference

```
GET  /                          Health check
GET  /api/plugins               List all plugins + availability status
POST /api/analyze               Start an audit — returns { job_id }
GET  /api/status/{job_id}       SSE stream of skill progress
GET  /api/report/{job_id}       Full report as JSON
GET  /api/report/{job_id}/pdf   Download PDF report
```

Full interactive docs at **http://localhost:8000/docs**

---

## Running tests

```bash
cd backend
pytest tests/ -v
```

---

## Adding a new platform

1. Create `backend/plugins/{name}_plugin.py` inheriting `BasePlugin`
2. Implement `is_available()`, `run_scan()`, `get_metadata()`
3. Add the module path to `_PLUGIN_MODULES` in `backend/plugins/__init__.py`
4. Add credential fields to `frontend/components/CredentialPanel.tsx`

No agent files change. See `.claude/skills/new-plugin/` for the full template.

---

## Security guarantees

- **Read-only** — no plugin ever writes, deletes, or modifies any resource
- **In-memory credentials** — platform keys entered in the UI are never written to disk or logs
- **No credential persistence** — each scan gets a fresh in-memory credential set; they are discarded when the request ends
- **LLM API keys** — only LLM provider keys live in `.env`; all cloud/repo credentials come from the UI

---

## Project structure

```
observerops/
├── backend/
│   ├── agents/          # 6 platform-agnostic AI skills
│   ├── plugins/         # 1 file per platform (21 plugins)
│   ├── routers/         # FastAPI route handlers
│   ├── base_plugin.py   # Abstract plugin interface
│   ├── config.py        # LLM provider routing
│   ├── synthesizer.py   # Audit orchestrator
│   └── main.py          # FastAPI app entrypoint
├── frontend/
│   ├── app/             # Next.js pages
│   └── components/      # UI components
├── docker-compose.yml
└── BUILD_SPEC.md        # Full technical specification
```

---

## License

MIT © [ZafTech](https://zaftech.ca)
