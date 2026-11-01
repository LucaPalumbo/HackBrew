# Repository Guidelines

## Project Structure & Module Organization

Application code lives in `src/hackbrew/` (Python/FastAPI) and `src/frontend/` (Vue/TypeScript). Automated tests live in `tests/` and supporting documentation in `docs/`. Keep frontend resources within the frontend framework's layout. Group related functionality into focused modules and keep `README.md` aligned with the actual project structure.

## Build, Test, and Development Commands

Use `scripts/hackbrew` for Docker-based setup, development, build, formatting, lint, typechecking, and tests. `README.md` documents the exact supported commands. Keep all application tooling in containers; do not introduce a requirement for host-installed Python, Node, or MongoDB. Update the documentation when changing the command interface.

## Coding Style & Naming Conventions

Follow the standard conventions of the language and framework selected for the project. Use consistent indentation within each language, descriptive identifiers, and filenames that match the surrounding modules. Configure an appropriate formatter and linter early, and document how contributors run them. Keep changes focused; avoid unrelated formatting edits.

## Testing Guidelines

Tests use pytest through the application's public HTTP interface and Playwright for browser-visible behavior, with real MongoDB in an isolated Docker environment. Assertions should observe external behavior rather than private helpers or database internals. Add automated tests alongside new behavior and bug fixes, organize them by feature, and document full-suite and individual-test commands. Test cleanup must remain isolated from the application's persistent volume.

## Commit & Pull Request Guidelines

Use concise, imperative commit subjects, such as `Add initial project configuration`. Pull requests should describe the change, its purpose, and verification performed. Link relevant issues and include screenshots for visible interface changes. Explicitly identify setup changes or checks that could not be run.

## Security & Configuration

Never commit credentials, access tokens, or local secrets. When configuration is introduced, provide example files with placeholder values and ignore local overrides and generated artifacts.

## Agent skills

### Issue tracker

Track issues and specs in this repository's GitHub Issues. Before reading or publishing tickets, follow `docs/agents/issue-tracker.md`.

### Triage labels

Use the default triage labels. Before assigning a triage status, read `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the repository root and decisions in `docs/adr/`. Before exploring the codebase, follow `docs/agents/domain.md`.
