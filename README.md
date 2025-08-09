# Agent Guidelines Template

This repository provides a base template for defining behavior and coding standards for AI agents using `AGENTS.md`.

## Structure

- `AGENTS.md` – Global default rules applied when no directory-level override exists
- `agent-rules/` – All supporting materials, such as coding style guides, naming conventions, testing practices, and templates

## Usage

1. Click "Use this template" to create a new repository.
2. Modify `AGENTS.md` to match your agent’s intended behavior and project context.
3. Place `AGENTS.md` in the root or any subdirectory of your project to define scope for that directory and its children.

## Notes

- The closest `AGENTS.md` file in the directory hierarchy overrides higher-level ones.
- All reusable guidance must be stored under the `agent-rules/` directory.
- This repository is intended for AI coding agents, not human contributors.
