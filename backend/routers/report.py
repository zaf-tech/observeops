"""GET /api/report/{job_id} — fetch report JSON; GET /api/report/{job_id}/pdf — styled PDF."""
import logging
import pathlib

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

REPORTS_DIR = pathlib.Path("reports")

SEV_CONFIG = {
    "CRITICAL": {"hex": "#dc2626", "bg": "#fef2f2", "border": "#fca5a5", "emoji": "🔴"},
    "HIGH":     {"hex": "#ea580c", "bg": "#fff7ed", "border": "#fdba74", "emoji": "🟠"},
    "MEDIUM":   {"hex": "#d97706", "bg": "#fffbeb", "border": "#fde68a", "emoji": "🟡"},
    "LOW":      {"hex": "#16a34a", "bg": "#f0fdf4", "border": "#86efac", "emoji": "🟢"},
    "INFO":     {"hex": "#2563eb", "bg": "#eff6ff", "border": "#93c5fd", "emoji": "ℹ️"},
}

PLATFORM_ICONS = {
    "github": "🐙", "gitlab": "🦊", "aws": "☁️", "azure": "🔷",
    "gcp": "🌐", "jenkins": "🏗️", "sonarqube": "📊", "snyk": "🛡️",
    "argocd": "🚀", "circleci": "⭕", "bitbucket": "🧑‍💻",
}


@router.get("/report/{job_id}")
async def get_report(job_id: str):
    from synthesizer import load_report
    from routers.analyze import job_exists, is_job_done

    if not job_exists(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if not is_job_done(job_id):
        return JSONResponse(status_code=202, content={"status": "pending", "message": "Audit still running"})

    report = load_report(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found — audit may have failed")
    return report


@router.get("/report/{job_id}/pdf")
async def download_pdf(job_id: str):
    from synthesizer import load_report
    from routers.analyze import job_exists, is_job_done

    if not job_exists(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if not is_job_done(job_id):
        return JSONResponse(status_code=202, content={"status": "pending"})

    report = load_report(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    pdf_path = REPORTS_DIR / f"{job_id}.pdf"

    try:
        _render_pdf_weasyprint(report, pdf_path)
    except Exception as exc:
        logger.warning("WeasyPrint failed (%s), using reportlab fallback", exc)
        try:
            _render_pdf_reportlab(report, pdf_path)
        except Exception as exc2:
            logger.error("PDF generation failed: %s", exc2)
            raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"observeops-report-{job_id[:8]}.pdf",
    )


# ── WeasyPrint renderer ───────────────────────────────────────────────

def _render_pdf_weasyprint(report: dict, output_path: pathlib.Path) -> None:
    from weasyprint import HTML
    html = _build_html(report)
    HTML(string=html).write_pdf(str(output_path))


def _build_html(report: dict) -> str:
    from datetime import datetime
    import markdown as md_lib

    summary        = report.get("summary", {})
    findings       = report.get("findings", [])
    markdown_text  = report.get("markdown", "")
    platform_stats = report.get("platform_stats", {})
    by_sev         = summary.get("by_severity", {})
    by_plat        = summary.get("by_platform", {})
    by_cat         = summary.get("by_category", {})
    total          = summary.get("total", 0)
    platforms      = ", ".join(by_plat.keys()) or "None"
    generated      = datetime.utcnow().strftime("%B %d, %Y · %H:%M UTC")
    job_id         = report.get("job_id", "")[:8]
    plugin_audit   = report.get("plugin_audit", [])

    available_plugins = [p for p in plugin_audit if p["status"] == "available"]
    skipped_plugins   = [p for p in plugin_audit if p["status"] == "skipped"]

    # Risk level
    if by_sev.get("CRITICAL", 0) > 0:
        risk_label, risk_color, risk_bg = "CRITICAL RISK", "#dc2626", "#fef2f2"
    elif by_sev.get("HIGH", 0) > 0:
        risk_label, risk_color, risk_bg = "HIGH RISK", "#ea580c", "#fff7ed"
    elif by_sev.get("MEDIUM", 0) > 0:
        risk_label, risk_color, risk_bg = "MEDIUM RISK", "#d97706", "#fffbeb"
    else:
        risk_label, risk_color, risk_bg = "LOW RISK", "#16a34a", "#f0fdf4"

    css = _get_css()

    # ── PAGE 1 — Cover ───────────────────────────────────────────────
    sev_badges = ""
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        count = by_sev.get(sev, 0)
        cfg   = SEV_CONFIG[sev]
        sev_badges += f"""
        <div class="sev-box" style="border-color:{cfg['border']};background:{cfg['bg']}">
            <div class="sev-count" style="color:{cfg['hex']}">{count}</div>
            <div class="sev-label" style="color:{cfg['hex']}">{sev}</div>
        </div>"""

    plat_rows = ""
    for plat, cnt in sorted(by_plat.items(), key=lambda x: -x[1]):
        plat_rows += f"<tr><td>{PLATFORM_ICONS.get(plat,'📦')} {plat.title()}</td><td style='text-align:center;font-weight:700'>{cnt}</td></tr>"
    if not plat_rows:
        plat_rows = "<tr><td colspan='2' style='text-align:center;color:#6b7280'>No platforms scanned</td></tr>"

    cat_rows = ""
    for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
        cat_rows += f"<tr><td>{cat.title()}</td><td style='text-align:center;font-weight:700'>{cnt}</td></tr>"

    plugin_coverage = ""
    for p in available_plugins:
        plugin_coverage += f'<span class="plugin-badge avail">{p["plugin"]}</span>'
    for p in skipped_plugins:
        plugin_coverage += f'<span class="plugin-badge skip">{p["plugin"]}</span>'

    cover = f"""
    <div class="cover-page">
        <div class="cover-header">
            <div class="logo-mark">OO</div>
            <div>
                <div class="product-name">ObserveOps</div>
                <div class="product-sub">Multi-Agent Infrastructure Audit Platform</div>
            </div>
        </div>

        <div class="cover-title-block">
            <h1 class="cover-title">Infrastructure Security<br>Audit Report</h1>
            <div class="cover-meta">
                <span>Generated: {generated}</span>
                <span class="meta-sep">·</span>
                <span>Report ID: {job_id}…</span>
                <span class="meta-sep">·</span>
                <span>Platforms: {platforms}</span>
            </div>
        </div>

        <div class="risk-banner" style="background:{risk_bg};border-color:{risk_color}">
            <div class="risk-icon" style="color:{risk_color}">⚠</div>
            <div style="flex:1">
                <div class="risk-label" style="color:{risk_color}">Overall Risk Assessment</div>
                <div class="risk-value" style="color:{risk_color}">{risk_label}</div>
            </div>
            <div class="risk-total">
                <div class="risk-total-num" style="color:{risk_color}">{total}</div>
                <div class="risk-total-label" style="color:{risk_color}">Total Findings</div>
            </div>
        </div>

        <div class="sev-grid">{sev_badges}</div>

        <div class="cover-tables">
            <div class="cover-table-block">
                <h3 class="table-title">Findings by Platform</h3>
                <table class="summary-table">
                    <tr><th>Platform</th><th>Count</th></tr>
                    {plat_rows}
                </table>
            </div>
            <div class="cover-table-block">
                <h3 class="table-title">Findings by Category</h3>
                <table class="summary-table">
                    <tr><th>Category</th><th>Count</th></tr>
                    {cat_rows}
                </table>
            </div>
        </div>

        {f'<div class="plugin-section"><h3 class="table-title">Scan Coverage</h3><div class="plugin-grid">{plugin_coverage}</div></div>' if plugin_coverage else ""}

        <div class="cover-footer">
            <strong>CONFIDENTIAL</strong> — This report contains sensitive infrastructure information.
            Distribution should be restricted to authorized personnel only.
            All scans performed are read-only. No changes were made to any system.
        </div>
    </div>
    """

    # ── PAGE 2 — Platform Overview (live stats) ──────────────────────
    platform_overview_html = ""
    if platform_stats:
        stats_cards = ""
        for pname, meta in platform_stats.items():
            icon = PLATFORM_ICONS.get(pname, "📦")
            stats_cards += _build_platform_stats_card(pname, icon, meta)

        platform_overview_html = f"""
        <div class="page-break"></div>
        <div class="content-page">
            <div class="page-section-header teal">
                <span>📊 PLATFORM OVERVIEW</span>
                <span class="section-sub">Live statistics collected during scan</span>
            </div>
            <div class="stats-grid">
                {stats_cards}
            </div>
        </div>
        """

    # ── PAGE 3 — Executive AI Report (markdown) ──────────────────────
    executive_html = ""
    if markdown_text:
        # Convert markdown to HTML using python-markdown
        md_html = md_lib.markdown(
            markdown_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
        executive_html = f"""
        <div class="page-break"></div>
        <div class="content-page executive-report">
            <div class="page-section-header navy">
                <span>📋 EXECUTIVE INFRASTRUCTURE AUDIT REPORT</span>
                <span class="section-sub">AI-generated analysis · {generated}</span>
            </div>
            <div class="markdown-body">
                {md_html}
            </div>
        </div>
        """

    # ── PAGE 4 — Detailed Findings ───────────────────────────────────
    finding_sections = ""
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        sev_findings = [f for f in findings if f.get("severity") == sev]
        if not sev_findings:
            continue
        cfg = SEV_CONFIG[sev]

        cards = ""
        for i, f in enumerate(sev_findings):
            evidence = f.get("evidence", {})
            ev_html = ""
            if evidence:
                ev_items = "".join(
                    f"<div><span class='ev-key'>{k}:</span> <span class='ev-val'>{str(v)[:120]}</span></div>"
                    for k, v in list(evidence.items())[:5]
                )
                ev_html = f'<div class="evidence-block">{ev_items}</div>'

            cards += f"""
            <div class="finding-card" style="border-left-color:{cfg['hex']}">
                <div class="finding-header">
                    <span class="finding-num" style="background:{cfg['hex']}">{i+1}</span>
                    <div class="finding-meta">
                        <span class="finding-platform">{f.get('platform','').upper()}</span>
                        <span class="finding-resource">{f.get('resource','')[:80]}</span>
                        <span class="finding-cat">{f.get('category','').title()}</span>
                    </div>
                </div>
                <p class="finding-title">{f.get('finding','')}</p>
                <div class="finding-rec">
                    <span class="rec-icon">→</span>
                    <span>{f.get('recommendation','')}</span>
                </div>
                {ev_html}
            </div>"""

        finding_sections += f"""
        <div class="section-header" style="background:{cfg['hex']}">
            <span>{cfg['emoji']} {sev} FINDINGS</span>
            <span class="section-count">{len(sev_findings)}</span>
        </div>
        {cards}
        """

    if not finding_sections:
        finding_sections = '<div class="no-findings">✅ No findings detected across all scanned platforms.</div>'

    findings_page = f"""
    <div class="page-break"></div>
    <div class="content-page">
        <div class="page-section-header orange">
            <span>🔍 DETAILED FINDINGS</span>
            <span class="section-sub">Sorted by severity · {total} total</span>
        </div>
        {finding_sections}
    </div>
    """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{css}</style></head>
<body>
{cover}
{platform_overview_html}
{executive_html}
{findings_page}
<div class="report-footer">
    ObserveOps · {generated} · Report {job_id}… · Read-only scan · No changes were made to any system
</div>
</body>
</html>"""


def _build_platform_stats_card(pname: str, icon: str, meta: dict) -> str:
    """Build a styled platform stats card for the Platform Overview page."""
    stat_rows = ""

    if pname == "github":
        stats_map = [
            ("Account", f"@{meta.get('login','?')}" + (f" · Org: {meta['org']}" if meta.get("org") else "")),
            ("Repositories", f"{meta.get('total_repos','?')} total — {meta.get('public_repos','?')} public, {meta.get('private_repos','?')} private"),
            ("GitHub Actions", f"{meta.get('repos_with_actions','?')} repos with workflows ({meta.get('total_workflows','?')} total workflows)"),
            ("Commits (90 days)", f"{meta.get('commits_last_90_days','?')} commits across {meta.get('stats_sampled_repos','?')} sampled repos"),
            ("Merged PRs (90 days)", str(meta.get("merged_prs_last_90_days", "?"))),
            ("Org Members", str(meta["total_members"]) if "total_members" in meta else None),
        ]
        contributors = meta.get("top_contributors", [])
        if contributors:
            contrib_str = " · ".join(f"@{c['login']} ({c['contributions']})" for c in contributors[:5])
            stats_map.append(("Top Contributors", contrib_str))
    else:
        skip = {"platform"}
        stats_map = [
            (k.replace("_", " ").title(), str(v)[:120] if not isinstance(v, list) else ", ".join(str(i) for i in v[:5]))
            for k, v in meta.items() if k not in skip and v
        ]

    for label, value in stats_map:
        if value is None:
            continue
        stat_rows += f"""
        <div class="stat-row">
            <span class="stat-label">{label}</span>
            <span class="stat-value">{value}</span>
        </div>"""

    return f"""
    <div class="platform-card">
        <div class="platform-card-header">
            <span class="platform-icon">{icon}</span>
            <span class="platform-card-name">{pname.upper()}</span>
        </div>
        <div class="platform-stats">
            {stat_rows}
        </div>
    </div>"""


def _get_css() -> str:
    return """
@page {
    size: A4;
    margin: 0;
}
@page :first { margin: 0; }

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 10pt;
    color: #1a202c;
    background: white;
}

/* ── Cover page ── */
.cover-page {
    min-height: 297mm;
    background: linear-gradient(160deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    padding: 40px 48px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    color: white;
}

.cover-header {
    display: flex; align-items: center; gap: 16px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}
.logo-mark {
    width: 52px; height: 52px;
    background: linear-gradient(135deg, #14B8A6, #2563EB);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18pt; font-weight: 900; color: white; letter-spacing: -1px;
}
.product-name { font-size: 22pt; font-weight: 800; color: white; letter-spacing: -0.5px; }
.product-sub  { font-size: 9pt; color: #94a3b8; margin-top: 2px; }

.cover-title {
    font-size: 28pt; font-weight: 900; line-height: 1.1; letter-spacing: -1px;
    color: #14B8A6;
}
.cover-meta {
    display: flex; gap: 10px; margin-top: 10px;
    font-size: 8.5pt; color: #94a3b8; flex-wrap: wrap;
}
.meta-sep { color: #475569; }

.risk-banner {
    display: flex; align-items: center; gap: 20px;
    padding: 16px 22px; border-radius: 12px; border: 2px solid;
}
.risk-icon  { font-size: 26pt; line-height: 1; flex-shrink: 0; }
.risk-label { font-size: 8pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; }
.risk-value { font-size: 18pt; font-weight: 900; }
.risk-total { text-align: center; flex-shrink: 0; }
.risk-total-num   { font-size: 32pt; font-weight: 900; line-height: 1; }
.risk-total-label { font-size: 7.5pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }

.sev-grid { display: flex; gap: 10px; }
.sev-box {
    flex: 1; border: 2px solid; border-radius: 10px;
    padding: 12px 8px; text-align: center;
}
.sev-count { font-size: 26pt; font-weight: 900; line-height: 1; }
.sev-label { font-size: 7pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }

.cover-tables { display: flex; gap: 18px; }
.cover-table-block { flex: 1; }
.table-title {
    font-size: 8.5pt; font-weight: 700; color: #14B8A6;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 7px;
}
.summary-table { width: 100%; border-collapse: collapse; font-size: 8.5pt; }
.summary-table th {
    background: rgba(255,255,255,0.08); color: #94a3b8;
    padding: 6px 10px; text-align: left;
    font-size: 7.5pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
}
.summary-table td {
    padding: 6px 10px; border-bottom: 1px solid rgba(255,255,255,0.06); color: #e2e8f0;
}
.summary-table tr:last-child td { border-bottom: none; }

.plugin-section { }
.plugin-grid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
.plugin-badge {
    padding: 3px 8px; border-radius: 4px;
    font-size: 7.5pt; font-weight: 600; letter-spacing: 0.03em;
}
.plugin-badge.avail { background: rgba(20,184,166,0.2); color: #5eead4; border: 1px solid rgba(20,184,166,0.3); }
.plugin-badge.skip  { background: rgba(255,255,255,0.05); color: #475569; border: 1px solid rgba(255,255,255,0.1); }

.cover-footer {
    margin-top: auto; padding-top: 14px;
    border-top: 1px solid rgba(255,255,255,0.1);
    font-size: 7.5pt; color: #64748b; line-height: 1.5;
}

/* ── Page break ── */
.page-break { page-break-after: always; break-after: page; }

/* ── Content pages (shared) ── */
.content-page {
    padding: 32px 40px 70px;
    min-height: 200mm;
}

.page-section-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 18px; border-radius: 8px;
    color: white; font-weight: 700; font-size: 10.5pt;
    letter-spacing: 0.05em; margin-bottom: 22px;
}
.page-section-header.teal   { background: linear-gradient(90deg, #0f766e, #14B8A6); }
.page-section-header.navy   { background: linear-gradient(90deg, #0f172a, #1e3a5f); }
.page-section-header.orange { background: linear-gradient(90deg, #92400e, #ea580c); }
.section-sub { font-size: 8pt; font-weight: 400; opacity: 0.8; }

/* ── Platform Overview page ── */
.stats-grid {
    display: flex; flex-direction: column; gap: 16px;
}
.platform-card {
    border: 1px solid #e2e8f0; border-radius: 10px;
    overflow: hidden; page-break-inside: avoid;
}
.platform-card-header {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    background: linear-gradient(90deg, #0f172a, #1e293b);
    color: white;
}
.platform-icon { font-size: 14pt; }
.platform-card-name { font-size: 11pt; font-weight: 800; letter-spacing: 0.04em; color: #14B8A6; }
.platform-stats { padding: 4px 0; }
.stat-row {
    display: flex; align-items: flex-start;
    padding: 7px 16px; border-bottom: 1px solid #f1f5f9;
    font-size: 9pt;
}
.stat-row:last-child { border-bottom: none; }
.stat-label {
    width: 38%; flex-shrink: 0;
    font-weight: 600; color: #374151;
}
.stat-value {
    flex: 1; color: #1e293b;
}

/* ── Executive Report (markdown) ── */
.executive-report { }
.markdown-body { font-size: 9.5pt; line-height: 1.6; color: #1e293b; }

.markdown-body h1 {
    font-size: 18pt; font-weight: 900; color: #0f172a;
    margin: 0 0 14px; padding-bottom: 8px;
    border-bottom: 3px solid #14B8A6;
}
.markdown-body h2 {
    font-size: 13pt; font-weight: 800; color: #0f172a;
    margin: 22px 0 8px; padding: 8px 12px;
    background: #f1f5f9; border-left: 4px solid #14B8A6;
    border-radius: 0 6px 6px 0;
    page-break-after: avoid;
}
.markdown-body h3 {
    font-size: 10.5pt; font-weight: 700; color: #1e40af;
    margin: 14px 0 6px;
    page-break-after: avoid;
}
.markdown-body p {
    margin: 6px 0; color: #374151;
}
.markdown-body ul, .markdown-body ol {
    margin: 6px 0 10px 20px;
}
.markdown-body li { margin: 3px 0; color: #374151; }
.markdown-body strong { color: #0f172a; }
.markdown-body em { color: #4b5563; }
.markdown-body blockquote {
    margin: 10px 0; padding: 8px 14px;
    border-left: 4px solid #14B8A6;
    background: #f0fdfa; color: #134e4a;
    border-radius: 0 6px 6px 0; font-style: italic;
}
.markdown-body table {
    width: 100%; border-collapse: collapse;
    margin: 12px 0; font-size: 8.5pt;
    page-break-inside: avoid;
}
.markdown-body th {
    background: #0f172a; color: #14B8A6;
    padding: 8px 12px; text-align: left;
    font-weight: 700; font-size: 8pt; text-transform: uppercase; letter-spacing: 0.05em;
}
.markdown-body td {
    padding: 7px 12px; border-bottom: 1px solid #e2e8f0; color: #374151;
}
.markdown-body tr:nth-child(even) td { background: #f8fafc; }
.markdown-body code {
    font-family: 'Courier New', monospace;
    background: #1e293b; color: #38bdf8;
    padding: 1px 5px; border-radius: 3px; font-size: 8pt;
}
.markdown-body pre {
    background: #1e293b; padding: 10px 14px;
    border-radius: 6px; overflow: hidden;
    margin: 10px 0; font-size: 8pt;
    page-break-inside: avoid;
}
.markdown-body pre code { background: none; color: #94a3b8; }
.markdown-body hr {
    border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;
}

/* ── Detailed Findings page ── */
.section-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 9px 16px; border-radius: 8px;
    color: white; font-weight: 700; font-size: 9.5pt;
    letter-spacing: 0.04em; margin: 18px 0 9px;
    page-break-after: avoid;
}
.section-count {
    background: rgba(255,255,255,0.25); border-radius: 20px;
    padding: 2px 10px; font-size: 9pt;
}
.finding-card {
    border: 1px solid #e2e8f0; border-left: 4px solid;
    border-radius: 8px; padding: 12px 14px; margin-bottom: 9px;
    background: #f8fafc; page-break-inside: avoid;
}
.finding-header { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 7px; }
.finding-num {
    color: white; font-weight: 800; font-size: 7.5pt;
    padding: 2px 6px; border-radius: 4px; flex-shrink: 0; margin-top: 1px;
}
.finding-meta { display: flex; gap: 7px; flex-wrap: wrap; align-items: center; }
.finding-platform {
    font-size: 7pt; font-weight: 700; color: #1e40af;
    background: #dbeafe; padding: 1px 6px; border-radius: 3px;
}
.finding-resource {
    font-size: 7.5pt; color: #475569; font-family: 'Courier New', monospace;
}
.finding-cat {
    font-size: 7pt; color: #6b7280; background: #f1f5f9;
    padding: 1px 6px; border-radius: 3px;
}
.finding-title {
    font-size: 9pt; font-weight: 600; color: #1a202c;
    line-height: 1.4; margin-bottom: 7px;
}
.finding-rec {
    display: flex; gap: 7px; align-items: flex-start;
    background: #f0fdf4; border: 1px solid #bbf7d0;
    border-radius: 6px; padding: 6px 9px;
    font-size: 8pt; color: #166534; line-height: 1.4;
}
.rec-icon { font-weight: 900; flex-shrink: 0; }
.evidence-block {
    margin-top: 7px; padding: 6px 10px;
    background: #1e293b; border-radius: 5px;
    font-size: 7pt; color: #94a3b8;
    font-family: 'Courier New', monospace;
    display: flex; flex-direction: column; gap: 2px;
}
.ev-key { color: #38bdf8; }
.ev-val { color: #cbd5e1; }
.no-findings {
    text-align: center; padding: 40px;
    font-size: 13pt; color: #16a34a; font-weight: 600;
}

/* ── Fixed footer on all pages ── */
.report-footer {
    position: fixed; bottom: 0; left: 0; right: 0;
    padding: 7px 40px;
    background: #0f172a; color: #64748b;
    font-size: 7pt; text-align: center;
    border-top: 1px solid #1e293b;
}
"""


# ── ReportLab fallback ───────────────────────────────────────────────

def _render_pdf_reportlab(report: dict, output_path: pathlib.Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak,
    )

    TEAL   = colors.HexColor("#14B8A6")
    NAVY   = colors.HexColor("#0f172a")
    SLATE  = colors.HexColor("#1e293b")
    RED    = colors.HexColor("#dc2626")
    ORANGE = colors.HexColor("#ea580c")
    YELLOW = colors.HexColor("#d97706")
    GREEN  = colors.HexColor("#16a34a")
    BLUE   = colors.HexColor("#2563eb")

    SEV_RL = {"CRITICAL": RED, "HIGH": ORANGE, "MEDIUM": YELLOW, "LOW": GREEN, "INFO": BLUE}

    summary        = report.get("summary", {})
    findings       = report.get("findings", [])
    markdown_text  = report.get("markdown", "")
    platform_stats = report.get("platform_stats", {})
    by_sev         = summary.get("by_severity", {})
    by_plat        = summary.get("by_platform", {})
    total          = summary.get("total", 0)
    platforms      = ", ".join(by_plat.keys()) or "None"

    from datetime import datetime
    generated = datetime.utcnow().strftime("%B %d, %Y · %H:%M UTC")

    base = getSampleStyleSheet()
    S = {
        "cover_title": ParagraphStyle("CT", parent=base["Title"],
            textColor=TEAL, fontSize=26, leading=30, spaceAfter=6),
        "cover_sub": ParagraphStyle("CS", parent=base["Normal"],
            textColor=colors.HexColor("#94a3b8"), fontSize=9),
        "section_hdr": ParagraphStyle("SH", parent=base["Normal"],
            textColor=colors.white, fontSize=11, fontName="Helvetica-Bold",
            backColor=NAVY, borderPad=8, spaceBefore=16, spaceAfter=8),
        "h2": ParagraphStyle("H2", parent=base["Heading2"],
            textColor=NAVY, fontSize=13, spaceBefore=14, spaceAfter=4),
        "h3": ParagraphStyle("H3", parent=base["Heading3"],
            textColor=SLATE, fontSize=10, spaceBefore=10, spaceAfter=3),
        "stat_label": ParagraphStyle("SL", parent=base["Normal"],
            textColor=colors.HexColor("#374151"), fontSize=9, fontName="Helvetica-Bold"),
        "stat_value": ParagraphStyle("SV", parent=base["Normal"],
            textColor=colors.HexColor("#1e293b"), fontSize=9),
        "body": ParagraphStyle("B", parent=base["Normal"],
            textColor=colors.HexColor("#374151"), fontSize=9, leading=13),
        "rec": ParagraphStyle("R", parent=base["Normal"],
            textColor=GREEN, fontSize=9, leading=13, leftIndent=8),
        "platform_badge": ParagraphStyle("PL", parent=base["Normal"],
            textColor=BLUE, fontSize=8, fontName="Helvetica-Bold"),
        "resource": ParagraphStyle("RS", parent=base["Normal"],
            textColor=colors.HexColor("#6b7280"), fontSize=8, fontName="Courier"),
    }

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2.2*cm, rightMargin=2.2*cm,
        topMargin=1.8*cm, bottomMargin=2.2*cm,
    )
    story = []

    # ── Cover ────────────────────────────────────────────────────────
    story += [
        Paragraph("ObserveOps", ParagraphStyle("Logo", parent=base["Title"],
            textColor=TEAL, fontSize=30, spaceAfter=2)),
        Paragraph("Infrastructure Security Audit Report", S["cover_title"]),
        Paragraph(f"Generated: {generated}  ·  Platforms: {platforms}", S["cover_sub"]),
        Spacer(1, 0.3*cm),
        HRFlowable(width="100%", color=TEAL, thickness=2, spaceAfter=10),
    ]

    sev_data = [["Severity", "Count"]]
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        sev_data.append([sev, str(by_sev.get(sev, 0))])
    sev_data.append(["TOTAL", str(total)])

    sev_style = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR",  (0,0), (-1,0), TEAL),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-2),
            [colors.HexColor("#f8fafc"), colors.HexColor("#f1f5f9")]),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#e2e8f0")),
        ("FONTNAME",   (0,-1), (-1,-1), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#d1d5db")),
        ("ALIGN", (1,0), (1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ])
    for i, sev in enumerate(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"], start=1):
        c = SEV_RL.get(sev, NAVY)
        sev_style.add("TEXTCOLOR", (0,i), (0,i), c)
        sev_style.add("FONTNAME",  (0,i), (0,i), "Helvetica-Bold")
        sev_style.add("TEXTCOLOR", (1,i), (1,i), c)
        sev_style.add("FONTNAME",  (1,i), (1,i), "Helvetica-Bold")

    story.append(Table(sev_data, colWidths=[10*cm, 5*cm], style=sev_style))
    story.append(Spacer(1, 0.4*cm))

    if by_plat:
        plat_data = [["Platform", "Findings"]] + [
            [k.title(), str(v)] for k, v in sorted(by_plat.items(), key=lambda x: -x[1])
        ]
        plat_style = TableStyle([
            ("BACKGROUND", (0,0), (-1,0), SLATE),
            ("TEXTCOLOR",  (0,0), (-1,0), TEAL),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#d1d5db")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
                [colors.HexColor("#f8fafc"), colors.HexColor("#f1f5f9")]),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ])
        story.append(Paragraph("Findings by Platform", S["h3"]))
        story.append(Table(plat_data, colWidths=[10*cm, 5*cm], style=plat_style))

    story.append(PageBreak())

    # ── Platform Overview ────────────────────────────────────────────
    if platform_stats:
        story.append(Paragraph("📊 Platform Overview", S["h2"]))
        story.append(HRFlowable(width="100%", color=TEAL, thickness=2, spaceAfter=8))

        for pname, meta in platform_stats.items():
            icon = PLATFORM_ICONS.get(pname, "📦")
            story.append(Paragraph(f"{icon} {pname.upper()}", S["h3"]))

            if pname == "github":
                rows = [
                    ("Account", f"@{meta.get('login','?')}" + (f" · Org: {meta['org']}" if meta.get("org") else "")),
                    ("Repositories", f"{meta.get('total_repos','?')} total — {meta.get('public_repos','?')} public, {meta.get('private_repos','?')} private"),
                    ("GitHub Actions", f"{meta.get('repos_with_actions','?')} repos, {meta.get('total_workflows','?')} workflows"),
                    ("Commits (90d)", str(meta.get("commits_last_90_days","?"))),
                    ("Merged PRs (90d)", str(meta.get("merged_prs_last_90_days","?"))),
                ]
                contribs = meta.get("top_contributors", [])
                if contribs:
                    rows.append(("Top Contributors", " · ".join(f"@{c['login']} ({c['contributions']})" for c in contribs[:5])))
            else:
                skip = {"platform"}
                rows = [(k.replace("_"," ").title(), str(v)[:100]) for k, v in meta.items() if k not in skip and v]

            tbl_data = [[Paragraph(f"<b>{label}</b>", S["stat_label"]),
                         Paragraph(val, S["stat_value"])] for label, val in rows if val]
            if tbl_data:
                tbl = Table(tbl_data, colWidths=[5*cm, 10*cm])
                tbl.setStyle(TableStyle([
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ("TOPPADDING", (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                    ("ROWBACKGROUNDS", (0,0), (-1,-1),
                        [colors.HexColor("#f8fafc"), colors.white]),
                    ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
                ]))
                story.append(tbl)
            story.append(Spacer(1, 0.3*cm))

        story.append(PageBreak())

    # ── Executive AI Report (markdown as plain paragraphs) ───────────
    if markdown_text:
        story.append(Paragraph("📋 Executive Infrastructure Audit Report", S["h2"]))
        story.append(HRFlowable(width="100%", color=NAVY, thickness=2, spaceAfter=8))

        for line in markdown_text.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.15*cm))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], S["h2"]))
            elif line.startswith("### "):
                story.append(Paragraph(line[4:], S["h3"]))
            elif line.startswith("# "):
                story.append(Paragraph(line[2:], S["cover_title"]))
            elif line.startswith("|"):
                pass  # tables handled below
            elif line.startswith("- ") or line.startswith("* "):
                story.append(Paragraph(f"• {line[2:]}", ParagraphStyle(
                    "LI", parent=base["Normal"], fontSize=9,
                    leftIndent=12, textColor=colors.HexColor("#374151"))))
            elif line.startswith("> "):
                story.append(Paragraph(line[2:], ParagraphStyle(
                    "BQ", parent=base["Normal"], fontSize=9, leftIndent=16,
                    textColor=colors.HexColor("#134e4a"),
                    backColor=colors.HexColor("#f0fdfa"), borderPad=4)))
            else:
                story.append(Paragraph(line, S["body"]))

        story.append(PageBreak())

    # ── Detailed Findings ────────────────────────────────────────────
    story.append(Paragraph("🔍 Detailed Findings", S["h2"]))
    story.append(HRFlowable(width="100%", color=ORANGE, thickness=2, spaceAfter=10))

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        sev_findings = [f for f in findings if f.get("severity") == sev]
        if not sev_findings:
            continue

        col = SEV_RL.get(sev, NAVY)
        emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "ℹ️"}.get(sev, "")
        story.append(Paragraph(f"{emoji} {sev} — {len(sev_findings)} finding(s)", S["h3"]))

        for f in sev_findings:
            plat    = f.get("platform", "").upper()
            res     = f.get("resource", "")[:80]
            cat     = f.get("category", "").title()
            finding = f.get("finding", "")
            rec     = f.get("recommendation", "")

            story += [
                Paragraph(f"<b>[{plat}]</b> {res} · <i>{cat}</i>", S["platform_badge"]),
                Paragraph(finding, S["body"]),
                Paragraph(f"→ {rec}", S["rec"]),
                Spacer(1, 0.18*cm),
            ]

        story.append(HRFlowable(width="100%", color=colors.HexColor("#e2e8f0"),
                                thickness=1, spaceAfter=6))

    if not findings:
        story.append(Paragraph("✅ No findings detected.", S["body"]))

    doc.build(story)
