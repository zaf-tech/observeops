# Skill: scaffold-project

Bootstrap the full ObserverAI project structure from scratch.

## Trigger

Use when the user says `/scaffold-project`, "bootstrap the project", "set up the project structure", "create the base files", or "initialize observerops".

## Behavior

Generate the following files in order. Ask for confirmation before writing if the file already exists.

## Files to create

### 1. `base_plugin.py` — abstract base class
```python
"""Abstract base for all ObserverAI platform plugins."""
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    name: str = ""
    credential_keys: list[str] = []

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if all required credentials are present."""

    @abstractmethod
    def run_scan(self) -> list[dict]:
        """Return a list of Finding dicts. Never raises — returns [] on error."""

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return platform version/account info."""
```

### 2. `config.py` — LLM provider routing
```python
"""
LLM provider routing for ObserverAI.
Never hardcode model names in agent/plugin code — always call these helpers.

.env keys:
  SCAN_LLM=ollama          # ollama | bedrock-haiku
  REPORT_LLM=ollama        # ollama | sonnet
  OLLAMA_MODEL=llama3.2
  OLLAMA_BASE_URL=http://localhost:11434
"""
import os


def get_scan_llm():
    provider = os.getenv("SCAN_LLM", "ollama")
    return _build_llm(provider)


def get_report_llm():
    provider = os.getenv("REPORT_LLM", "ollama")
    return _build_llm(provider)


def _build_llm(provider: str):
    if provider == "ollama":
        from langchain_ollama import OllamaLLM
        return OllamaLLM(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    if provider == "bedrock-haiku":
        import boto3
        from langchain_aws import BedrockLLM
        return BedrockLLM(model_id=os.getenv("BEDROCK_HAIKU_MODEL_ID"), client=boto3.client("bedrock-runtime"))
    if provider == "sonnet":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("CLAUDE_MODEL_ID"), api_key=os.getenv("ANTHROPIC_API_KEY"))
    raise ValueError(f"Unknown LLM provider: {provider}")
```

### 3. `.env.example` — credential template
```
# ObserverAI — copy to .env and fill in values
# Only set the platforms you actually have

# ── AWS ──────────────────────────────────────
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

# ── LLM routing ──────────────────────────────
SCAN_LLM=ollama
REPORT_LLM=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
# ANTHROPIC_API_KEY=          # only needed if REPORT_LLM=sonnet
# CLAUDE_MODEL_ID=claude-sonnet-4-6
```

### 4. `requirements.txt`
```
# Core
python-dotenv

# Cloud
boto3
azure-identity
azure-mgmt-resource
google-cloud-resource-manager

# Code repos
PyGithub
python-gitlab
atlassian-python-api

# CI/CD
# (jenkins, argocd use plain requests)
requests

# Quality/security
# (sonarqube, snyk use plain requests)

# IaC
pyyaml

# LLM
langchain-ollama
langchain-aws
langchain-anthropic
```

### 5. `plugins/` directory — empty `__init__.py`

### 6. `run_audit.py` — entrypoint (see run-audit skill)

### 7. `synthesizer.py` — report generator (see synthesize-report skill)

## After scaffolding

Tell the user:
```
Project scaffolded. Next steps:
1. cp .env.example .env  →  fill in credentials for the platforms you have
2. pip install -r requirements.txt
3. Use /new-plugin to add platform plugins
4. python run_audit.py  →  runs all available plugins and prints the report
```
