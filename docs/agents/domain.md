# Domain Docs

This is a single-context repository: domain terms live in `GLOSSARY.md` at the repository root, and architecture decision records (ADRs) live in `docs/adr/`.

## Before exploring

- Read the root `GLOSSARY.md` when it exists.
- Read ADRs in `docs/adr/` that concern the area being explored.
- If these files do not exist, proceed silently. The `domain-modeling` skill creates them when terms or decisions are resolved.

## Use the glossary's vocabulary

When naming a domain concept in an issue, proposal, hypothesis, or test, use the term defined in `GLOSSARY.md`. If a concept is missing, reconsider whether it belongs to the project's language; note real gaps for `domain-modeling`.

## Surface ADR conflicts

If a proposal contradicts an existing ADR, identify the ADR and explain why the decision should be revisited before changing it.
