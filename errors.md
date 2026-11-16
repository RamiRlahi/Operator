# Error taxonomy

| Condition | Agent behaviour | Evidence |
|---|---|---|
| Bad arguments or malformed output | Reject invalid input without a side effect. Supply a format or validation observation and consume one model attempt. | SCN-025 and `tests/test_error_recovery.py` |
| Empty result | A missing ticket ends with a lookup message. An empty knowledge-base result can trigger a broader search. | SCN-014 and SCN-028 |
| Unknown tool | Return an error listing registered tools. Dispatch only allowlisted functions. | `test_error_class_wrong_tool` |
| Policy or security violation | Reject invalid refunds, ineligible orders, wrong recipients and cross-ticket requests before a write. | `test_invalid_operational_action_stops_before_approval` |
| Tool unavailable or timeout | Return a typed, concise error. The offline model retries transient ticket reads within the attempt bound. | SCN-029 |
| Human refuses or closes input | End the run as `HUMAN_REJECTED`. The refused write has no effect. An earlier approved write remains committed. | SCN-026 and `tests/test_checkpoint.py` |
| Duplicate or partial write | Use an idempotency key and a transaction for operational actions. A failure rolls back the row and associated side effect together. Use the same key to retry an approved operation. | SCN-027 and `tests/test_idempotency.py` |
| Repeated steps or resource limit | Count attempts before every request. Stop on a repeating action, the hard attempt bound or the estimated spend threshold. | SCN-031 to SCN-035 and `tests/test_stopping_condition.py` |
| Provider failure | Return a concise failure status. SDK retries are disabled. | `tests/test_live_configuration.py` verifies provider configuration using a mock transport. |

The offline run recovers from three deliberately injected faults. The refusal, repeated write and stop-rule cases are measured separately from that recovery fraction.
