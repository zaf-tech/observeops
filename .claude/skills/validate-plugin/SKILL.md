# Skill: validate-plugin

Review an existing plugin file for compliance with ObserverAI rules and BasePlugin interface.

## Trigger

Use when the user says `/validate-plugin`, "check my plugin", "review this plugin", "does this plugin comply", or "lint the plugin".

## Behavior

Read the plugin file the user specifies (or the most recently edited `*_plugin.py`), then check each rule below. Report PASS / FAIL for each.

## Checklist

### Interface compliance
- [ ] Class inherits from `BasePlugin`
- [ ] `name` attribute is a non-empty string
- [ ] `credential_keys` is a list of strings
- [ ] `is_available()` is implemented and returns bool
- [ ] `run_scan()` is implemented and returns `list[dict]`
- [ ] `get_metadata()` is implemented and returns `dict`

### Safety rules (CRITICAL — any failure blocks merge)
- [ ] No write / delete / modify API calls anywhere in the file
- [ ] No credentials hardcoded (no string literals that look like keys/tokens)
- [ ] `is_available()` does not raise — wraps in try/except or only uses `os.getenv`
- [ ] `run_scan()` has a top-level try/except that returns `[]` on failure
- [ ] No `print()` for credentials or raw API responses — uses `logger` only

### Finding format
- [ ] Every dict appended to findings contains all 7 required keys:
      `platform`, `resource`, `severity`, `category`, `finding`, `recommendation`, `evidence`
- [ ] `severity` values are only: `CRITICAL | HIGH | MEDIUM | LOW | INFO`
- [ ] `category` values are only: `security | cost | reliability | performance | compliance`

### Plugin isolation
- [ ] File imports no other plugin files
- [ ] File does not import or modify any agent file
- [ ] Platform SDK is imported at top-level (not inside functions), so missing deps fail fast

## Output format

```
Plugin: plugins/my_plugin.py
─────────────────────────────
PASS  inherits BasePlugin
PASS  name defined
FAIL  run_scan() missing top-level try/except → findings could be lost on API error
PASS  no hardcoded credentials
...

Issues found: 1
Recommended fix: wrap run_scan body in try/except Exception and return [] on failure.
```
