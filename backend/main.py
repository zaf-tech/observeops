"""ObserveOps — FastAPI application entrypoint."""
import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ObserveOps API starting up")
    os.makedirs("reports", exist_ok=True)
    from job_store import restore_from_disk
    restore_from_disk()
    yield
    logger.info("ObserveOps API shutting down")


app = FastAPI(
    title="ObserveOps API",
    description="Platform-agnostic multi-agent infrastructure auditing system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from routers import analyze, status, report, validate, history, skills, chat  # noqa: E402

app.include_router(analyze.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(validate.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(chat.router,   prefix="/api")


@app.get("/", tags=["health"])
async def health():
    return {"status": "ok", "service": "ObserveOps API", "version": "1.0.0"}


@app.get("/api/plugins", tags=["info"])
async def list_plugins():
    """Return all registered plugins and which are currently available."""
    from plugins import discover_plugins, all_plugins
    available = {p.name for p in discover_plugins()}
    return {
        "total": len(all_plugins()),
        "available": len(available),
        "plugins": [
            {"name": p.name, "available": p.name in available, "credential_keys": p.credential_keys}
            for p in all_plugins()
        ],
    }
