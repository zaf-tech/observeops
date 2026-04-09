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
    billing_data = platform_stats.get("_billing")
    non_billing_stats = {k: v for k, v in platform_stats.items() if k != "_billing"}

    if non_billing_stats or billing_data:
        stats_cards = ""
        for pname, meta in non_billing_stats.items():
            icon = PLATFORM_ICONS.get(pname, "📦")
            stats_cards += _build_platform_stats_card(pname, icon, meta)

        billing_section_html = ""
        if billing_data:
            billing_section_html = _build_billing_html(billing_data)

        platform_overview_html = f"""
        <div class="page-break"></div>
        <div class="content-page">
            <div class="page-section-header teal">
                <span>📊 PLATFORM OVERVIEW</span>
                <span class="section-sub">Live statistics collected during scan</span>
            </div>
            {f'<div class="stats-grid">{stats_cards}</div>' if stats_cards else ""}
            {billing_section_html}
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

    # ── PER-PROVIDER PAGES — one page per cloud provider ─────────────
    # Group findings and stats by provider
    all_providers = sorted(set(
        list(by_plat.keys()) + list(non_billing_stats.keys())
    ))
    per_provider_pages = ""
    for provider in all_providers:
        prov_findings = [f for f in findings if f.get("platform") == provider]
        prov_stats    = non_billing_stats.get(provider)
        prov_billing  = billing_data.get(provider) if billing_data else None
        pc            = PROVIDER_COLORS.get(provider, {"bar": "#14b8a6", "mtd": "#3b82f6", "header": "#0f172a", "accent": "#14b8a6", "icon": "📦", "label": provider.upper()})
        icon          = PLATFORM_ICONS.get(provider, "📦")

        # Provider stats card
        prov_stats_html = ""
        if prov_stats:
            prov_stats_html = f'<div style="margin-bottom:16px">{_build_platform_stats_card(provider, icon, prov_stats)}</div>'

        # Provider billing mini-section
        prov_billing_html = ""
        if prov_billing and isinstance(prov_billing, dict):
            hist = prov_billing.get("historical_months", [])
            mtd  = prov_billing.get("current_mtd")
            fc   = prov_billing.get("forecast")
            svcs = prov_billing.get("top_services", [])
            cur  = prov_billing.get("current_month", "Current")
            if hist or mtd:
                bars = [{"month": m["month"], "amount": m["amount"], "color": pc["bar"], "opacity": "0.75"} for m in hist]
                if mtd:
                    bars.append({"month": f"{cur} MTD", "amount": mtd["amount"], "color": pc["mtd"], "opacity": "0.9"})
                if fc:
                    bars.append({"month": "Fcst", "amount": fc["amount"], "color": "#f97316", "opacity": "0.65"})
                svg = _build_provider_svg(bars, chart_w=350, chart_h=90)
                table_rows_b = ""
                for i, m in enumerate(hist):
                    prev = hist[i-1]["amount"] if i > 0 else None
                    diff = f"{((m['amount']-prev)/prev*100):+.1f}%" if prev and prev > 0 else "—"
                    diff_c = "#dc2626" if diff.startswith("+") and float(diff[1:-1]) > 10 else ("#16a34a" if diff.startswith("-") else "#6b7280")
                    table_rows_b += f"<tr><td>{m['month']}</td><td style='text-align:right'>${m['amount']:,.2f}</td><td style='text-align:right;color:{diff_c}'>{diff}</td></tr>"
                if mtd:
                    table_rows_b += f"<tr style='background:#eff6ff'><td>{cur} (MTD)</td><td style='text-align:right;color:#2563eb;font-weight:700'>${mtd['amount']:,.2f}</td><td>—</td></tr>"
                if fc:
                    table_rows_b += f"<tr style='background:#fff7ed'><td><em>Forecast</em></td><td style='text-align:right;color:#ea580c;font-weight:700'>${fc['amount']:,.2f}</td><td>—</td></tr>"
                svc_rows_b = ""
                if svcs:
                    max_s = svcs[0]["amount"] or 1
                    for s in svcs[:6]:
                        pct = int((s["amount"] / max_s) * 100)
                        svc_rows_b += f"<tr><td style='font-size:7.5pt'>{s['service'][:40]}</td><td><div style='background:#e5e7eb;height:6px;width:80px;border-radius:2px'><div style='background:{pc['accent']};height:6px;width:{pct}%;border-radius:2px'></div></div></td><td style='text-align:right;font-size:7.5pt'>${s['amount']:,.2f}</td></tr>"
                prov_billing_html = f"""
                <div style="margin:12px 0;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">
                    <div style="padding:7px 12px;background:{pc['header']};color:{pc['accent']};font-size:9pt;font-weight:800">💰 Billing — {pc['label']}</div>
                    <div style="padding:10px 12px;background:white">
                        {svg}
                        <div style="display:flex;gap:8px;margin-top:4px;font-size:6.5pt;color:#9ca3af">
                            <span>&#9646; Historical</span>
                            {"<span style='color:#3b82f6'>&#9646; MTD</span>" if mtd else ""}
                            {"<span style='color:#f97316'>&#9646; Forecast</span>" if fc else ""}
                        </div>
                        {f"<table class='billing-table' style='margin-top:8px'><tr><th>Month</th><th style='text-align:right'>Cost</th><th style='text-align:right'>vs Prev</th></tr>{table_rows_b}</table>" if table_rows_b else ""}
                        {f"<p style='font-size:8pt;font-weight:600;margin-top:8px;margin-bottom:3px'>Top Services</p><table class='billing-table'>{svc_rows_b}</table>" if svc_rows_b else ""}
                    </div>
                </div>"""
            elif prov_billing.get("note"):
                prov_billing_html = f'<p style="font-size:8pt;color:#b45309;border:1px solid #fde68a;background:#fffbeb;padding:6px 10px;border-radius:6px;margin:10px 0">{prov_billing["note"]}</p>'

        # Provider findings by severity
        prov_findings_html = ""
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            sev_f = [f for f in prov_findings if f.get("severity") == sev]
            if not sev_f:
                continue
            cfg = SEV_CONFIG[sev]
            cards_p = ""
            for i, f in enumerate(sev_f):
                evidence = f.get("evidence", {})
                ev_html = ""
                if evidence:
                    ev_items = "".join(
                        f"<div><span class='ev-key'>{k}:</span> <span class='ev-val'>{str(v)[:120]}</span></div>"
                        for k, v in list(evidence.items())[:3]
                    )
                    ev_html = f'<div class="evidence-block">{ev_items}</div>'
                cards_p += f"""
                <div class="finding-card" style="border-left-color:{cfg['hex']}">
                    <div class="finding-header">
                        <span class="finding-num" style="background:{cfg['hex']}">{i+1}</span>
                        <div class="finding-meta">
                            <span class="finding-resource">{f.get('resource','')[:80]}</span>
                            <span class="finding-cat">{f.get('category','').title()}</span>
                        </div>
                    </div>
                    <p class="finding-title">{f.get('finding','')}</p>
                    <div class="finding-rec"><span class="rec-icon">→</span><span>{f.get('recommendation','')}</span></div>
                    {ev_html}
                </div>"""
            prov_findings_html += f"""
            <div class="section-header" style="background:{cfg['hex']}">
                <span>{cfg['emoji']} {sev}</span><span class="section-count">{len(sev_f)}</span>
            </div>{cards_p}"""

        if not prov_findings_html and not prov_stats_html and not prov_billing_html:
            continue

        # Provider severity summary bar
        prov_by_sev = {sev: len([f for f in prov_findings if f.get("severity") == sev]) for sev in ["CRITICAL","HIGH","MEDIUM","LOW","INFO"]}
        sev_bar = ""
        for sev, cnt in prov_by_sev.items():
            if cnt:
                cfg = SEV_CONFIG[sev]
                sev_bar += f'<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;background:{cfg["bg"]};border:1px solid {cfg["border"]};font-size:7.5pt;font-weight:700;color:{cfg["hex"]}">{cfg["emoji"]} {cnt}</span>'

        per_provider_pages += f"""
        <div class="page-break"></div>
        <div class="content-page">
            <div class="provider-page-header" style="background:linear-gradient(90deg,{pc['header']},{pc['header']}ee);border-left:5px solid {pc['accent']}">
                <span style="font-size:18pt">{icon}</span>
                <div>
                    <div style="font-size:14pt;font-weight:900;color:{pc['accent']}">{pc['label']} Report</div>
                    <div style="font-size:8pt;color:#94a3b8;margin-top:2px">{len(prov_findings)} findings · {generated}</div>
                </div>
                <div style="margin-left:auto;display:flex;gap:6px;flex-wrap:wrap">{sev_bar}</div>
            </div>
            {prov_stats_html}
            {prov_billing_html}
            {prov_findings_html if prov_findings_html else '<p style="color:#6b7280;font-size:9pt;padding:12px 0">No findings for this provider.</p>'}
        </div>"""

    # ── PAGE — All Findings (consolidated, sorted by severity) ───────
    all_finding_sections = ""
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
        all_finding_sections += f"""
        <div class="section-header" style="background:{cfg['hex']}">
            <span>{cfg['emoji']} {sev} FINDINGS</span>
            <span class="section-count">{len(sev_findings)}</span>
        </div>
        {cards}"""

    if not all_finding_sections:
        all_finding_sections = '<div class="no-findings">✅ No findings detected across all scanned platforms.</div>'

    findings_page = f"""
    <div class="page-break"></div>
    <div class="content-page">
        <div class="page-section-header orange">
            <span>🔍 ALL FINDINGS — CONSOLIDATED</span>
            <span class="section-sub">Sorted by severity · {total} total</span>
        </div>
        {all_finding_sections}
    </div>
    """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{css}</style></head>
<body>
{cover}
{platform_overview_html}
{executive_html}
{per_provider_pages}
{findings_page}
<div class="report-footer">
    ObserveOps · {generated} · Report {job_id}… · Read-only scan · No changes were made to any system
</div>
</body>
</html>"""


PROVIDER_COLORS = {
    "aws":   {"bar": "#f97316", "mtd": "#3b82f6", "header": "#1c1917", "accent": "#f97316", "icon": "☁️",  "label": "AWS"},
    "azure": {"bar": "#3b82f6", "mtd": "#60a5fa", "header": "#1e1b4b", "accent": "#3b82f6", "icon": "🔷", "label": "Azure"},
    "gcp":   {"bar": "#eab308", "mtd": "#facc15", "header": "#1c1917", "accent": "#eab308", "icon": "🌐", "label": "GCP"},
}


def _fmt_usd(n: float) -> str:
    if n >= 1_000_000:
        return f"${n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"${n/1_000:.1f}k"
    return f"${n:,.2f}"


def _build_provider_svg(bars: list[dict], chart_w: int = 300, chart_h: int = 80) -> str:
    """Build an SVG bar chart for one provider."""
    if not bars:
        return ""
    max_amt = max(b["amount"] for b in bars) or 1
    n = len(bars)
    slot_w = (chart_w - 10) / n
    bar_w  = max(slot_w - 6, 4)
    svg_bars = ""
    for i, b in enumerate(bars):
        x = 5 + i * slot_w + (slot_w - bar_w) / 2
        bh = max(int((b["amount"] / max_amt) * (chart_h - 18)), 2)
        by = chart_h - 12 - bh
        color = b.get("color", "#14b8a6")
        lbl   = _fmt_usd(b["amount"])
        month_short = b["month"].replace("(MTD)", "").replace("(Forecast)", "").strip()
        month_short = month_short[:6]  # "Jan 25"
        svg_bars += (
            f'<rect x="{x:.1f}" y="{by}" width="{bar_w:.1f}" height="{bh}" fill="{color}" rx="2" opacity="{b.get("opacity","0.85")}"/>'
            f'<text x="{x + bar_w/2:.1f}" y="{by - 2}" text-anchor="middle" font-size="5" fill="#4b5563">{lbl}</text>'
            f'<text x="{x + bar_w/2:.1f}" y="{chart_h - 2}" text-anchor="middle" font-size="4.5" fill="#9ca3af">{month_short}</text>'
        )
    return f'<svg width="{chart_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg" style="overflow:visible">{svg_bars}</svg>'


def _build_billing_html(billing: dict) -> str:
    """Build multi-cloud billing section for PDF (WeasyPrint)."""
    if not billing:
        return ""

    providers = [(k, v) for k, v in billing.items() if isinstance(v, dict)]
    if not providers:
        return ""

    # Aggregate KPIs
    total_mtd      = sum(v.get("current_mtd", {}).get("amount", 0) for _, v in providers)
    total_forecast = sum(v.get("forecast", {}).get("amount", 0) for _, v in providers)
    total_6mo      = sum(sum(m["amount"] for m in v.get("historical_months", [])) for _, v in providers)

    # KPI strip
    kpi_html = f"""
    <div class="billing-kpi-row">
        <div class="billing-kpi">
            <div class="billing-kpi-value">${total_mtd:,.2f}</div>
            <div class="billing-kpi-label">Total Cloud Spend (MTD)</div>
        </div>
        <div class="billing-kpi" style="border-color:#fed7aa;background:#fff7ed">
            <div class="billing-kpi-value" style="color:#ea580c">{f'${total_forecast:,.2f}' if total_forecast else '—'}</div>
            <div class="billing-kpi-label">Projected This Month</div>
        </div>
        <div class="billing-kpi" style="border-color:#99f6e4;background:#f0fdf4">
            <div class="billing-kpi-value" style="color:#0d9488">${total_6mo:,.2f}</div>
            <div class="billing-kpi-label">Last 6 Months Total</div>
        </div>
    </div>"""

    # Per-provider cards
    provider_cards = ""
    for provider, data in providers:
        pc = PROVIDER_COLORS.get(provider, {"bar": "#14b8a6", "mtd": "#3b82f6", "header": "#0f172a", "accent": "#14b8a6", "icon": "💰", "label": provider.upper()})
        hist = data.get("historical_months", [])
        mtd  = data.get("current_mtd")
        fc   = data.get("forecast")
        svcs = data.get("top_services", [])
        budgets = data.get("budgets", [])
        current_month = data.get("current_month", "Current")

        # Build bars list
        bars = [{"month": m["month"], "amount": m["amount"], "color": pc["bar"], "opacity": "0.75"} for m in hist]
        if mtd:
            bars.append({"month": f"{current_month} MTD", "amount": mtd["amount"], "color": pc["mtd"], "opacity": "0.9"})
        if fc:
            bars.append({"month": f"Fcst", "amount": fc["amount"], "color": "#f97316", "opacity": "0.65"})

        svg = _build_provider_svg(bars)

        # Month table rows
        table_rows = ""
        for i, m in enumerate(hist):
            prev = hist[i-1]["amount"] if i > 0 else None
            diff = f"{((m['amount']-prev)/prev*100):+.1f}%" if prev and prev > 0 else "—"
            diff_color = "#dc2626" if diff.startswith("+") and float(diff[1:-1]) > 10 else ("#16a34a" if diff.startswith("-") else "#6b7280")
            table_rows += f"<tr><td>{m['month']}</td><td style='text-align:right'>${m['amount']:,.2f}</td><td style='text-align:right;color:{diff_color}'>{diff}</td></tr>"
        if mtd:
            table_rows += f"<tr style='background:#eff6ff'><td>{current_month} (MTD)</td><td style='text-align:right;color:#2563eb;font-weight:700'>${mtd['amount']:,.2f}</td><td>—</td></tr>"
        if fc:
            table_rows += f"<tr style='background:#fff7ed'><td><em>Forecast</em></td><td style='text-align:right;color:#ea580c;font-weight:700'>${fc['amount']:,.2f}</td><td>—</td></tr>"

        # Services rows
        svc_rows = ""
        if svcs:
            max_svc = svcs[0]["amount"] or 1
            for svc in svcs[:8]:
                pct = int((svc["amount"] / max_svc) * 100)
                svc_rows += f"""
                <tr>
                    <td style="font-size:7.5pt;color:#374151;padding:2px 6px">{svc['service'][:40]}</td>
                    <td style="padding:2px 6px">
                        <div style="background:#e5e7eb;height:6px;border-radius:2px;width:100px">
                            <div style="background:{pc['accent']};height:6px;border-radius:2px;width:{pct}%"></div>
                        </div>
                    </td>
                    <td style="text-align:right;font-size:7.5pt;font-weight:600;padding:2px 6px">${svc['amount']:,.2f}</td>
                </tr>"""

        # MoM trend
        trend_html = ""
        if len(hist) >= 2:
            prev_amt = hist[-2]["amount"]
            curr_amt = hist[-1]["amount"]
            pct_chg  = ((curr_amt - prev_amt) / prev_amt * 100) if prev_amt > 0 else 0
            trend_color = "#dc2626" if pct_chg > 10 else ("#16a34a" if pct_chg < -5 else "#6b7280")
            arrow = "▲" if pct_chg > 0 else "▼"
            trend_html = f'<span style="font-size:8pt;color:{trend_color}">{arrow} {abs(pct_chg):.1f}% MoM</span>'

        note_html = f'<p style="font-size:7.5pt;color:#b45309;border:1px solid #fde68a;background:#fffbeb;padding:4px 8px;border-radius:4px;margin-top:6px">{data.get("note","")}</p>' if data.get("note") else ""

        budget_html = ""
        if budgets:
            budget_html = '<p style="font-size:8pt;font-weight:600;margin-top:8px;margin-bottom:3px">Budgets</p>'
            for b in budgets[:4]:
                amt = f"${b['budget']:,.2f}" if b.get("budget") else "Unlimited"
                budget_html += f'<div style="display:flex;justify-content:space-between;font-size:8pt;padding:2px 0"><span style="color:#374151">{b["name"]}</span><span style="font-weight:700;color:#d97706">{amt}</span></div>'

        provider_cards += f"""
        <div class="billing-provider-card">
            <div class="billing-provider-header" style="background:{pc['header']}">
                <span style="font-size:13pt">{pc['icon']}</span>
                <span style="font-size:10pt;font-weight:800;color:{pc['accent']};letter-spacing:0.05em">{pc['label']}</span>
                {f'<span style="font-size:7.5pt;color:#94a3b8">· {data.get("project_id","")}</span>' if data.get("project_id") else ""}
                <span style="margin-left:auto;font-size:7.5pt">{trend_html}</span>
            </div>
            <div class="billing-provider-body">
                <!-- KPIs -->
                <div style="display:flex;gap:8px;margin-bottom:8px">
                    {f'<div class="billing-mini-kpi"><div class="billing-mini-val" style="color:#1e293b">${mtd["amount"]:,.2f}</div><div class="billing-mini-lbl">MTD Spend</div></div>' if mtd else ""}
                    {f'<div class="billing-mini-kpi" style="background:#fff7ed;border-color:#fed7aa"><div class="billing-mini-val" style="color:#ea580c">${fc["amount"]:,.2f}</div><div class="billing-mini-lbl">Forecast</div></div>' if fc else ""}
                    <div class="billing-mini-kpi" style="background:#f8fafc;border-color:#e2e8f0"><div class="billing-mini-val" style="color:#0d9488">${sum(m["amount"] for m in hist):,.2f}</div><div class="billing-mini-lbl">6-month total</div></div>
                </div>
                <!-- Chart -->
                {svg if svg else ""}
                <!-- Legend -->
                <div style="display:flex;gap:10px;margin-top:4px;font-size:6.5pt;color:#9ca3af">
                    <span>&#9646; Historical</span>
                    {f'<span style="color:#3b82f6">&#9646; MTD</span>' if mtd else ""}
                    {f'<span style="color:#f97316">&#9646; Forecast</span>' if fc else ""}
                </div>
                <!-- Table -->
                {f'<table class="billing-table" style="margin-top:8px"><tr><th>Month</th><th style="text-align:right">Cost</th><th style="text-align:right">vs Prev</th></tr>{table_rows}</table>' if table_rows else ""}
                {f'<p style="font-size:8pt;font-weight:600;margin-top:8px;margin-bottom:3px">Top Services (Current Month)</p><table class="billing-table"><tr><th>Service</th><th>Spend</th><th style="text-align:right">Amount</th></tr>{svc_rows}</table>' if svc_rows else ""}
                {budget_html}
                {note_html}
            </div>
        </div>"""

    return f"""
    <div class="billing-section">
        <div class="billing-header">
            <span>💰 CLOUD BILLING DASHBOARD</span>
            <span style="font-size:8pt;opacity:0.7">Live data · All amounts in USD</span>
        </div>
        {kpi_html}
        <div class="billing-providers-grid">
            {provider_cards}
        </div>
    </div>"""


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

/* ── Billing section ── */
.billing-section {
    margin-top: 20px;
    border: 1px solid #d1fae5;
    border-radius: 10px;
    overflow: hidden;
    page-break-inside: avoid;
}
.billing-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px;
    background: linear-gradient(90deg, #0f172a, #134e4a);
    color: #14B8A6;
    font-size: 10pt; font-weight: 800; letter-spacing: 0.04em;
}
.billing-kpi-row {
    display: flex; gap: 10px; padding: 12px 16px;
    background: #f8fafc; border-bottom: 1px solid #e2e8f0;
}
.billing-kpi {
    flex: 1; border: 1px solid #d1fae5; background: white;
    border-radius: 8px; padding: 8px 12px; text-align: center;
}
.billing-kpi-value { font-size: 14pt; font-weight: 900; color: #0f172a; }
.billing-kpi-label { font-size: 7pt; color: #6b7280; margin-top: 2px; }
.billing-providers-grid {
    display: flex; flex-direction: column; gap: 14px;
    padding: 14px 16px; background: white;
}
.billing-provider-card {
    border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;
    page-break-inside: avoid;
}
.billing-provider-header {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px; color: white;
}
.billing-provider-body {
    padding: 10px 12px; background: white;
}
.billing-mini-kpi {
    flex: 1; background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 6px; padding: 5px 8px; text-align: center;
}
.billing-mini-val { font-size: 10pt; font-weight: 800; }
.billing-mini-lbl { font-size: 6.5pt; color: #6b7280; margin-top: 1px; }
.billing-table {
    width: 100%; border-collapse: collapse; font-size: 8pt;
}
.billing-table th {
    background: #f8fafc; padding: 4px 6px;
    text-align: left; font-weight: 700; color: #374151;
    border-bottom: 1px solid #e2e8f0; font-size: 7.5pt;
}
.billing-table td { padding: 3px 6px; border-bottom: 1px solid #f1f5f9; }

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

/* ── Per-provider page header ── */
.provider-page-header {
    display: flex; align-items: center; gap: 14px;
    padding: 14px 18px; border-radius: 10px; margin-bottom: 18px;
    color: white;
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
