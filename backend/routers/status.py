"""GET /api/status/{job_id} — Server-Sent Events stream of skill progress."""
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status/{job_id}")
async def stream_status(job_id: str):
    """SSE stream — sends progress events until the job completes."""
    from routers.analyze import get_job_events, is_job_done, job_exists

    if not job_exists(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    async def event_generator():
        sent = 0
        while True:
            events = get_job_events(job_id)
            while sent < len(events):
                event = events[sent]
                yield f"data: {json.dumps(event)}\n\n"
                sent += 1
            if is_job_done(job_id) and sent >= len(events):
                yield f"data: {json.dumps({'skill': 'DONE', 'status': 'complete', 'findings_count': sent})}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
