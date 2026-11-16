"""
Human Checkpoint unit and integration tests for The Operator.
Validates:
1. Approved actions proceed and commit side effects.
2. Rejected actions halt execution and record operator rationale.
3. Decision history audit trail is maintained.
"""

import pytest
from unittest.mock import Mock
from agent.checkpoint import HumanCheckpoint
from agent.models import ToolCall
from agent.tools import ToolRegistry
from sandbox.environment import SandboxEnvironment


@pytest.fixture
def sandbox(tmp_path):
    env = SandboxEnvironment(tmp_path / "test.db")
    env.reset()
    yield env
    env.close()


def test_checkpoint_approval_allows_write(sandbox):
    cp = HumanCheckpoint(mode="headless", auto_approve=True)
    tools = ToolRegistry(sandbox, checkpoint_handler=cp.request_approval)

    call = ToolCall(
        name="execute_action",
        arguments={
            "ticket_id": "TKT-101",
            "action_type": "CANCEL_ORDER",
            "payload": {"order_id": "ORD-502"},
            "idempotency_key": "IDEMP-CANCEL-ORD-502",
        },
    )

    result = tools.execute(call)
    assert not result.is_error
    assert "committed in sandbox" in result.output
    assert len(cp.decision_history) == 1
    assert cp.decision_history[0]["approved"] is True


def test_checkpoint_rejection_blocks_write(sandbox):
    cp = HumanCheckpoint(mode="headless", auto_approve=False)
    tools = ToolRegistry(sandbox, checkpoint_handler=cp.request_approval)

    call = ToolCall(
        name="execute_action",
        arguments={
            "ticket_id": "TKT-101",
            "action_type": "CANCEL_ORDER",
            "payload": {"order_id": "ORD-502"},
            "idempotency_key": "IDEMP-CANCEL-ORD-502-REJECT",
        },
    )

    result = tools.execute(call)
    assert result.is_error
    assert result.error_type == "UserRejectionError"
    assert "Human Checkpoint DENIED action" in result.output

    # Verify action was NOT committed to the database
    conn = sandbox.get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM executed_actions WHERE idempotency_key = 'IDEMP-CANCEL-ORD-502-REJECT'")
    assert c.fetchone()[0] == 0


@pytest.mark.parametrize("approval", [None, False, True])
@pytest.mark.parametrize(
    ("tool_name", "arguments", "action_type", "query", "baseline", "after_write"),
    [
        ("update_ticket_status", {"status": "ESCALATED", "tags": ["review"]},
         "UPDATE_TICKET_STATUS", "SELECT status FROM tickets WHERE ticket_id = 'TKT-101'", "OPEN", "ESCALATED"),
        ("draft_reply", {"recipient": "alice@example.com", "subject": "Review", "body": "We are reviewing this."},
         "DRAFT_REPLY", "SELECT COUNT(*) FROM drafts", 0, 1),
        ("execute_action", {"action_type": "ISSUE_REFUND", "payload": {"amount": 10.0}, "idempotency_key": "refund-1"},
         "ISSUE_REFUND", "SELECT COUNT(*) FROM executed_actions", 0, 1),
    ],
)
def test_every_new_write_requires_approval(sandbox, approval, tool_name, arguments, action_type, query, baseline, after_write):
    connection = sandbox.get_connection()

    def approve(**proposal):
        assert proposal["ticket_id"] == "TKT-101"
        assert proposal["action_type"] == action_type
        assert connection.execute(query).fetchone()[0] == baseline
        return approval, "Test review"

    handler = Mock(side_effect=approve) if approval is not None else None
    tools = ToolRegistry(sandbox, checkpoint_handler=handler)
    call = ToolCall(name=tool_name, arguments={"ticket_id": "TKT-101", **arguments})
    result = tools.execute(call)

    if approval:
        assert not result.is_error
        assert connection.execute(query).fetchone()[0] == after_write
        assert not tools.execute(call).is_error
        assert connection.execute(query).fetchone()[0] == after_write
    else:
        assert result.error_type == "UserRejectionError"
        assert connection.execute(query).fetchone()[0] == baseline

    if handler is not None:
        handler.assert_called_once()
