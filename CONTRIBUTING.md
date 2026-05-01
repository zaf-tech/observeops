# Contributing to ObserveOps

Thank you for your interest in contributing to ObserveOps.

## Before you contribute

- Read and follow the project Code of Conduct in CODE_OF_CONDUCT.md.
- Open an issue first for major changes so we can align on scope.
- Keep all platform integrations read-only.

## Development setup

1. Fork the repository and create a feature branch.
2. Run the project locally (Docker or local dev) as documented in README.md.
3. Make focused changes with clear commit messages.
4. Add or update tests when behavior changes.
5. Open a pull request with a clear summary.

## Pull request checklist

- Change is scoped and documented.
- No secrets are committed.
- Tests pass locally when applicable.
- Backward compatibility is considered.
- Plugin architecture rules are respected.

## Plugin contribution rules

- Add new platforms as plugin files only.
- Do not hardcode platform logic into agents.
- Handle missing credentials gracefully.
- Return standardized finding objects.

## Reporting bugs and requesting features

- Use GitHub Issues.
- Include reproduction steps and expected vs actual behavior.
- For security issues, do not open public issues. See SECURITY.md.

## Contributor contacts

- Talha Jilal: talhajilal@gmail.com
- Talha Jilal (ZafTech): talha.jilal@zaftech.ca
- Ramish Amir: Ramishamir2750@gmail.com

## Liability and risk notice

This project is provided as open source under the MIT License.
Use this software at your own risk.