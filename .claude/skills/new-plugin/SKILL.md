# Skill: new-plugin

Scaffold a new ObserverAI platform plugin following the BasePlugin interface.

## Trigger

Use when the user says `/new-plugin`, "create a plugin", "add a new platform", or "scaffold a plugin".

## Behavior

Ask for:
1. **Platform name** (e.g. `datadog`, `pagerduty`) — becomes `{name}_plugin.py`
2. **Plugin category** — Cloud/K8s, Code Repo, CI/CD, Code Quality, or IaC
3. **Credential env vars** — the env variable names that signal this plugin is active
4. **Library/SDK** — the Python package used to talk to this platform

Then generate `plugins/{name}_plugin.py` using the template in TEMPLATE.md.

## Rules (from CLAUDE.md — never break)
- ALL access is READ-ONLY — no write, delete, or modify operations in scan logic
- Credentials come from `.env` only — never hardcoded, never logged
- `is_available()` must check env vars gracefully — no exceptions
- `run_scan()` returns `[]` on empty or error — never raises
- Every finding must match the Finding format exactly (see FINDING_FORMAT.md)
- No changes to any agent file — only a new plugin file

## Output

Create the file, then confirm:
> Plugin `plugins/{name}_plugin.py` created.
> Register credentials in `.env`: {CREDENTIAL_KEYS}
> Category: {category}
