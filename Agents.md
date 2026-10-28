# PocketAgent — Project Instructions

## Objective
Build a privacy-focused, offline-first AI assistant for Windows and Android.

## Development principles
- Prefer the simplest working implementation.
- Use local inference for all core AI features.
- Never introduce a paid API dependency for core functionality.
- Reuse shared UI and business logic where practical.
- Keep platform-specific inference behind a clearly defined interface.
- Avoid unnecessary dependencies and large architectural rewrites.

## Workflow
1. Inspect existing files before modifying them.
2. State the implementation plan briefly.
3. Make small, focused changes.
4. Run relevant tests and builds after changes.
5. Report the actual results, failures and unresolved issues.
6. Commit only after reviewing the diff and confirming tests pass.
7. Never claim a feature works offline until it has been tested without network access.

## Cost control
- Prefer lower-cost models for routine implementation tasks.
- Reserve stronger reasoning for difficult architectural decisions or persistent bugs.
- Avoid repeating full-repository analysis when a focused file inspection is enough.
- Do not run unnecessary downloads, builds or long-running tests.
- Never purchase services, upgrade subscriptions or enable paid APIs without explicit approval.

## Safety
- Do not expose API keys or secrets.
- Validate agent tool inputs.
- Require confirmation before destructive file operations.
- Never execute arbitrary model-generated shell commands without user approval.

## Definition of done
A feature is complete only when its implementation, tests, limitations and setup instructions are documented.