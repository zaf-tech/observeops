"""POST /api/analyze — accepts credentials, fires audit swarm as background task."""
import uuid
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    credentials: dict[str, Any] = {}
    llm_provider: str = "ollama"
    report_llm: str = "ollama"
    llm_config: dict[str, Any] = {}   # {"scan": {...}, "report": {...}}
    custom_instructions: str = ""     # optional user-supplied report guidance


class AnalyzeResponse(BaseModel):
    job_id: str
    message: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Accepts credentials + LLM choice in-memory (never persisted) and starts the audit swarm.
    Returns a job_id to poll /api/status/{job_id} for SSE progress.
    """
    import job_store

    job_id = str(uuid.uuid4())
    platforms = [k.split("_")[0].lower() for k, v in request.credentials.items() if v]

    job_store.create_job(job_id, request.llm_provider, request.report_llm, platforms)

    def progress_cb(skill: str, status: str, count: int):
        event = {"skill": skill, "status": status, "findings_count": count}
        job_store.push_event(job_id, event)
        logger.info("Job %s | %s → %s (%d findings)", job_id, skill, status, count)

    background_tasks.add_task(
        _run_audit_task,
        job_id,
        dict(request.credentials),
        request.llm_provider,
        request.report_llm,
        dict(request.llm_config),
        request.custom_instructions,
        progress_cb,
    )

    return AnalyzeResponse(job_id=job_id, message="Audit started")


async def _run_audit_task(
    job_id: str,
    credentials: dict,
    scan_llm: str,
    report_llm: str,
    llm_config: dict,
    custom_instructions: str,
    progress_cb,
):
    import job_store
    try:
        from synthesizer import run_audit
        await run_audit(job_id, credentials, scan_llm, report_llm, llm_config, custom_instructions, progress_cb)
    except Exception as exc:
        logger.error("Audit task failed for job %s: %s", job_id, exc)
        job_store.fail_job(job_id, str(exc))


# ── Accessors used by status + report routers ─────────────────────

def get_job_events(job_id: str) -> list[dict]:
    import job_store
    return job_store.get_events(job_id)


def is_job_done(job_id: str) -> bool:
    import job_store
    return job_store.is_done(job_id)


def job_exists(job_id: str) -> bool:
    import job_store
    return job_store.job_exists(job_id)
