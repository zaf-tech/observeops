# ObserverAI — Project Skills

Slash commands available in this workspace.

| Command | Skill folder | What it does |
|---------|-------------|--------------|
| `/scaffold-project` | `scaffold-project/` | Bootstrap the full project structure (base_plugin, config, .env.example, requirements.txt, entrypoint) |
| `/new-plugin` | `new-plugin/` | Scaffold a new platform plugin from the BasePlugin template |
| `/validate-plugin` | `validate-plugin/` | Lint a plugin file against all ObserverAI rules and interface requirements |
| `/run-audit` | `run-audit/` | Generate or explain the audit runner that discovers and executes available plugins |
| `/synthesize-report` | `synthesize-report/` | Scaffold or improve the Synthesizer that turns findings into an executive report |

## Quick start

```
/scaffold-project    ← run this first on a fresh repo
/new-plugin          ← add platforms one at a time
/validate-plugin     ← check your work before committing
/run-audit           ← wire it all up and run
```
