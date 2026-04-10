"""
POST /api/chat/{job_id} — streaming conversational AI over a specific audit report.

The LLM receives the full findings + executive markdown as system context and
streams answers back as Server-Sent Events (SSE). Works with every LLM provider
already configured in config.py (Ollama, Claude, GPT-4o, Gemini, etc.)
"""
import json
import logging
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    llm_provider: str = "ollama"
    llm_config: dict = {}


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/chat/{job_id}")
async def chat(job_id: str, request: ChatRequest):
    """Stream a conversational AI response grounded in a specific audit report."""
    from routers.analyze import job_exists, is_job_done
    from synthesizer import load_report

    if not job_exists(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if not is_job_done(job_id):
        raise HTTPException(status_code=202, detail="Report is still running")

    report = load_report(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report file not found")

    return StreamingResponse(
        _stream_response(report, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


# ── Streaming generator ───────────────────────────────────────────────────────

def _stream_response(report: dict, request: ChatRequest) -> Iterator[bytes]:
    try:
        from config import get_report_llm

        system_prompt = _build_system_prompt(report)
        llm = get_report_llm(request.llm_provider, request.llm_config)
        logger.info("Chat stream: job=%s provider=%s llm=%s",
                    report.get("job_id","")[:8], request.llm_provider, type(llm).__name__)

        # Keep last 10 conversation turns (5 pairs) to stay within context limits
        recent_history = request.history[-10:]

        # ── Chat-model path (ChatOpenAI, ChatAnthropic, ChatOllama …) ────
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

            messages = [SystemMessage(content=system_prompt)]
            for msg in recent_history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                else:
                    messages.append(AIMessage(content=msg.content))
            messages.append(HumanMessage(content=request.message))

            for chunk in llm.stream(messages):
                text = ""
                if hasattr(chunk, "content"):
                    text = chunk.content if isinstance(chunk.content, str) else ""
                elif isinstance(chunk, str):
                    text = chunk
                if text:
                    yield _sse({"chunk": text})

        except Exception as chat_exc:
            # ── Plain-LLM fallback (OllamaLLM string interface) ───────────
            logger.info("Chat: chat-model path failed (%s), trying string LLM", chat_exc)
            history_text = ""
            for msg in recent_history:
                role = "Human" if msg.role == "user" else "Assistant"
                history_text += f"\n{role}: {msg.content}"

            prompt = (
                f"{system_prompt}\n\n"
                f"{history_text}\n"
                f"Human: {request.message}\n"
                "Assistant:"
            )
            for chunk in llm.stream(prompt):
                text = chunk if isinstance(chunk, str) else str(chunk)
                if text:
                    yield _sse({"chunk": text})

        yield _sse({"done": True})

    except Exception as exc:
        logger.error("Chat stream fatal error: %s", exc, exc_info=True)
        yield _sse({"error": str(exc)})


def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode()


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(report: dict) -> str:
    summary    = report.get("summary", {})
    findings   = report.get("findings", [])
    markdown   = report.get("markdown", "")
    platforms  = list(summary.get("by_platform", {}).keys())
    by_sev     = summary.get("by_severity", {})
    report_name = report.get("report_name", "")

    # Sort findings by severity, take top 40 to stay within context
    _order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    top_findings = sorted(findings, key=lambda f: _order.get(f.get("severity", "INFO"), 4))[:40]

    # Trim markdown if very long (keep first ~6k chars which covers executive summary)
    md_text = markdown[:6000] + ("\n...[truncated]" if len(markdown) > 6000 else "")

    # Platform stats summary
    ps = report.get("platform_stats", {})
    ps_text = ""
    if ps:
        for pname, meta in ps.items():
            if pname == "_billing" or not isinstance(meta, dict):
                continue
            ps_text += f"\n[{pname.upper()}] "
            ps_text += " · ".join(f"{k}={v}" for k, v in list(meta.items())[:6] if k != "platform")

    findings_json = json.dumps(top_findings, indent=2, default=str)

    return f"""You are ObserveOps AI — a cloud security expert with full access to a specific infrastructure audit report. Your job is to answer questions, explain findings, suggest remediation steps, and help the user understand their security posture.

REPORT: {report_name or f'Audit {report.get("job_id","")[:8]}'}
PLATFORMS SCANNED: {', '.join(platforms) or 'none'}
FINDINGS SUMMARY: {summary.get('total', 0)} total — CRITICAL: {by_sev.get('CRITICAL',0)} | HIGH: {by_sev.get('HIGH',0)} | MEDIUM: {by_sev.get('MEDIUM',0)} | LOW: {by_sev.get('LOW',0)} | INFO: {by_sev.get('INFO',0)}
{f'PLATFORM STATS:{ps_text}' if ps_text else ''}

═══ EXECUTIVE REPORT ═══
{md_text}

═══ FINDINGS DATA (top {len(top_findings)} by severity) ═══
{findings_json}

RESPONSE RULES:
- Always ground your answers in the actual data above — reference real resource names, counts, and finding details
- For remediation questions: provide exact CLI commands (aws, az, gcloud, kubectl) or config steps specific to the affected resources
- For ticket drafting: produce complete, copy-pasteable Jira/GitHub issue content with title, description, acceptance criteria
- For risk questions: reason from actual severity, blast radius, and exploitability — don't just repeat the label
- If asked about something not in this report: say so clearly and offer what related context you do have
- Format all responses in Markdown — use headers, bullets, and code blocks where they add clarity
- Be concise by default; offer to elaborate if the user wants more depth
- Never fabricate findings, resource names, or cost figures that aren't in the data above"""
