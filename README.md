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
git clone https://github.com/zaf-tech/observeops.git
cd observeops

cp backend/.env.example backend/.env
```

### 2. Do not put any keys in `.env`

Use `backend/.env` only as a runtime environment file required by Docker Compose.
Enter **all credentials and API keys** in the browser UI during the audit session.

### 3. Build and run

```bash
docker compose up --build -d
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
# Do not put keys in .env

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

## How to run this program

Choose one of these modes:

### Mode A: Docker (fastest setup)

```bash
git clone https://github.com/your-org/observerops.git
cd observerops
cp backend/.env.example backend/.env
docker compose up --build
```

Do not place secrets in `.env`. All credentials are provided in the browser UI.

Then open:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

Stop services with:

```bash
docker compose down
```

### Mode B: Local development (separate backend + frontend)

Backend terminal:

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Frontend terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the app at http://localhost:3000.

### Mode C: Backend-only CLI run

```bash
cd backend
python run_audit.py
```

The CLI writes report JSON files to `backend/reports/`.

---

## How to use this program (API keys and credentials)

All credentials are entered in the browser and kept in-memory for the active audit run.

### 1) LLM provider API keys (entered in browser)

Enter only the key for the provider you select in **AI Model Routing**.

Supported providers include:

- Ollama (local; no API key)
- OpenAI
- Anthropic Claude
- Google Gemini
- DeepSeek
- AWS Bedrock
- Groq
- Mistral
- Azure OpenAI
- Cohere

### 2) Platform credentials (entered in browser)

Enter platform credentials in **Configure Platforms**.

Common credential fields include:

- AWS: access key, secret key, region
- Azure: tenant ID, client ID, client secret, subscription ID
- GCP: service account JSON path / project ID
- GitHub/GitLab/Bitbucket: tokens and org/workspace fields
- Jenkins/Azure DevOps/CircleCI/ArgoCD: URL + token credentials
- Sonar/Snyk/Artifactory/Nexus: server URL and token/user credentials

### 3) Security note

Do not commit secrets to the repository. Keep `.env` free of API keys.

### Typical usage flow

1. Start backend and frontend (Docker or local).
2. Open http://localhost:3000.
3. Add platform credentials in **Configure Platforms**.
4. Select scan model and report model.
5. Click **Generate Audit Report**.
6. Monitor progress in the live log.
7. Read the report and download PDF if needed.

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
| Gemini Flash-Lite | Fast low-cost scanning | Gemini API key entered in browser |
| DeepSeek V3 | High quality, low cost | DeepSeek API key entered in browser |
| AWS Bedrock Haiku | AWS-native deployments | AWS credentials in UI |
| Claude Sonnet | Best executive reports | Anthropic API key entered in browser |

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
- **LLM and platform keys** — all keys are provided in UI for the active run; do not store secrets in `.env`

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
## Contributors

Thanks to all contributors who support this project.

- [Talha Jilal](https://github.com/talhajilal)

## License

MIT © [ZafTech](https://zaftech.ca)
