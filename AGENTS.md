# Codex Project Instructions

These instructions are part of the repository and should guide future Codex work.

## Documentation Source of Truth

- Use `README.md` as the entry point.
- Use `docs/PROJECT_OVERVIEW.md` for current state.
- Use `docs/SYSTEM_FLOW.md` for pipeline flow.
- Use `docs/GENERATION_TO_BACKEND_VALUATION.md` for the generation-to-backend valuation bridge.
- Use `docs/MANUAL_SETUP.md` for setup.
- Use `docs/REVIEW_PROTOCOL.md` for implementation and review rules.
- Use `TODO.md` as the single live backlog.

## TODO Rule

Whenever a task completes an item from `TODO.md`, update `TODO.md` in the same change. If the task changes setup, flow, architecture, valuation behavior, or review rules, update the matching file in `docs/` too.

Before starting any new user-requested task:

- Discuss the request with the user first and confirm the intended scope before implementation.
- Check `TODO.md` for unfinished related items.
- If related unfinished work exists, surface it to the user and agree whether to continue, defer, or adjust scope.
- Add the new task or subtask to `TODO.md` before implementation unless it is a trivial documentation-only correction.
- Keep `TODO.md` current while working, not only at the end.

After finishing any task:

- Update `TODO.md`.
- Update the relevant files among `README.md`, `docs/PROJECT_OVERVIEW.md`, `docs/SYSTEM_FLOW.md`, `docs/GENERATION_TO_BACKEND_VALUATION.md`, `docs/MANUAL_SETUP.md`, and `docs/REVIEW_PROTOCOL.md` when the task changes behavior, setup, flow, architecture, or review rules.
- Report any unfinished related TODO items that still block the next step.

## Code Comments

- Write explanatory code comments in Arabic when adding comments to new or changed code.
- Keep comments concise and useful. Do not add comments that merely restate obvious code.
- Preserve existing English comments unless changing the surrounding code makes an Arabic replacement clearer.

## Architecture Rules

- Do not mix raw payloads, verified facts, derived signals, classification results, valuation runs, AI explanations, and reports.
- Legacy root `scoring/` output may feed backend as `derived_signals`, not as verified facts.
- Backend valuation must require classification before returning priced output.
- AI explanations are report prose only; they are not facts and must not be valuation evidence by themselves.
- Keep the Streamlit trend pipeline working while adding backend integration.

## Manual Gates

Ask before changing schema shape, enum semantics, valuation thresholds, scraping behavior, auth/org boundaries, or data retention policy.
