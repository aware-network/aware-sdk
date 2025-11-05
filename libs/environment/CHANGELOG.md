# Changelog

# Changelog

## 0.1.3 - 2025-11-05
- Cleanup - Decouple from kernel. No functional changes.

## 0.1.2 - 2025-11-05
- Added `PatchInstruction` support to OperationPlans so diffs execute through the shared filesystem executor.
- Extended receipts to record `diff_hash` metadata for patch operations.
- Exposed environment-level `apply_patch` handler to generate patch plans for CLI and Studio clients.
- Rewired CLI apply tests to cover the new environment-driven flow.

## 0.1.1 - 2025-11-05
- Added MIT license, publishable metadata, and README guidance for open-source distribution.
- Documented constitution-aware rendering and runtime usage patterns.

## 0.1.0 - 2025-10-26
- Introduced core registries for agents, roles, rules, and objects.
- Added `Environment` container to aggregate registries.
