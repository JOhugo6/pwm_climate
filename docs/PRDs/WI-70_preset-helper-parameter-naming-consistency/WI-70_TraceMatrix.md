# Requirement Traceability Matrix (FR -> Code -> Test)

This document ensures unambiguous traceability between requirements, implementation, review, and testing.

It is a mandatory control artifact for:

- code review
- testing
- quality audit
- process coordination

---

## Mandatory rules

- Each row in the FR table represents exactly one Functional Requirement.
- FR IDs must match the PRD verbatim.
- AC IDs must match the PRD verbatim.
- Grouping or merging FRs is forbidden.
- Every `.md` reference must be a Markdown link.
- Plain text `.md` file names are forbidden.
- Placeholder examples must not remain in a real artifact.
- The matrix file name must be `<PRD_NAME>_TraceMatrix.md`.
- If a CR artifact does not exist yet, the field must contain exactly `N/A (no CR artifact exists yet)`.
- If an approved CR artifact is not required yet, the field must contain exactly `N/A (not in CR -> QA stage)`.
- If an approved CR artifact is required but does not exist yet, the field must contain exactly `N/A (no APPROVED CR exists yet)`.
- This file is generated from the official template and must not be structurally modified.

---

## 1. Basic information

- Project name: `pwm_climate`
- PRD reference (Markdown link to PRD file): [WI-70_Implementation_Assignment.md](./WI-70_Implementation_Assignment.md)
- Corrective / revision PRD references (Markdown links, if any): N/A
- Latest CR report reference:
  - [WI-70_CR-01_20260421.md](./WI-70_CR-01_20260421.md)
- Latest APPROVED CR report reference:
  - [WI-70_CR-01_20260421.md](./WI-70_CR-01_20260421.md)
- Latest test report reference: [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md)
- Version: `0.1`
- Last updated: `2026-04-21`
- Owner: `SOFTWARE_ENGINEER`

---

## 2. Traceability rules

- Every Functional Requirement from the PRD:
  - must link to code
  - must link to at least one test when tested
- There is no:
  - code without an FR
  - test without an FR or AC
- Any missing mandatory link is a process failure.
- The exact Test Report file name must be recorded for every tested FR and AC.
- Recording only a test case ID or TR number is not sufficient.
- The latest CR report file must be recorded as a Markdown link.
- For `CR -> QA`, the latest approved CR report file must be recorded as a Markdown link.

---

## 3. Traceability Matrix - Functional Requirements

| FR ID (from PRD) | FR Description (verbatim from PRD) | Code Reference (file / module / class / method) | Commit / Ref | AC ID(s) (from PRD) | Test Case ID(s) | Test Report File (Markdown link) | Status |
|---|---|---|---|---|---|---|---|
| FR-70-01 | Choose one consistent parameter name for the external source mapping used by `_apply_flat_preset_temperatures()` and `_merge_preset_temperatures()`. | `custom_components/pwm_climate/preset_helpers.py :: _apply_flat_preset_temperatures(); _merge_preset_temperatures()` | `local worktree (uncommitted)` | `AC-70-01` | `QA-01` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | `TESTED_PASS` |
| FR-70-02 | Update the implementation so the chosen name is used consistently inside both helper bodies and any directly affected call sites or local references. | `custom_components/pwm_climate/preset_helpers.py :: _merge_preset_temperatures(); resolve_preset_temperatures()` | `local worktree (uncommitted)` | `AC-70-01`, `AC-70-02` | `QA-01` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | `TESTED_PASS` |
| FR-70-03 | Preserve the current behavior when the provided mapping is `None`, non-mapping, contains unknown keys, contains invalid temperature values, or mixes preset ids and preset labels. | `custom_components/pwm_climate/preset_helpers.py :: _apply_flat_preset_temperatures(); _merge_preset_temperatures()` | `local worktree (uncommitted)` | `AC-70-02`, `AC-70-03` | `QA-01`, `QA-02` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | `TESTED_PASS` |
| FR-70-04 | `resolve_preset_temperatures()` must continue to apply defaults first, then overlay entry data, then overlay entry options, with options taking precedence. | `custom_components/pwm_climate/preset_helpers.py :: resolve_preset_temperatures()` | `local worktree (uncommitted)` | `AC-70-02`, `AC-70-03` | `QA-01`, `QA-02` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | `TESTED_PASS` |
| FR-70-05 | No public API or config schema change may result from this WI. This remains a naming consistency cleanup only. | `custom_components/pwm_climate/preset_helpers.py` | `local worktree (uncommitted)` | `AC-70-01`, `AC-70-02`, `AC-70-04` | `QA-01`, `QA-02`, `QA-03` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | `TESTED_PASS` |

Status legend:

- `NOT_IMPLEMENTED`
- `IMPLEMENTED_NOT_TESTED`
- `TESTED_PASS`
- `TESTED_FAIL`

---

## 4. Traceability Matrix - Acceptance Criteria

| AC ID (from PRD) | AC Description (verbatim from PRD) | Related FR ID(s) | Test Case ID | Test Report File (Markdown link) | Test Result | Status |
|---|---|---|---|---|---|---|
| AC-70-01 | The preset helper functions use consistent parameter naming for their external source mapping. | `FR-70-01`, `FR-70-02`, `FR-70-05` | `QA-01` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | PASS | `TESTED_PASS` |
| AC-70-02 | Runtime behavior of `resolve_preset_temperatures()` remains unchanged across defaults, entry data, and entry options overlays. | `FR-70-03`, `FR-70-04`, `FR-70-05` | `QA-01`, `QA-02` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | PASS | `TESTED_PASS` |
| AC-70-03 | Relevant repo-local tests pass after the cleanup. | `FR-70-03`, `FR-70-04` | `QA-01`, `QA-02` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | PASS | `TESTED_PASS` |
| AC-70-04 | Docker smoke validation completes without introducing a startup regression. | `FR-70-05` | `QA-03` | [WI-70_TR-01_20260421.md](./WI-70_TR-01_20260421.md) | PASS | `TESTED_PASS` |

Each AC must be covered by at least one test before final completion.

---

## 5. Code without requirement

| File / Module | Description | Reason |
|---|---|---|
| None | N/A | WI-70 implementation changes map directly to FR-70 requirements. |

If this table is not empty, the change set must be reviewed explicitly.

---

## 6. Test without requirement

| Test Case ID | Description | Reason |
|---|---|---|
| None | N/A | The added regression tests map directly to the WI-70 preset helper cleanup. |

If this table is not empty, the test scope must be reviewed explicitly.

---

## 7. Coverage summary

- Total FR count: `5`
- FR covered by code: `5`
- FR covered by tests: `5`
- FR without tests: `0`
- FR without implementation: `0`

---

## 8. Final evaluation

A validation cycle is incomplete if any tested FR or AC does not contain an exact Test Report reference.

### Traceability status

- [x] COMPLETE
- [ ] INCOMPLETE
- [ ] FAILED

### Notes

- Identified gaps: `None`
- Risks: `None`
- Recommendations: `QA traceability is complete for WI-70; no additional action is required unless a retest is requested.`
