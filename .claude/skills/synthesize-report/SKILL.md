# Skill: synthesize-report

Scaffold or improve the Synthesizer agent that turns raw plugin findings into an executive health report.

## Trigger

Use when the user says `/synthesize-report`, "build the synthesizer", "generate the report", "write the Synthesizer", or "create the executive summary".

## Behavior

1. Check whether `synthesizer.py` exists.
2. If not, generate it using the pattern below.
3. If it exists, review it against the rules and suggest improvements.

## Synthesizer pattern

```python
"""
Synthesizer — aggregates findings from all plugins and produces
a unified executive health report.

LLM routing (from config.py):
  - Default: Ollama llama3.2  (free, local)
  - Upgrade:  Claude Sonnet   (set REPORT_LLM=sonnet in .env)
"""
import json
from config import get_report_llm

class Synthesizer:
    def synthesize(self, findings: list[dict]) -> str:
        if not findings:
            return "No findings — all scanned platforms appear healthy."

        summary = self._group_by_severity(findings)
        prompt = self._build_prompt(findings, summary)
        llm = get_report_llm()
        return llm.complete(prompt)

    # ------------------------------------------------------------------
    def _group_by_severity(self, findings):
        groups = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}
        for f in findings:
            groups.setdefault(f["severity"], []).append(f)
        return groups

    def _build_prompt(self, findings, summary):
        counts = {k: len(v) for k, v in summary.items()}
        findings_json = json.dumps(findings, indent=2)
        return f"""You are an infrastructure security expert writing an executive report.

Finding counts: {counts}

Raw findings:
{findings_json}

Write a concise executive summary covering:
1. Overall risk posture (one sentence)
2. Top 3 critical/high issues with remediation steps
3. Breakdown by platform and category
4. Recommended priority action list
"""
```

## Rules
- Never hardcode a model name — always call `config.get_report_llm()`
- Synthesizer must accept ANY list of findings, including an empty list
- Must work with findings from zero, one, or many platforms simultaneously
