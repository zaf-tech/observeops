"""GET /api/skills — returns all agent skill definitions from YAML files."""
import pathlib
import yaml
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

SKILLS_DIR = pathlib.Path(__file__).parent.parent / "skills"
_SKILL_ORDER = [
    "cloud_auditor",
    "log_analyst",
    "security_auditor",
    "cicd_guard",
    "code_reviewer",
    "report_synthesizer",
]


@router.get("/skills")
async def get_skills():
    """Return all agent skill definitions in execution order."""
    skills = []
    for name in _SKILL_ORDER:
        path = SKILLS_DIR / f"{name}.yaml"
        if path.exists():
            try:
                with open(path) as f:
                    skills.append(yaml.safe_load(f))
            except Exception as exc:
                logger.warning("Failed to load skill %s: %s", name, exc)
    return {"skills": skills}
