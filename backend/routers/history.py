"""GET /api/reports — list all past audit jobs with their status and summary."""
import logging
import pathlib

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

REPORTS_DIR = pathlib.Path("reports")


@router.get("/reports")
async def list_reports():
    """Return all audit jobs sorted newest-first with status + finding counts."""
    import job_store
    jobs = job_store.list_jobs(limit=100)
    return {"jobs": jobs, "total": len(jobs)}


@router.delete("/reports/{job_id}")
async def delete_report(job_id: str):
    """Delete a report and its metadata from disk."""
    import job_store
    if not job_store.job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    deleted = []
    for suffix in [".json", ".meta.json", ".pdf"]:
        p = REPORTS_DIR / f"{job_id}{suffix}"
        if p.exists():
            p.unlink()
            deleted.append(str(p.name))

    return {"deleted": deleted}
