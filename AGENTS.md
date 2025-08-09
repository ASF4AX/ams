# AGENTS.md Template

## Scope and Inheritance
This file defines baseline rules for the repository and all subdirectories. You can place additional `AGENTS.md` files in lower directories to override these defaults.

## Agent Behavior
Coding agents using this repository should:

- Read `PRD.md` to understand features and requirements.
- Consult documents in `docs/` for implementation details and best practices.
- Produce reliable and maintainable code that matches documented expectations.

## Document Usage Guidelines

### PRD.md
- Describes goals and user scenarios.
- Review thoroughly before adding or modifying features.

### agent-rules/
- Locate reusable guidance in the `agent-rules/` directory.
- Store shared style guides, naming conventions, and testing practices here.
- Find language-specific setup instructions here if needed.
- Refer to shared rules in this folder for conventions that apply across languages.
- Follow language-specific guides such as [Python](./agent-rules/python/AGENTS.md) or [JavaScript](./agent-rules/js/AGENTS.md).

### docs/
- Consult guides in the `docs/` directory for project-specific instructions and best practices.
- Use `docs/plan.md` to track upcoming tasks and progress. Read it before starting work and update it after completing a task.
- Follow `docs/AGENTS.md` for rules when editing the task list or current goal.

## Development Guidelines
- Keep functions small and focused.
- Use consistent naming conventions.
- Comment any non-obvious logic.
- Avoid hardcoded values unless required by documentation.

## Commenting Essentials
Comment to explain *why*, not *what*.
Use block comments for context, docstrings for interfaces.
Avoid stating the obvious or leaving stale comments.
Keep it clear, minimal, and up to date.

## Commit and Communication
- Summarize the implemented changes in commit and PR messages.
- Refer to sections of `PRD.md` or relevant docs where appropriate.
- Write concise, clear English.

## Testing and Validation
- Provide tests for important modules such as parsers or retry logic.
- Ensure output conforms to the specified structure.
- Simulate failure scenarios if feasible to confirm robustness measures.
- Display the names of executed tests in the output by enabling verbose mode
  (or the equivalent) in your test runner.
