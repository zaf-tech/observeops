"""
POST /api/validate — test real connectivity for each platform before running a scan.
Returns per-platform status: ok | failed | skipped (no credentials).
READ-ONLY probes only — no writes.
"""
import logging
import os
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class ValidateRequest(BaseModel):
    credentials: dict[str, Any] = {}


class PlatformResult(BaseModel):
    platform: str
    status: str        # "ok" | "failed" | "skipped"
    message: str
    detail: str = ""


class ValidateResponse(BaseModel):
    results: list[PlatformResult]
    ready: bool        # True if at least one platform is "ok"


@router.post("/validate", response_model=ValidateResponse)
async def validate_credentials(request: ValidateRequest):
    """
    Inject credentials in-memory and run lightweight connectivity probes.
    Never persists credentials. Never modifies any resource.
    """
    # Inject supplied credentials into this request's env scope
    creds = {k: v for k, v in request.credentials.items() if v and str(v).strip()}
    saved = {}
    for k, v in creds.items():
        saved[k] = os.environ.get(k)
        os.environ[k] = str(v)

    results: list[PlatformResult] = []
    try:
        results = await _run_probes(creds)
    finally:
        # Restore original env values
        for k, original in saved.items():
            if original is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = original

    ready = any(r.status == "ok" for r in results)
    return ValidateResponse(results=results, ready=ready)


# ── Probes ───────────────────────────────────────────────────────────

async def _run_probes(creds: dict) -> list[PlatformResult]:
    import asyncio
    tasks = [
        _probe_aws(creds),
        _probe_azure(creds),
        _probe_gcp(creds),
        _probe_github(creds),
        _probe_gitlab(creds),
        _probe_jenkins(creds),
        _probe_sonarqube(creds),
        _probe_snyk(creds),
        _probe_argocd(creds),
        _probe_circleci(creds),
    ]
    return list(await asyncio.gather(*tasks))


async def _probe_aws(creds: dict) -> PlatformResult:
    if not (creds.get("AWS_ACCESS_KEY_ID") and creds.get("AWS_SECRET_ACCESS_KEY")):
        return PlatformResult(platform="aws", status="skipped", message="No credentials provided")
    try:
        import asyncio, boto3, botocore.exceptions
        def _call():
            sts = boto3.client(
                "sts",
                aws_access_key_id=creds["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=creds["AWS_SECRET_ACCESS_KEY"],
                region_name=creds.get("AWS_DEFAULT_REGION", "us-east-1"),
            )
            return sts.get_caller_identity()
        identity = await asyncio.to_thread(_call)
        return PlatformResult(
            platform="aws", status="ok",
            message=f"Connected — Account {identity.get('Account')}",
            detail=identity.get("Arn", ""),
        )
    except Exception as exc:
        return PlatformResult(platform="aws", status="failed", message="Connection failed", detail=str(exc)[:120])


async def _probe_azure(creds: dict) -> PlatformResult:
    required = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"]
    if not all(creds.get(k) for k in required):
        return PlatformResult(platform="azure", status="skipped", message="No credentials provided")
    try:
        import asyncio
        def _call():
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import SubscriptionClient
            cred = ClientSecretCredential(
                tenant_id=creds["AZURE_TENANT_ID"],
                client_id=creds["AZURE_CLIENT_ID"],
                client_secret=creds["AZURE_CLIENT_SECRET"],
            )
            sub_client = SubscriptionClient(cred)
            sub = sub_client.subscriptions.get(creds["AZURE_SUBSCRIPTION_ID"])
            return sub.display_name
        name = await asyncio.to_thread(_call)
        return PlatformResult(platform="azure", status="ok", message=f"Connected — {name}")
    except Exception as exc:
        return PlatformResult(platform="azure", status="failed", message="Connection failed", detail=str(exc)[:120])


async def _probe_gcp(creds: dict) -> PlatformResult:
    has_json = bool(creds.get("GCP_SERVICE_ACCOUNT_JSON"))
    has_file = bool(creds.get("GOOGLE_APPLICATION_CREDENTIALS") and creds.get("GCP_PROJECT_ID"))
    if not has_json and not has_file:
        return PlatformResult(platform="gcp", status="skipped", message="No credentials provided")
    try:
        import asyncio, json as _json
        def _call():
            from google.cloud import resourcemanager_v3
            if has_json:
                from google.oauth2 import service_account
                info = _json.loads(creds["GCP_SERVICE_ACCOUNT_JSON"])
                project_id = creds.get("GCP_PROJECT_ID") or info.get("project_id", "")
                sa_creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"],
                )
                client = resourcemanager_v3.ProjectsClient(credentials=sa_creds)
            else:
                project_id = creds["GCP_PROJECT_ID"]
                client = resourcemanager_v3.ProjectsClient()
            project = client.get_project(name=f"projects/{project_id}")
            return project.display_name or project_id, project_id
        name, pid = await asyncio.to_thread(_call)
        return PlatformResult(platform="gcp", status="ok", message=f"Connected — {name} ({pid})")
    except Exception as exc:
        return PlatformResult(platform="gcp", status="failed", message="Connection failed", detail=str(exc)[:120])


async def _probe_github(creds: dict) -> PlatformResult:
    if not creds.get("GITHUB_TOKEN"):
        return PlatformResult(platform="github", status="skipped", message="No token provided")
    try:
        import asyncio
        def _call():
            from github import Github, GithubException
            g = Github(creds["GITHUB_TOKEN"])
            user = g.get_user()
            return user.login
        login = await asyncio.to_thread(_call)
        return PlatformResult(platform="github", status="ok", message=f"Connected — @{login}")
    except Exception as exc:
        return PlatformResult(platform="github", status="failed", message="Invalid token", detail=str(exc)[:120])


async def _probe_gitlab(creds: dict) -> PlatformResult:
    if not creds.get("GITLAB_TOKEN"):
        return PlatformResult(platform="gitlab", status="skipped", message="No token provided")
    try:
        import asyncio
        def _call():
            import gitlab
            gl = gitlab.Gitlab(
                creds.get("GITLAB_URL", "https://gitlab.com"),
                private_token=creds["GITLAB_TOKEN"],
            )
            gl.auth()
            return gl.users.get(gl.user.id).username
        username = await asyncio.to_thread(_call)
        return PlatformResult(platform="gitlab", status="ok", message=f"Connected — @{username}")
    except Exception as exc:
        return PlatformResult(platform="gitlab", status="failed", message="Invalid token", detail=str(exc)[:120])


async def _probe_jenkins(creds: dict) -> PlatformResult:
    if not all(creds.get(k) for k in ["JENKINS_URL", "JENKINS_USER", "JENKINS_TOKEN"]):
        return PlatformResult(platform="jenkins", status="skipped", message="No credentials provided")
    try:
        import asyncio, requests
        from requests.auth import HTTPBasicAuth
        def _call():
            r = requests.get(
                f"{creds['JENKINS_URL'].rstrip('/')}/api/json",
                auth=HTTPBasicAuth(creds["JENKINS_USER"], creds["JENKINS_TOKEN"]),
                timeout=8,
            )
            r.raise_for_status()
            return r.json().get("nodeName", "Jenkins")
        name = await asyncio.to_thread(_call)
        return PlatformResult(platform="jenkins", status="ok", message=f"Connected — {name}")
    except Exception as exc:
        return PlatformResult(platform="jenkins", status="failed", message="Connection failed", detail=str(exc)[:120])


async def _probe_sonarqube(creds: dict) -> PlatformResult:
    if not creds.get("SONAR_TOKEN"):
        return PlatformResult(platform="sonarqube", status="skipped", message="No token provided")
    try:
        import asyncio, requests, base64
        def _call():
            token = creds["SONAR_TOKEN"]
            encoded = base64.b64encode(f"{token}:".encode()).decode()
            url = creds.get("SONAR_URL", "https://sonarcloud.io").rstrip("/")
            r = requests.get(
                f"{url}/api/system/status",
                headers={"Authorization": f"Basic {encoded}"},
                timeout=8,
            )
            r.raise_for_status()
            return r.json().get("status", "UP")
        status = await asyncio.to_thread(_call)
        return PlatformResult(platform="sonarqube", status="ok", message=f"Connected — status: {status}")
    except Exception as exc:
        return PlatformResult(platform="sonarqube", status="failed", message="Connection failed", detail=str(exc)[:120])


async def _probe_snyk(creds: dict) -> PlatformResult:
    if not creds.get("SNYK_TOKEN"):
        return PlatformResult(platform="snyk", status="skipped", message="No token provided")
    try:
        import asyncio, requests
        def _call():
            r = requests.get(
                "https://snyk.io/api/v1/user/me",
                headers={"Authorization": f"token {creds['SNYK_TOKEN']}"},
                timeout=8,
            )
            r.raise_for_status()
            return r.json().get("username", "user")
        username = await asyncio.to_thread(_call)
        return PlatformResult(platform="snyk", status="ok", message=f"Connected — @{username}")
    except Exception as exc:
        return PlatformResult(platform="snyk", status="failed", message="Invalid token", detail=str(exc)[:120])


async def _probe_argocd(creds: dict) -> PlatformResult:
    if not all(creds.get(k) for k in ["ARGOCD_URL", "ARGOCD_TOKEN"]):
        return PlatformResult(platform="argocd", status="skipped", message="No credentials provided")
    try:
        import asyncio, requests
        def _call():
            r = requests.get(
                f"{creds['ARGOCD_URL'].rstrip('/')}/api/v1/version",
                headers={"Authorization": f"Bearer {creds['ARGOCD_TOKEN']}"},
                timeout=8, verify=False,
            )
            r.raise_for_status()
            return r.json().get("Version", "unknown")
        version = await asyncio.to_thread(_call)
        return PlatformResult(platform="argocd", status="ok", message=f"Connected — ArgoCD {version}")
    except Exception as exc:
        return PlatformResult(platform="argocd", status="failed", message="Connection failed", detail=str(exc)[:120])


async def _probe_circleci(creds: dict) -> PlatformResult:
    if not creds.get("CIRCLECI_TOKEN"):
        return PlatformResult(platform="circleci", status="skipped", message="No token provided")
    try:
        import asyncio, requests
        def _call():
            r = requests.get(
                "https://circleci.com/api/v2/me",
                headers={"Circle-Token": creds["CIRCLECI_TOKEN"]},
                timeout=8,
            )
            r.raise_for_status()
            return r.json().get("login", "user")
        login = await asyncio.to_thread(_call)
        return PlatformResult(platform="circleci", status="ok", message=f"Connected — @{login}")
    except Exception as exc:
        return PlatformResult(platform="circleci", status="failed", message="Invalid token", detail=str(exc)[:120])
