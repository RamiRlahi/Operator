# Error Taxonomy & Failure Recovery

This document categorizes all runtime and tool failure modes for **The Operator**, detailing the operational failure condition, the agent's automated recovery strategy, and the corresponding regression test verifying safe handling.

---

## Error Classes & Recovery Strategies

| Error Class | Root Cause | Observable Behavior | Agent Recovery Strategy | Test Case |
|---|---|---|---|---|
| **1. BadArgumentsError** | Model produces malformed JSON or omits required Pydantic schema parameters. | `ToolResult.is_error = True`, clear error message: `"Bad arguments error for tool '...' : field required"`. Zero stack traces. | The agent inspects the missing/invalid field in the observation turn, corrects parameter formatting, and re-invokes the tool. | `tests/test_error_recovery.py::test_error_class_bad_arguments` |
| **2. EmptyResultError** | Querying a non-existent ticket ID (`TKT-999`) or an unmatched knowledge base query. | Database returns 0 rows. Observation yields: `"Error: Ticket 'TKT-999' not found in database"`. | Agent catches diagnostic message, re-queries unread tickets or broadens KB search query category (billing, security, shipping). | `tests/test_error_recovery.py::test_error_class_empty_result` |
| **3. WrongToolError** | Model attempts to call an unregistered tool name or calls write tools without proper context. | Registry returns: `"Error: Unknown tool '...'. Available tools: [...]"`. | Agent parses the available tools list from the observation and selects the correct tool. | `tests/test_error_recovery.py::test_error_class_wrong_tool` |
| **4. PolicyViolationError** | Refund amount exceeds max authorized limit ($150.00) or order is already delivered. | Tool rejects write with: `"Policy violation: Requested refund of $X exceeds operator limit of $150.00"`. | Agent halts automated financial execution, tags ticket as `exceeds_threshold`, and updates ticket status to `ESCALATED` for human supervisor review. | `tests/test_error_recovery.py::test_error_class_policy_violation` |
| **5. SecurityViolationError** | Customer requests password reset to an unverified third-party email. | Tool halts action: `"Security policy violation: Cannot send password reset to '...' (must match registered email)"`. | Agent flags ticket with `security_risk`, refrains from sending credentials, and escalates ticket. | `tests/test_error_recovery.py::test_error_class_security_violation` |
| **6. UserRejectionError (User Changes Mind)** | Human operator denies write authorization at the checkpoint gate (`[N]` or custom rationale). | Checkpoint returns: `"Human Checkpoint DENIED action ... Reason: [...]"`. | Agent immediately terminates write side effects, records operator rationale, marks trajectory as `HUMAN_REJECTED`, and halts without state corruption. | `tests/test_error_recovery.py::test_error_class_user_rejection` |
| **7. InfiniteLoopError (Cycle)** | Model gets trapped repeating the exact same tool and arguments indefinitely. | Loop cycle detector flags matching consecutive action signatures. | Agent terminates with status `STOPPED_CYCLE`, logs error summary, and prevents infinite token burn. | `tests/test_stopping_condition.py::test_stopping_condition_cycle_detector_proof` |
| **8. TimeoutBudgetError** | Task exceeds step ceiling (10 steps) or token monetary budget ($0.25). | Loop bounds evaluator intercepts turn execution. | Intercepts turn, sets status to `STOPPED_MAX_STEPS` or `STOPPED_BUDGET`, and emits structured trajectory log. | `tests/test_stopping_condition.py::test_stopping_condition_budget_cap_proof` |

---

## Recovery-After-Failure Measurement

In the benchmark evaluation suite (`eval/runner.py`), failure recovery was evaluated across **Cohort D (Scenarios SCN-025 to SCN-030)**:

- **Total Recovery Test Scenarios**: 6
- **Successful Recoveries**: 6 / 6
- **Recovery-After-Failure Rate**: **100.0%**

### Key Takeaway
Stack traces are strictly intercepted at the `ToolRegistry` boundary. The agent is never exposed to raw Python runtime exceptions. By receiving actionable plain-text diagnostics (e.g., `"Bad arguments error: Missing field 'query'"`), the agent self-corrects parameter schemas within a single follow-up turn.
