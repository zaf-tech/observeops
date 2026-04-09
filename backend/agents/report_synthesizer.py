"""
Skill 6 — Report Synthesizer
Receives all findings from Skills 1-5 and produces a prioritized
executive Markdown + PDF report using a high-reasoning LLM.
"""
import logging
import json
from typing import Callable

logger = logging.getLogger(__name__)


def _extract_llm_text(result) -> str:
    """
    Safely extract plain text from any LangChain response type.
    - OllamaLLM / string-based LLMs return str directly
    - ChatOpenAI, ChatAnthropic, ChatGoogleGenerativeAI etc. return AIMessage
    - AIMessage has a .content attribute (str or list of content blocks)
    """
    if result is None:
        return ""
    # AIMessage and similar chat model responses
    if hasattr(result, "content"):
        content = result.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            # Multi-modal content blocks — extract text parts
            parts = [c.get("text", "") if isinstance(c, dict) else str(c) for c in content]
            return " ".join(parts).strip()
    # Plain string (OllamaLLM, etc.)
    text = str(result).strip()
    # Guard against AIMessage repr leaking through
    if text.startswith("content=") and "additional_kwargs" in text:
        # Happens if someone does str(AIMessage(...)) — try to parse it out
        import re
        m = re.search(r"content='(.*?)'(?:\s+additional_kwargs|$)", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        m = re.search(r'content="(.*?)"(?:\s+additional_kwargs|$)', text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return text


class ReportSynthesizer:
    def __init__(self,
                 progress_cb: Callable[[str], None] | None = None,
                 report_llm: str | None = None,
                 llm_config: dict | None = None,
                 custom_instructions: str = "",
                 platform_stats: dict | None = None):
        self._progress            = progress_cb or (lambda msg: logger.info(msg))
        self._report_llm          = report_llm
        self._llm_config          = llm_config or {}
        self._custom_instructions = custom_instructions.strip()
        self._platform_stats      = platform_stats or {}

    def run(self, all_findings: list[dict]) -> dict:
        self._progress("ReportSynthesizer: aggregating findings…")
        summary = self._build_summary(all_findings)

        # Estimate tokens before calling LLM
        prompt_tokens_est = self._estimate_prompt_tokens(all_findings)
        self._progress(
            f"ReportSynthesizer: generating report via LLM provider='{self._report_llm}'… "
            f"(~{prompt_tokens_est:,} prompt tokens estimated)"
        )

        markdown, token_usage = self._generate_markdown(all_findings, summary)

        self._progress(
            f"ReportSynthesizer: report complete — "
            f"prompt {token_usage['prompt_tokens']:,} tok · "
            f"output {token_usage['completion_tokens']:,} tok · "
            f"total {token_usage['total_tokens']:,} tok"
        )
        return {"markdown": markdown, "summary": summary, "token_usage": token_usage}

    def _estimate_prompt_tokens(self, findings: list[dict]) -> int:
        """Rough token estimate: 1 token ≈ 4 characters."""
        prompt = self._build_prompt(findings, self._build_summary(findings))
        return max(1, len(prompt) // 4)

    # ── Summary ────────────────────────────────────────────────────────

    def _build_summary(self, findings: list[dict]) -> dict:
        severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        counts = {s: 0 for s in severity_order}
        by_platform: dict[str, int] = {}
        by_category: dict[str, int] = {}

        for f in findings:
            sev = f.get("severity", "INFO").upper()
            counts[sev] = counts.get(sev, 0) + 1
            plat = f.get("platform", "unknown")
            by_platform[plat] = by_platform.get(plat, 0) + 1
            cat = f.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total":       len(findings),
            "by_severity": counts,
            "by_platform": by_platform,
            "by_category": by_category,
        }

    # ── LLM generation ─────────────────────────────────────────────────

    def _generate_markdown(self, findings: list[dict], summary: dict) -> tuple[str, dict]:
        _null_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            from config import get_report_llm
            llm = get_report_llm(self._report_llm, self._llm_config)
            logger.info("ReportSynthesizer: LLM object created → %s", type(llm).__name__)

            prompt = self._build_prompt(findings, summary)
            prompt_tokens_est = max(1, len(prompt) // 4)
            logger.info("ReportSynthesizer: invoking LLM with %d findings (~%d tokens)…",
                        len(findings), prompt_tokens_est)

            result = llm.invoke(prompt)
            llm_text = _extract_llm_text(result)

            # Actual token counts from response metadata (LangChain standard)
            completion_tokens = max(1, len(llm_text) // 4)
            token_usage = {"prompt_tokens": prompt_tokens_est,
                           "completion_tokens": completion_tokens,
                           "total_tokens": prompt_tokens_est + completion_tokens}
            # Override with exact counts if LangChain provides them
            if hasattr(result, "usage_metadata") and result.usage_metadata:
                um = result.usage_metadata
                token_usage = {
                    "prompt_tokens":     getattr(um, "input_tokens",  prompt_tokens_est),
                    "completion_tokens": getattr(um, "output_tokens", completion_tokens),
                    "total_tokens":      getattr(um, "total_tokens",  token_usage["total_tokens"]),
                }
            logger.info("ReportSynthesizer: LLM returned %d chars | tokens: %s", len(llm_text), token_usage)

            if llm_text and len(llm_text) > 100:
                return self._format_report(llm_text, summary), token_usage
            else:
                logger.warning(
                    "ReportSynthesizer: LLM response too short (%d chars), "
                    "falling back to template. Response: %r",
                    len(llm_text), llm_text[:200]
                )

        except Exception as exc:
            logger.error(
                "ReportSynthesizer: LLM invocation failed — %s: %s. "
                "Falling back to structured template.",
                type(exc).__name__, exc
            )

        return self._template_report(findings, summary), _null_usage

    def _build_prompt(self, findings: list[dict], summary: dict) -> str:
        counts     = summary["by_severity"]
        platforms  = list(summary["by_platform"].keys())
        top        = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH")][:15]
        medium_low = [f for f in findings if f.get("severity") in ("MEDIUM", "LOW")][:10]

        findings_json = json.dumps(top + medium_low, indent=2, default=str)

        # Build platform stats block
        stats_block = ""
        if self._platform_stats:
            stats_block = "\nPLATFORM STATISTICS (collected live during scan):\n"
            for pname, meta in self._platform_stats.items():
                if pname == "_billing":
                    continue  # handled separately below
                stats_block += f"\n[{pname.upper()}]\n"
                for k, v in meta.items():
                    if k == "platform":
                        continue
                    if isinstance(v, list):
                        if v:
                            stats_block += f"  {k}: {', '.join(str(i) for i in v[:5])}\n"
                    else:
                        stats_block += f"  {k}: {v}\n"

        # Multi-cloud billing data block (real figures from Cost Explorer / Azure CM / GCP)
        billing_block = ""
        billing = self._platform_stats.get("_billing")
        if billing:
            billing_block = "\nCLOUD BILLING DATA (real figures collected during scan):\n"
            for provider, data in billing.items():
                if not isinstance(data, dict):
                    continue
                billing_block += f"\n  [{provider.upper()}]\n"
                for m in data.get("historical_months", []):
                    billing_block += f"    {m['month']}: ${m['amount']:,.2f} {m.get('unit','USD')}\n"
                if data.get("current_mtd"):
                    mtd = data["current_mtd"]
                    billing_block += f"    {data.get('current_month','Current')} (MTD): ${mtd['amount']:,.2f}\n"
                if data.get("forecast"):
                    fc = data["forecast"]
                    billing_block += f"    {data.get('current_month','Current')} (full month forecast): ${fc['amount']:,.2f}\n"
                if data.get("top_services"):
                    billing_block += "    Top services this month:\n"
                    for svc in data["top_services"][:5]:
                        billing_block += f"      - {svc['service']}: ${svc['amount']:,.2f}\n"
                if data.get("budgets"):
                    billing_block += "    Budgets configured:\n"
                    for b in data["budgets"][:3]:
                        amt = f"${b['budget']:,.2f}" if b.get("budget") else "no limit set"
                        billing_block += f"      - {b['name']}: {amt}\n"
                if data.get("note"):
                    billing_block += f"    Note: {data['note']}\n"

        # Custom instructions block
        custom_block = ""
        if self._custom_instructions:
            custom_block = f"\nADDITIONAL REQUIREMENTS FROM CLIENT:\n{self._custom_instructions}\n"

        return f"""You are a senior cloud security consultant writing an executive infrastructure audit report for a CTO/CISO audience.

SCAN RESULTS:
- Platforms scanned: {', '.join(platforms) or 'none'}
- Total findings: {summary['total']}
- CRITICAL: {counts.get('CRITICAL', 0)} | HIGH: {counts.get('HIGH', 0)} | MEDIUM: {counts.get('MEDIUM', 0)} | LOW: {counts.get('LOW', 0)} | INFO: {counts.get('INFO', 0)}
{stats_block}{billing_block}{custom_block}
FINDINGS (JSON):
{findings_json}

Write a professional executive report in Markdown with these exact sections:

## Platform Overview
For each platform scanned, write a 2-4 line summary covering:
- What was found (repos, pipelines, resources, etc.) with specific counts from the statistics above
- Overall health status
- Any standout positive or negative observations
Use the PLATFORM STATISTICS above to cite real numbers (e.g. "37 repositories (12 public, 25 private), 8 GitHub Actions workflows").

## Executive Summary
2-3 sentences summarizing the overall security posture and most critical risks found across all platforms.

## Critical & High Priority Issues
For each CRITICAL and HIGH finding: what was found, why it matters, and the specific remediation step.

## Medium & Low Priority Issues
Group by platform. Brief description of each issue and fix.

## Risk Breakdown Table
| Platform | Critical | High | Medium | Low | Total |
(fill in real numbers per platform)

## Recommended Action Plan
Numbered priority list of the top 5-10 remediation actions, ordered by risk.{custom_block and chr(10) + '(Address any additional client requirements listed above in this section.)' or ''}{billing_block and chr(10) + chr(10) + '## Cloud Billing Summary' + chr(10) + 'Using the REAL billing figures provided above (do NOT fabricate numbers):' + chr(10) + '- For each provider (AWS/Azure/GCP), show a month-by-month cost table (last 6 months)' + chr(10) + '- Include current month MTD and full-month forecast where available' + chr(10) + '- List the top services by cost for each provider' + chr(10) + '- Highlight notable spend trends (month-over-month increases/decreases %)' + chr(10) + '- Recommend cost optimisation opportunities aligned with the security findings' or ''}

## Positive Observations
Any platforms or controls that appear well-configured.

Rules:
- Be specific and use actual resource names and counts from findings and statistics
- Use professional security language
- Keep recommendations actionable and concrete
- Do NOT include generic boilerplate — only reference what was actually found
- If additional requirements were provided, integrate them naturally into relevant sections
"""

    def _format_report(self, llm_text: str, summary: dict) -> str:
        header = self._report_header(summary)
        return f"{header}\n\n{llm_text}"

    # ── Fallback template (used only when LLM fails) ──────────────────

    def _template_report(self, findings: list[dict], summary: dict) -> str:
        header = self._report_header(summary)
        lines  = [header]

        if self._custom_instructions:
            lines.append(f"\n## Additional Requirements\n\n{self._custom_instructions}\n")

        if not findings:
            lines.append("\n## Results\n\nNo findings detected across all scanned platforms.\n")
            lines.append("\n---\n*Generated by ObserveOps (template mode — LLM unavailable)*")
            return "\n".join(lines)

        lines.append("\n## Findings by Severity\n")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            sev_findings = [f for f in findings if f.get("severity", "").upper() == sev]
            if not sev_findings:
                continue
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "ℹ️"}.get(sev, "")
            lines.append(f"\n### {emoji} {sev} ({len(sev_findings)} findings)\n")
            for f in sev_findings:
                lines.append(f"**[{f.get('platform','').upper()}]** `{f.get('resource','')}`  ")
                lines.append(f"- **Issue:** {f.get('finding','')}")
                lines.append(f"- **Fix:** {f.get('recommendation','')}")
                lines.append("")

        lines.append("\n---")
        lines.append("*⚠ Note: This report was generated in template mode because the LLM was unavailable.*")
        lines.append("*Configure an LLM provider in the AI Model Routing section for a full AI-written executive report.*")
        return "\n".join(lines)

    def _report_header(self, summary: dict) -> str:
        from datetime import datetime
        counts    = summary["by_severity"]
        platforms = ", ".join(summary["by_platform"].keys()) or "none"

        header = f"""# ObserveOps Infrastructure Audit Report
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
**Platforms Scanned:** {platforms}

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | {counts.get('CRITICAL', 0)} |
| 🟠 HIGH | {counts.get('HIGH', 0)} |
| 🟡 MEDIUM | {counts.get('MEDIUM', 0)} |
| 🟢 LOW | {counts.get('LOW', 0)} |
| ℹ️ INFO | {counts.get('INFO', 0)} |
| **TOTAL** | **{summary['total']}** |
"""

        # Platform statistics section
        if self._platform_stats:
            header += "\n## Platform Overview\n"
            for pname, meta in self._platform_stats.items():
                if pname == "_billing":
                    continue
                header += f"\n### {pname.upper()}\n"
                header += self._format_platform_stats(pname, meta)

        # Multi-cloud billing section
        billing = self._platform_stats.get("_billing")
        if billing:
            header += "\n## Cloud Billing (Live Data)\n"
            for provider, data in billing.items():
                if not isinstance(data, dict):
                    continue
                header += f"\n### {provider.upper()}\n"
                header += self._format_billing_stats(data)

        # Custom instructions reminder
        if self._custom_instructions:
            header += f"\n> **Client Requirements Addressed:** {self._custom_instructions[:200]}{'…' if len(self._custom_instructions) > 200 else ''}\n"

        return header

    def _format_billing_stats(self, billing: dict) -> str:
        lines = []
        hist = billing.get("historical_months", [])
        if hist:
            lines.append("\n| Month | Cost (USD) |")
            lines.append("|-------|-----------|")
            for m in hist:
                lines.append(f"| {m['month']} | ${m['amount']:,.2f} |")
        mtd = billing.get("current_mtd")
        if mtd:
            lines.append(f"| {billing.get('current_month','Current')} (MTD) | ${mtd['amount']:,.2f} |")
        fc = billing.get("forecast")
        if fc:
            lines.append(f"| {billing.get('current_month','Current')} (forecast) | **${fc['amount']:,.2f}** |")
        if billing.get("top_services"):
            lines.append("\n**Top services this month:**")
            for svc in billing["top_services"][:8]:
                lines.append(f"- {svc['service']}: ${svc['amount']:,.2f}")
        return "\n".join(lines) + "\n"

    def _format_platform_stats(self, platform: str, meta: dict) -> str:
        """Render a human-readable stats block for a platform."""
        lines = []
        if platform == "github":
            if "login" in meta:
                lines.append(f"**Account:** @{meta['login']}" + (f" · Org: `{meta['org']}`" if meta.get("org") else ""))
            if "total_repos" in meta:
                lines.append(f"**Repositories:** {meta['total_repos']} total "
                             f"({meta.get('public_repos', '?')} public, {meta.get('private_repos', '?')} private)")
            if "repos_with_actions" in meta:
                lines.append(f"**GitHub Actions:** {meta['repos_with_actions']} repos with workflows "
                             f"({meta.get('total_workflows', 0)} total workflows)")
            if "commits_last_90_days" in meta:
                lines.append(f"**Commits (last 90 days):** {meta['commits_last_90_days']} "
                             f"*(sampled across {meta.get('stats_sampled_repos', '?')} repos)*")
            if "merged_prs_last_90_days" in meta:
                lines.append(f"**Merged PRs (last 90 days):** {meta['merged_prs_last_90_days']}")
            if meta.get("top_contributors"):
                contribs = ", ".join(
                    f"@{c['login']} ({c['contributions']})" for c in meta["top_contributors"]
                )
                lines.append(f"**Top Contributors:** {contribs}")
            if "total_members" in meta:
                lines.append(f"**Org Members:** {meta['total_members']}")
        else:
            # Generic: render key-value pairs, skipping internal fields
            skip = {"platform", "login", "org"}
            for k, v in meta.items():
                if k in skip:
                    continue
                label = k.replace("_", " ").title()
                if isinstance(v, list):
                    if v:
                        lines.append(f"**{label}:** {', '.join(str(i) for i in v[:5])}")
                else:
                    lines.append(f"**{label}:** {v}")

        return "\n".join(f"- {l}" for l in lines) + "\n" if lines else ""
