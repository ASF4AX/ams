# Agent Workbench

This directory is reserved for agent-only working files inside this repository.

Intended use:
- reusable inspection scripts
- repeated query helpers
- scratch outputs that help with local verification

Rules:
- do not bother saving one-off commands or throwaway snippets here unless they are likely to be reused
- treat files here as disposable unless the user explicitly asks to promote them
- prefer creating subdirectories only when needed, for example `queries/` or `scratch/`
- do not rely on this path for application runtime behavior
- keep environment-specific targets and workflows documented inside this directory instead of in the repository root guidance

Git behavior:
- the directory is ignored by default
- this README, `.agent-workbench/AGENTS.md`, `.agent-workbench/config.example.json`, and reusable query helpers are intentionally kept in version control as markers and guidance
- `.agent-workbench/config.json` is ignored and should hold real local target values when needed
