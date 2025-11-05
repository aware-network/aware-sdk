# Kernel Object Best Practices

These principles keep environment objects consistent across CLI, Studio, and providers. The thread object migration serves as the reference implementation.

## 1. Spec Modules Only
- Each object lives in `environments/aware_environments/kernel/objects/<object>/spec.py`.
- Use `ArgumentSpec` and `serialize_arguments` to describe CLI flags; keep selectors in the spec metadata, not in handlers.
- Publish pathspecs that map directly to the canonical filesystem layout (e.g. `thread-branches`, `thread-pane-manifests`).
- Run `ensure_paths_metadata` via the registry so downstream consumers receive canonical path metadata (hyphenated ids).

## 2. Handler Responsibilities
- Handlers must stay pure: validate inputs, call helper/adapters, return JSON-serialisable payloads.
- Encapsulate filesystem mutations inside `write_plan.py` modules so a single OperationPlan describes every change.
- Always include `receipts[]` and `journal[]` in mutation responses; include selectors and any derived identifiers (branch ids, participant ids).
- Reuse shared adapters (projects, tasks, conversations) rather than duplicating filesystem traversal logic.

## 3. Receipts Before Writes
- Mutation handlers call `OperationPlan.validate()` then `plan.apply()` only after the environment records a receipt.
- Pathspec IDs in ACL categories must align with the spec metadata (e.g. `creates`/`updates` lists).
- Return `access_paths` or `materialized_paths` for read operations when useful for audit.

## 4. Testing Discipline
- Provide dedicated handler tests in `environments/tests/` for every function, with fixture data under `tests/fixtures/<object>/`.
- Tests should assert payload structure, receipts content, and filesystem side effects.
- Add integration coverage in CLI tests that rely on the object to ensure end-to-end parity remains intact.

## 5. Migration Playbook
- Extract spec + handlers + write_plan.
- Register the new spec in `objects/__init__.py`; remove legacy inline entries.
- Switch CLI registration to `register_environment_objects`.
- Delete CLI-local specs after the executor path is proven; keep only argument transforms that call into the environment.

## 6. Documentation
- Record design intent under the owning task (e.g. `object-spec-project`) before implementing.
- Update this document whenever a new pattern emerges (thread is the current baseline, future objects should refine it rather than fork it).
