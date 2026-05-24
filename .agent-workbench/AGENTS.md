# Agent Workbench Guidelines

This directory is the preferred place for reusable agent-side tooling and guidance that should not clutter the repository root.

## Query Tools

- Put repeatable query and inspection helpers under `queries/`.
- Do not save one-off commands here unless they are likely to be reused.
- Prefer small scripts with stable CLI flags over ad hoc inline snippets.

## Environment Targets

- Do not hardcode environment-specific URIs in committed scripts.
- Read named targets such as `local`, `dev`, or `prod` from a local config file.
- Keep the committed shape in `config.example.json`.
- Create an ignored `config.json` locally when a real environment mapping is needed.

## API Usage

- Prefer `.agent-workbench/queries/api_smoke_check.py` over ad hoc HTTP snippets when checking the AMS read API.
- When reporting API check results, state which target or explicit base URL was used.
- Treat the intended API target as the primary source of truth; do not fall back to another target unless the user asks for it.
