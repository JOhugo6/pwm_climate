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
- PRD reference (Markdown link to PRD file): [WI-72_Implementation_Assignment.md](./WI-72_Implementation_Assignment.md)
- Corrective / revision PRD references (Markdown links, if any): N/A
- Latest CR report reference:
  - [WI-72_CR-04_20260421.md](./WI-72_CR-04_20260421.md)
- Latest APPROVED CR report reference:
  - [WI-72_CR-04_20260421.md](./WI-72_CR-04_20260421.md)
- Latest test report reference: [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md)
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
| FR-72-01 | `PWMClimateController` must expose `DeviceInfo` so Home Assistant can register the entity in device registry. | `custom_components/pwm_climate/climate.py :: PWMClimateController.__init__()` | `local worktree (uncommitted)` | `AC-72-01`, `AC-72-04` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `TESTED_PASS` |
| FR-72-02 | The device registration metadata must be stable across restarts for the same config entry and must not create duplicate devices for an unchanged entity. | `custom_components/pwm_climate/climate.py :: PWMClimateController.__init__()` | `local worktree (uncommitted)` | `AC-72-01`, `AC-72-02`, `AC-72-04` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `TESTED_PASS` |
| FR-72-03 | The chosen device identifiers or related registration keys must be derived from repository-local stable data such as domain and config-entry identity, not from volatile runtime state. | `custom_components/pwm_climate/climate.py :: PWMClimateController.__init__()` | `local worktree (uncommitted)` | `AC-72-01`, `AC-72-02` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `TESTED_PASS` |
| FR-72-04 | Device registration must preserve the current entity unique ID and must not break existing entity registry continuity for valid installs. | `custom_components/pwm_climate/climate.py :: PWMClimateController.__init__()` | `local worktree (uncommitted)` | `AC-72-03`, `AC-72-04` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `TESTED_PASS` |
| FR-72-05 | The entity must remain fully operational when device metadata is present; no change is allowed to HVAC behavior, presets, output calculation, or listener flow. | `custom_components/pwm_climate/climate.py :: PWMClimateController.__init__(); tests/test_climate.py` | `local worktree (uncommitted)` | `AC-72-03`, `AC-72-04`, `AC-72-05` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `TESTED_PASS` |
| FR-72-06 | If manufacturer, model, or name metadata is provided, it must be consistent with the integration's identity and not contradict manifest or entity naming. | `custom_components/pwm_climate/climate.py :: PWMClimateController.__init__()` | `local worktree (uncommitted)` | `AC-72-01`, `AC-72-03`, `AC-72-04` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `TESTED_PASS` |
| FR-72-07 | No user-visible config flow, duplicate prevention, or reconfiguration behavior may change for this WI. | `custom_components/pwm_climate/config_flow.py` (unchanged in WI-72 scope) | `local worktree (uncommitted)` | `AC-72-03`, `AC-72-05` | `QA-02`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `TESTED_PASS` |

Status legend:

- `NOT_IMPLEMENTED`
- `IMPLEMENTED_NOT_TESTED`
- `TESTED_PASS`
- `TESTED_FAIL`

---

## 4. Traceability Matrix - Acceptance Criteria

| AC ID (from PRD) | AC Description (verbatim from PRD) | Related FR ID(s) | Test Case ID | Test Report File (Markdown link) | Test Result | Status |
|---|---|---|---|---|---|---|---|
| AC-72-01 | `PWMClimateController` exposes `DeviceInfo` and registers as a Home Assistant device. | `FR-72-01`, `FR-72-02`, `FR-72-03`, `FR-72-06` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `PASS` | `TESTED_PASS` |
| AC-72-02 | Device registration uses stable metadata and does not create duplicate devices for unchanged config entries. | `FR-72-02`, `FR-72-03` | `QA-01`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `PASS` | `TESTED_PASS` |
| AC-72-03 | Existing climate-entity runtime behavior remains unchanged from the user perspective aside from improved device grouping in UI. | `FR-72-04`, `FR-72-05`, `FR-72-07` | `QA-01`, `QA-02`, `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `PASS` | `TESTED_PASS` |
| AC-72-04 | Automated tests covering device metadata exposure and identifier stability are added and executed. | `FR-72-01`, `FR-72-02`, `FR-72-03`, `FR-72-04`, `FR-72-06` | `QA-01`, `QA-02` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `PASS` | `TESTED_PASS` |
| AC-72-05 | Docker smoke validation completes without introducing a new startup or entity regression. | `FR-72-04`, `FR-72-05`, `FR-72-07` | `QA-03` | [WI-72_TR-01_20260421.md](./WI-72_TR-01_20260421.md) | `PASS` | `TESTED_PASS` |

Each AC must be covered by at least one test before final completion.

---

## 5. Code without requirement

| File / Module | Description | Reason |
|---|---|---|
| None | N/A | WI-72 implementation changes map directly to FR-72 requirements. |

If this table is not empty, the change set must be reviewed explicitly.

---

## 6. Test without requirement

| Test Case ID | Description | Reason |
|---|---|---|
| None | N/A | The added device-info tests map directly to WI-72 FR/AC coverage, and the remaining climate tests continue to exercise unchanged runtime behavior. |

If this table is not empty, the test scope must be reviewed explicitly.

---

## 7. Coverage summary

- Total FR count: `7`
- FR covered by code: `7`
- FR covered by tests: `7`
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

- Identified gaps: `None. WI-72 QA cycle completed with published TR evidence and matching traceability links.`
- Risks: `None identified in this validation cycle.`
- Recommendations: `Keep the published TR linked here as the formal QA record for this WI.`
