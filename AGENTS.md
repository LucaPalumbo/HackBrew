# Repository Guidelines

## Project Structure & Module Organization

This directory is currently an empty project scaffold. No source code, tests, assets, or build configuration exist yet. As implementation begins, keep application code in `src/`, automated tests in `tests/`, static resources in `assets/`, and supporting documentation in `docs/`, unless the chosen framework requires another layout. Group related functionality into focused modules. Add a `README.md` describing the project and its actual directory structure.

## Build, Test, and Development Commands

No build, test, or local development commands are configured. When introducing tooling, document the exact setup, development, build, and test commands in `README.md`. Prefer a small, consistent command interface through the selected ecosystem's package scripts or a task runner. Do not assume commands such as `npm test` or `make build` work until their configuration is committed.

## Coding Style & Naming Conventions

Follow the standard conventions of the language and framework selected for the project. Use consistent indentation within each language, descriptive identifiers, and filenames that match the surrounding modules. Configure an appropriate formatter and linter early, and document how contributors run them. Keep changes focused; avoid unrelated formatting edits.

## Testing Guidelines

No testing framework or coverage threshold has been established. Add automated tests alongside new behavior and bug fixes once the implementation stack is selected. Organize tests by feature, use descriptive names that explain the expected behavior, and follow the framework's discovery conventions. Document how to run the full suite and individual tests.

## Commit & Pull Request Guidelines

There is no Git history from which to infer commit conventions. Use concise, imperative commit subjects, such as `Add initial project configuration`. Pull requests should describe the change, its purpose, and verification performed. Link relevant issues and include screenshots for visible interface changes. Explicitly identify setup changes or checks that could not be run.

## Security & Configuration

Never commit credentials, access tokens, or local secrets. When configuration is introduced, provide example files with placeholder values and ignore local overrides and generated artifacts.

## Agent skills

### Issue tracker

Track issues and specs in this repository's GitHub Issues. Before reading or publishing tickets, follow `docs/agents/issue-tracker.md`.

### Triage labels

Use the default triage labels. Before assigning a triage status, read `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the repository root and decisions in `docs/adr/`. Before exploring the codebase, follow `docs/agents/domain.md`.
