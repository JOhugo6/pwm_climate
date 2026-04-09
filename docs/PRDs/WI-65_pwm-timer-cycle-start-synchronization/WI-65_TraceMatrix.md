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
- PRD reference (Markdown link to PRD file): [WI-65_Implementation_Assignment.md](./WI-65_Implementation_Assignment.md)
- Corrective / revision PRD references (Markdown links, if any): N/A
- Latest CR report reference:
  - [WI-65_CR-01_20260409.md](./WI-65_CR-01_20260409.md)
- Latest APPROVED CR report reference:
  - [WI-65_CR-01_20260409.md](./WI-65_CR-01_20260409.md)
- Latest test report reference: [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md)
- Version: `0.1`
- Last updated: `2026-04-09`
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
| FR-65-01 | SoftwarePWMTimer.apply() and _async_pwm_loop() must no longer observe a partially updated timing configuration where new duty/period fields are combined with a stale _cycle_start. | `custom_components/pwm_climate/pwm_timer.py :: _PWMTimingSnapshot; SoftwarePWMTimer.apply(); SoftwarePWMTimer._async_pwm_loop()` | `local worktree (uncommitted)` | `AC-65-01` | `TC-WI65-01`, `TC-WI65-02` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | TESTED_PASS |
| FR-65-02 | When a restart-triggering change occurs, the timer must publish a self-consistent cycle snapshot so the next phase calculation uses matching values for period, duty, on-time, off-time, and cycle start. | `custom_components/pwm_climate/pwm_timer.py :: _PWMTimingSnapshot; SoftwarePWMTimer.apply()` | `local worktree (uncommitted)` | `AC-65-02` | `TC-WI65-01`, `TC-WI65-03` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | TESTED_PASS |
| FR-65-03 | The fix must preserve current behavior for the stable 0% and 100% duty paths: fixed OFF and fixed ON must continue to bypass the PWM loop as they do today. | `custom_components/pwm_climate/pwm_timer.py :: SoftwarePWMTimer.apply(); SoftwarePWMTimer._async_set_stable_output()` | `local worktree (uncommitted)` | `AC-65-03` | `TC-WI65-04` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | TESTED_PASS |
| FR-65-04 | For non-trivial PWM duty ratios, the timer must continue to restart the cycle immediately when required by a duty, period, or forced restart change. | `custom_components/pwm_climate/pwm_timer.py :: SoftwarePWMTimer.apply()` | `local worktree (uncommitted)` | `AC-65-02` | `TC-WI65-01`, `TC-WI65-03` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | TESTED_PASS |
| FR-65-05 | The background loop must continue responding to _update_event notifications without indefinite waiting or deadlock. | `custom_components/pwm_climate/pwm_timer.py :: SoftwarePWMTimer._async_pwm_loop(); SoftwarePWMTimer._async_wait_for_update()` | `local worktree (uncommitted)` | `AC-65-01`, `AC-65-02` | `TC-WI65-02` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | TESTED_PASS |
| FR-65-06 | The fix must not require callers such as custom_components/pwm_climate/climate.py to change how they invoke SoftwarePWMTimer.apply(). | `custom_components/pwm_climate/pwm_timer.py :: SoftwarePWMTimer.apply()` | `local worktree (uncommitted)` | `AC-65-01`, `AC-65-02` | `TC-WI65-01`, `TC-WI65-03` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | TESTED_PASS |
| FR-65-07 | No user-visible configuration behavior may change. Config flow, duplicate prevention, and reconfiguration behavior remain unchanged for this WI. | `custom_components/pwm_climate/config_flow.py` (unchanged in WI-65 scope) | `local worktree (uncommitted)` | `AC-65-05` | `TC-WI65-05` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | TESTED_PASS |

Status legend:

- `NOT_IMPLEMENTED`
- `IMPLEMENTED_NOT_TESTED`
- `TESTED_PASS`
- `TESTED_FAIL`

---

## 4. Traceability Matrix - Acceptance Criteria

| AC ID (from PRD) | AC Description (verbatim from PRD) | Related FR ID(s) | Test Case ID | Test Report File (Markdown link) | Test Result | Status |
|---|---|---|---|---|---|---|
| AC-65-01 | The PWM timer no longer exposes a race window where _async_pwm_loop() can calculate phase using mixed old/new timing state around _cycle_start. | `FR-65-01`, `FR-65-05`, `FR-65-06` | `TC-WI65-01`, `TC-WI65-02` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | PASS | TESTED_PASS |
| AC-65-02 | Restart-triggering updates publish a coherent cycle snapshot and preserve the intended immediate-restart semantics. | `FR-65-02`, `FR-65-04`, `FR-65-06` | `TC-WI65-01`, `TC-WI65-03` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | PASS | TESTED_PASS |
| AC-65-03 | Stable OFF and stable ON paths continue to behave as before from the user perspective. | `FR-65-03` | `TC-WI65-04` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | PASS | TESTED_PASS |
| AC-65-04 | Automated tests covering timer restart coherence are added and executed. | `FR-65-01`, `FR-65-02`, `FR-65-03`, `FR-65-04` | `TC-WI65-01`, `TC-WI65-02`, `TC-WI65-03`, `TC-WI65-04` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | PASS | TESTED_PASS |
| AC-65-05 | Docker smoke validation completes without introducing a new startup or PWM runtime regression for the integration. | `FR-65-07` | `TC-WI65-05` | [WI-65_TR-01_20260409.md](./WI-65_TR-01_20260409.md) | PASS | TESTED_PASS |

Each AC must be covered by at least one test before final completion.

---

## 5. Code without requirement

| File / Module | Description | Reason |
|---|---|---|
| None | N/A | WI-65 implementation changes map directly to FR-65 requirements. |

If this table is not empty, the change set must be reviewed explicitly.

---

## 6. Test without requirement

| Test Case ID | Description | Reason |
|---|---|---|
| None | N/A | Added WI-65 timer tests map directly to WI-65 FR/AC coverage. |

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

- Identified gaps: None.
- Risks: `docs/` is ignored by `.gitignore`, so the QA artifacts are local workspace files and do not appear in `git status`.
- Recommendations: None.
