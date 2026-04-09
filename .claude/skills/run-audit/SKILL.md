# Skill: run-audit

Scaffold or wire up the audit runner that discovers available plugins and executes them.

## Trigger

Use when the user says `/run-audit`, "run the audit", "execute a scan", "wire up the agents", or "how do I run this".

## Behavior

1. Check whether `run_audit.py` (or equivalent entrypoint) exists in the project root.
2. If it does NOT exist, generate it using the template below.
3. If it DOES exist, explain how to invoke it and what env vars to set.

## Generated entrypoint pattern

```python
"""ObserverAI — audit runner."""
import importlib, os, pathlib, logging
from synthesizer import Synthesizer

logging.basicConfig(level=logging.INFO)

PLUGIN_DIR = pathlib.Path(__file__).parent / "plugins"

def discover_plugins():
    plugins = []
    for path in sorted(PLUGIN_DIR.glob("*_plugin.py")):
        module_name = f"plugins.{path.stem}"
        mod = importlib.import_module(module_name)
        # find the class that subclasses BasePlugin
        for attr in vars(mod).values():
            if isinstance(attr, type) and hasattr(attr, "is_available") and attr.__name__ != "BasePlugin":
                instance = attr()
                if instance.is_available():
                    plugins.append(instance)
    return plugins

def main():
    plugins = discover_plugins()
    if not plugins:
        print("No plugins available — check your .env credentials.")
        return

    all_findings = []
    for plugin in plugins:
        print(f"Scanning {plugin.name}...")
        findings = plugin.run_scan()
        all_findings.extend(findings)
        print(f"  {len(findings)} findings")

    report = Synthesizer().synthesize(all_findings)
    print(report)

if __name__ == "__main__":
    main()
```

## Usage instructions to give the user

```bash
# 1. Copy and fill in credentials
cp .env.example .env
# 2. Install deps
pip install -r requirements.txt
# 3. Run
python run_audit.py
```

## Rules
- Never suggest running with credentials hardcoded in the command
- Only plugins whose `is_available()` returns True are executed
- The runner must not crash if zero plugins are available
