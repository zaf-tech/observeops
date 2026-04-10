# ObserveOps — Product Roadmap & Enhancement Ideas
> AIops Infrastructure Auditing Platform · Future Scope Document  
> Last updated: April 2026 · Author: ZafTech

---

## Vision

Transform ObserveOps from a one-shot audit tool into a **continuous, conversational AIops platform** — one that not only finds problems but explains them, tracks them over time, and helps teams fix them. The goal is a product that an enterprise CTO would pay for monthly, not just run once.

---

## Priority 1 — Highest Impact (Build Next)

### 1.1 Report Chat Agent
**"Ask anything about your infrastructure report"**

A conversational AI interface scoped to a specific audit report. The LLM receives the full findings JSON and executive markdown as system context and answers natural language questions in real time.

**Example interactions:**
- *"Which S3 bucket is the highest risk and why?"*
- *"Show me all IAM findings sorted by blast radius"*
- *"What would it cost to remediate the critical issues?"*
- *"Draft a Jira ticket for finding #3"*
- *"Compare my AWS posture to industry benchmarks"*

**Technical approach:**
```
Report page
└── 💬 "Ask about this report" button
    └── Slide-in chat panel
        ├── System context: findings JSON + markdown injected once per session
        ├── User message → POST /api/chat/{job_id}
        └── Streaming SSE response rendered as markdown
```

- Backend: `/api/chat/{job_id}` — load report JSON, build system prompt, stream LLM response
- Works with any LLM already configured (Ollama, Claude Sonnet, GPT-4o)
- Conversation history retained in session (last 10 turns for context window efficiency)
- Frontend: collapsible slide-in chat panel on the report page, no page reload

**Why it's sellable:** No other infrastructure audit tool lets you *talk* to your report. This is the single biggest differentiator.

---

### 1.2 Remediation Playbooks
**"Don't just tell me what's wrong — tell me exactly how to fix it"**

For each finding, auto-generate a step-by-step remediation guide with exact CLI commands, Terraform/Pulumi snippets, or console step-by-step instructions tailored to the affected resource.

**Example output for a public S3 bucket finding:**
```bash
# Step 1: Block public access
aws s3api put-public-access-block \
  --bucket my-bucket-name \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Step 2: Verify
aws s3api get-public-access-block --bucket my-bucket-name
```

- LLM generates playbook on-demand per finding (cached after first generation)
- Supports: AWS CLI, Azure CLI, gcloud CLI, Terraform HCL, Kubernetes YAML
- "Copy to clipboard" and "Download as .sh / .tf" buttons in UI

---

### 1.3 Scheduled Scans + Drift Detection
**"Is my security posture getting better or worse?"**

- Run the same credential set on a configurable schedule (daily, weekly, monthly)
- Each new scan is automatically compared to the previous one
- Three categories of change: **New** (regressions), **Fixed** (improvements), **Changed** (severity shifts)
- Trend chart on dashboard: finding count over time per severity

**Drift report additions:**
- "Since last scan: 3 new CRITICAL, 7 fixed HIGH, net improvement score: +12"
- Email/Slack notification on regression (new CRITICAL detected)
- SLA tracking: how long has each finding been open across scans?

---

## Priority 2 — Strong Market Differentiators

### 2.1 Compliance Framework Mapping
**"Are we SOC 2 ready?"**

Automatically map every finding to one or more compliance frameworks:

| Framework | Coverage |
|-----------|----------|
| SOC 2 Type II | Trust Services Criteria (CC6, CC7, CC8) |
| ISO 27001:2022 | Annex A controls |
| CIS Benchmarks | AWS, Azure, GCP, Kubernetes |
| PCI-DSS v4.0 | Requirements 1, 2, 6, 7, 8 |
| HIPAA | Security Rule safeguards |
| NIST CSF | Identify, Protect, Detect, Respond, Recover |

**Output:** A compliance scorecard per framework — *"You satisfy 67% of SOC 2 CC6 (Logical Access Controls). 4 gaps require remediation."*

**Why it's sellable:** Compliance readiness assessments cost $50k+ from consulting firms. This automates a significant portion of that work.

---

### 2.2 Executive Dashboard (Cross-Report Analytics)
**"One screen that shows the health of everything, over time"**

A persistent web dashboard aggregating data across all historical reports:

- **Trend lines:** finding counts per severity over time (30/60/90 days)
- **Platform heatmap:** which cloud provider has the most findings per category
- **Top 10 recurring findings:** issues that never get fixed
- **Cloud spend trend:** total cost across all providers over time
- **Risk score:** a single composite number (0–100) representing overall security posture
- **Team leaderboard:** if multi-tenant, which team/client improved most this month

---

### 2.3 Jira / Slack / Microsoft Teams Integration
**"Turn findings into tickets automatically"**

- **Jira:** One-click "Create ticket" per finding — pre-filled with title, description, severity, remediation steps, affected resource. Bulk-create all CRITICAL/HIGH findings as an epic.
- **Slack:** Webhook alert on scan completion with severity summary card and link to report. Immediate alert channel for new CRITICAL findings.
- **Microsoft Teams:** Adaptive card with scan summary, top 3 findings, and "Open Full Report" button.
- **PagerDuty:** Trigger an incident for CRITICAL findings in production environments.

---

### 2.4 Risk Scoring + SLA Breach Tracking

- Assign each finding a numeric risk score (1–10) combining: severity, exploitability, blast radius, asset criticality
- Track mean time to remediate (MTTR) per team, per platform, per category
- SLA thresholds: CRITICAL must be resolved within 24h, HIGH within 7 days
- SLA breach alerts: *"Finding #AWS-047 has been open for 18 days — SLA breached"*
- Risk score trends in executive report: improving or deteriorating?

---

## Priority 3 — Enterprise & Commercial Features

### 3.1 Multi-Tenant Workspace Management
**For MSPs, consulting firms, and enterprises with multiple teams**

- Separate workspaces per client/team with isolated credential storage
- Role-based access: Admin, Analyst, Read-only
- White-label PDF reports: client's logo, colour scheme, company name on cover
- Report sharing via time-limited signed URL (no login required for recipients)
- Billing per workspace / per scan for SaaS monetisation

---

### 3.2 Infrastructure Inventory View
**"What do I actually have running?"**

Beyond security findings — show a complete inventory of discovered assets:

- **AWS:** All EC2 instances (type, region, state, cost/month), S3 buckets (size, public/private), RDS instances, Lambda functions, IAM users (last login, MFA status)
- **Azure:** All VMs, Storage Accounts, App Services, Managed Identities
- **GCP:** GKE clusters, Cloud Run services, GCS buckets, Service Accounts

Exportable as CSV/Excel. Useful for asset management, FinOps, and capacity planning beyond security.

---

### 3.3 Predictive Cost Intelligence
**Beyond billing history — predict the future**

- Trend-based spend forecasting: *"At current growth rate, AWS bill will reach $28k in 3 months"*
- Anomaly detection: flag unusual spend spikes mid-month before the invoice arrives
- Right-sizing recommendations: identify idle EC2s, oversized RDS, underused reservations
- Reservation / savings plan recommendations with projected annual savings
- Cross-cloud cost comparison: *"This workload costs 40% more on Azure than equivalent AWS services"*

---

### 3.4 CI/CD Pipeline Gate
**"Block deployments that introduce new security findings"**

- GitHub Action / GitLab CI job that runs ObserveOps as a pipeline step
- Configurable policy: fail pipeline if new CRITICAL or HIGH findings are introduced
- PR comment with finding summary
- Baseline comparison: only flag *new* findings vs the last approved baseline

```yaml
# Example GitHub Action
- name: ObserveOps Security Gate
  uses: zaftech/observeops-action@v1
  with:
    api_url: ${{ secrets.OBSERVEOPS_URL }}
    fail_on: CRITICAL,HIGH
    aws_access_key: ${{ secrets.AWS_ACCESS_KEY_ID }}
```

---

### 3.5 Kubernetes & Container Deep Scan
**Extend into runtime security**

- Live pod/container scanning for known CVEs (using Trivy or Grype under the hood)
- RBAC misconfiguration detection (overly permissive ClusterRoles, wildcard verbs)
- Network policy gaps: pods with no NetworkPolicy applied
- Image provenance: unsigned images, images from untrusted registries
- Runtime anomaly detection via Falco integration

---

## Priority 4 — Future Innovation

### 4.1 Natural Language Scan Configuration
*"Scan my AWS account for anything that could cause a data breach and cost more than $5k/month"*

Instead of configuring credential fields, users describe what they want to find in plain English. An LLM translates this into a structured scan configuration.

### 4.2 Auto-Remediation (with approval gate)
For low-risk, reversible fixes:
- User approves a remediation in the UI
- ObserveOps executes the fix (e.g., enable S3 block public access)
- Documents the change, before/after state
- Rolls back if anything goes wrong
- Full audit trail

**Note:** This breaks the "read-only" model — requires careful scoping and explicit opt-in per fix type.

### 4.3 Peer Benchmarking
*"How does my AWS security posture compare to similar companies?"*

Anonymised, aggregated benchmarking data:
- *"Companies your size have an average of 3.2 CRITICAL findings. You have 7."*
- Industry-specific benchmarks (fintech, healthcare, e-commerce)
- Percentile ranking: *"You're in the top 23% for IAM hygiene"*

### 4.4 AI-Powered Threat Modelling
Given the infrastructure inventory and findings, the LLM constructs a threat model:
- Most likely attack paths through the environment
- Crown jewel identification: which assets are most valuable to an attacker?
- MITRE ATT&CK mapping of each finding
- Prioritised remediation based on actual attack likelihood, not just severity labels

---

## Monetisation Model Ideas

| Tier | Price | Features |
|------|-------|----------|
| **Community** | Free | 1 workspace, 5 scans/month, Ollama LLM only, basic PDF |
| **Professional** | $99/mo | Unlimited scans, all cloud providers, Claude/GPT-4 LLM, chat agent, scheduled scans |
| **Business** | $499/mo | Multi-workspace, compliance mapping, Jira/Slack integration, drift detection, white-label PDF |
| **Enterprise** | Custom | SSO, SOC 2 report, on-premise deployment, dedicated support, CI/CD gate, custom plugins |

---

## Technical Debt & Architecture Improvements

- **Async plugin execution:** Run all plugins in parallel (currently sequential) — could cut scan time by 60%
- **Plugin marketplace:** Allow third-party plugins via a defined interface + packaging standard
- **WebSocket for progress:** Replace SSE with WebSocket for bidirectional communication (needed for chat agent)
- **Report versioning:** Store diffs between report versions, not just full snapshots
- **Credential vault:** Integrate with HashiCorp Vault or AWS Secrets Manager instead of environment variables
- **Horizontal scaling:** Redis-backed job queue (Celery/RQ) to support concurrent scans across multiple workers

---

*This document is maintained by ZafTech. Items marked Priority 1 are candidates for the next development sprint.*
