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
- PRD reference (Markdown link to PRD file): [WI-63_Implementation_Assignment.md](./WI-63_Implementation_Assignment.md)
- Corrective / revision PRD references (Markdown links, if any): N/A
- Latest CR report reference:
  - [WI-63_CR-01_20260409.md](./WI-63_CR-01_20260409.md)
- Latest APPROVED CR report reference:
  - [WI-63_CR-01_20260409.md](./WI-63_CR-01_20260409.md)
- Latest test report reference: [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md)
- Version: `0.2`
- Last updated: `2026-04-09`
- Owner: `TESTER`

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
| FR-63-01 | PWMOutputAdapter._async_call_service() must no longer use a blanket except Exception branch that classifies every non-timeout failure as a recoverable output-write failure. | `custom_components/pwm_climate/output_adapter.py :: PWMOutputAdapter._async_call_service()` | `local worktree (uncommitted)` | `AC-63-01` | `TC-WI63-01`, `TC-WI63-02`, `TC-WI63-03` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |
| FR-63-02 | The implementation must distinguish between explicitly recoverable service execution failures and unexpected runtime/programmer faults. Only the approved recoverable failure set may be converted into a False return value. | `custom_components/pwm_climate/output_adapter.py :: PWMOutputAdapter._async_call_service()` | `local worktree (uncommitted)` | `AC-63-02`, `AC-63-04` | `TC-WI63-01`, `TC-WI63-02` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |
| FR-63-03 | asyncio.CancelledError or equivalent task-cancellation signals raised while the adapter is waiting on a Home Assistant service call must propagate to the caller and must not be logged as an ordinary service-call failure. | `custom_components/pwm_climate/output_adapter.py :: PWMOutputAdapter._async_call_service()` | `local worktree (uncommitted)` | `AC-63-05` | `TC-WI63-03` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |
| FR-63-04 | Timeout behavior introduced by WI #61 must remain intact: a timed-out service call must log actionable context and return False without indefinite waiting. | `custom_components/pwm_climate/output_adapter.py :: _DEFAULT_SERVICE_CALL_TIMEOUT; PWMOutputAdapter._async_call_service()` | `local worktree (uncommitted)` | `AC-63-03` | `TC-WI63-04` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |
| FR-63-05 | When a recoverable service-call failure occurs, the adapter must emit a clear error record that identifies the target entity and the attempted domain.service. | `custom_components/pwm_climate/output_adapter.py :: PWMOutputAdapter._async_call_service()` | `local worktree (uncommitted)` | `AC-63-02` | `TC-WI63-01` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |
| FR-63-06 | Successful service calls must preserve the current success path, including the caller-level cache update behavior used by binary, number, and climate output modes. | `custom_components/pwm_climate/output_adapter.py :: PWMOutputAdapter._async_set_binary_output(); PWMOutputAdapter._async_set_number_output(); PWMOutputAdapter._async_set_climate_output()` | `local worktree (uncommitted)` | `AC-63-06` | `TC-WI63-06` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |
| FR-63-07 | Recoverable failure behavior must apply uniformly to every output mode that routes through _async_call_service(): _async_set_binary_output(), _async_set_number_output(), and _async_set_climate_output(). | `custom_components/pwm_climate/output_adapter.py :: PWMOutputAdapter._async_set_binary_output(); PWMOutputAdapter._async_set_number_output(); PWMOutputAdapter._async_set_climate_output(); PWMOutputAdapter._async_call_service()` | `local worktree (uncommitted)` | `AC-63-02`, `AC-63-06` | `TC-WI63-05` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |
| FR-63-08 | No user-visible configuration behavior may change. Duplicate prevention in config flow remains unchanged, and no reconfiguration flow is required for this fix. | `custom_components/pwm_climate/config_flow.py` (unchanged in WI-63 scope) | `local worktree (uncommitted)` | `AC-63-07` | `TC-WI63-07` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | TESTED_PASS |

Status legend:

- `NOT_IMPLEMENTED`
- `IMPLEMENTED_NOT_TESTED`
- `TESTED_PASS`
- `TESTED_FAIL`

---

## 4. Traceability Matrix - Acceptance Criteria

| AC ID (from PRD) | AC Description (verbatim from PRD) | Related FR ID(s) | Test Case ID | Test Report File (Markdown link) | Test Result | Status |
|---|---|---|---|---|---|---|
| AC-63-01 | The blanket except Exception handling in PWMOutputAdapter._async_call_service() is replaced by explicit recoverable-failure handling. | `FR-63-01` | `TC-WI63-01`, `TC-WI63-02`, `TC-WI63-03` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | `PASS (QA pytest rerun confirmed recoverable, unexpected, and cancellation paths are explicitly separated)` | TESTED_PASS |
| AC-63-02 | Recoverable service-call failures still produce an actionable log and a controlled False return to the caller. | `FR-63-02`, `FR-63-05`, `FR-63-07` | `TC-WI63-01`, `TC-WI63-05` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | `PASS (recoverable HomeAssistantError path logged actionable context and caller cache remained unchanged across output modes)` | TESTED_PASS |
| AC-63-03 | Timeout handling from WI #61 continues to behave as before and remains covered by automated tests. | `FR-63-04` | `TC-WI63-04` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | `PASS (timeout regression test remained green in QA pytest reruns)` | TESTED_PASS |
| AC-63-04 | Unexpected exception types are no longer silently swallowed as ordinary output failures. | `FR-63-02` | `TC-WI63-02` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | `PASS (unexpected RuntimeError propagated instead of being downgraded to False)` | TESTED_PASS |
| AC-63-05 | asyncio.CancelledError propagates correctly during service-call cancellation. | `FR-63-03` | `TC-WI63-03` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | `PASS (CancelledError propagation verified in QA pytest rerun)` | TESTED_PASS |
| AC-63-06 | Automated tests covering recoverable failures, unexpected exceptions, and cancellation are added and executed. | `FR-63-06`, `FR-63-07` | `TC-WI63-01`, `TC-WI63-02`, `TC-WI63-03`, `TC-WI63-05`, `TC-WI63-06` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | `PASS (targeted and full pytest runs both passed: 17 tests green)` | TESTED_PASS |
| AC-63-07 | Docker smoke validation completes without introducing a new startup regression for the integration. | `FR-63-08` | `TC-WI63-07` | [WI-63_TR-01_20260409.md](./WI-63_TR-01_20260409.md) | `PASS (Docker boot/restart, HTTP 200, persisted pwm_climate entry, and clean pwm_climate startup logs verified)` | TESTED_PASS |

Each AC must be covered by at least one test before final completion.

---

## 5. Code without requirement

| File / Module | Description | Reason |
|---|---|---|
| None | N/A | WI-63 implementation changes map directly to FR-63 requirements. |

If this table is not empty, the change set must be reviewed explicitly.

---

## 6. Test without requirement

| Test Case ID | Description | Reason |
|---|---|---|
| None | N/A | Added/updated tests map directly to WI-63 FR/AC coverage. |

If this table is not empty, the test scope must be reviewed explicitly.

---

## 7. Coverage summary

- Total FR count: `8`
- FR covered by code: `8`
- FR covered by tests: `8`
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

- Identified gaps: `None for the planned WI-63 QA scope.`
- Risks: Docker smoke validated boot/restart persistence and clean startup logs, but it did not attempt to synthesize a live recoverable service-call failure inside Home Assistant; that behavior remains covered by repo-local pytest.
- Recommendations: Optional future smoke enhancement: add a dedicated HA-side fault-injection harness if the project wants runtime evidence for recoverable service-call exceptions beyond unit-test coverage.
