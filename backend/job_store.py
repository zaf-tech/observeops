"""
Persistent job store — writes one .meta.json per job to disk.
Survives page refreshes and container restarts.
In-memory events are kept for the SSE stream during active scans.
"""
import json
import logging
import pathlib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REPORTS_DIR = pathlib.Path("reports")

# In-memory: SSE events + done flag (rebuilt from disk on startup)
_events: dict[str, list[dict]] = {}
_done:   dict[str, bool]       = {}


# ── Lifecycle ─────────────────────────────────────────────────────────

def create_job(job_id: str, scan_llm: str, report_llm: str, platforms: list[str],
               report_name: str = "") -> None:
    """Called when a scan is accepted. Writes initial meta to disk."""
    REPORTS_DIR.mkdir(exist_ok=True)
    _events[job_id] = []
    _done[job_id]   = False
    _write_meta(job_id, {
        "job_id":       job_id,
        "report_name":  report_name,
        "status":       "running",
        "started_at":   _now(),
        "completed_at": None,
        "scan_llm":     scan_llm,
        "report_llm":   report_llm,
        "platforms":    platforms,
        "total":        0,
        "critical":     0,
        "high":         0,
        "medium":       0,
        "low":          0,
        "info":         0,
    })


def complete_job(job_id: str, summary: dict) -> None:
    """Called when synthesis finishes successfully."""
    _done[job_id] = True
    meta = _read_meta(job_id) or {}
    meta.update({
        "status":       "completed",
        "completed_at": _now(),
        "total":        summary.get("total", 0),
        "critical":     summary.get("by_severity", {}).get("CRITICAL", 0),
        "high":         summary.get("by_severity", {}).get("HIGH", 0),
        "medium":       summary.get("by_severity", {}).get("MEDIUM", 0),
        "low":          summary.get("by_severity", {}).get("LOW", 0),
        "info":         summary.get("by_severity", {}).get("INFO", 0),
        "platforms":    list(summary.get("by_platform", {}).keys()),
    })
    _write_meta(job_id, meta)


def fail_job(job_id: str, reason: str = "") -> None:
    """Called when the audit task crashes."""
    _done[job_id] = True
    meta = _read_meta(job_id) or {}
    meta.update({
        "status":       "error",
        "completed_at": _now(),
        "error":        reason[:200],
    })
    _write_meta(job_id, meta)


# ── In-memory accessors (SSE) ──────────────────────────────────────

def push_event(job_id: str, event: dict) -> None:
    _events.setdefault(job_id, []).append(event)


def get_events(job_id: str) -> list[dict]:
    return _events.get(job_id, [])


def is_done(job_id: str) -> bool:
    if job_id in _done:
        return _done[job_id]
    # Fallback: check disk (for jobs from previous runs during same session)
    meta = _read_meta(job_id)
    return bool(meta and meta.get("status") in ("completed", "error"))


def job_exists(job_id: str) -> bool:
    return job_id in _events or _meta_path(job_id).exists()


# ── History listing ────────────────────────────────────────────────

def list_jobs(limit: int = 50) -> list[dict]:
    """Return all jobs sorted by started_at descending."""
    REPORTS_DIR.mkdir(exist_ok=True)
    jobs = []
    for meta_file in sorted(REPORTS_DIR.glob("*.meta.json"), reverse=True):
        try:
            jobs.append(json.loads(meta_file.read_text()))
        except Exception as exc:
            logger.warning("Could not read meta file %s: %s", meta_file, exc)
    return jobs[:limit]


# ── Startup restore ───────────────────────────────────────────────

def restore_from_disk() -> None:
    """
    On server startup, mark all persisted jobs as done in memory
    so /api/status can return immediately for completed jobs.
    """
    REPORTS_DIR.mkdir(exist_ok=True)
    restored = 0
    for meta_file in REPORTS_DIR.glob("*.meta.json"):
        try:
            meta = json.loads(meta_file.read_text())
            job_id = meta.get("job_id", "")
            if job_id and meta.get("status") in ("completed", "error"):
                _done[job_id] = True
                restored += 1
        except Exception:
            pass
    if restored:
        logger.info("Restored %d completed job(s) from disk", restored)


# ── Internals ─────────────────────────────────────────────────────

def _meta_path(job_id: str) -> pathlib.Path:
    return REPORTS_DIR / f"{job_id}.meta.json"


def _write_meta(job_id: str, data: dict) -> None:
    _meta_path(job_id).write_text(json.dumps(data, indent=2, default=str))


def _read_meta(job_id: str) -> dict | None:
    p = _meta_path(job_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
