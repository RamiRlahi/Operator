"""
Human Checkpoint unit and integration tests for The Operator.
Validates:
1. Approved actions proceed and commit side effects.
2. Rejected actions halt execution and record operator rationale.
3. Decision history audit trail is maintained.
"""

import pytest
from agent.checkpoint import HumanCheckpoint
from agent.models import ToolCall
from agent.tools import ToolRegistry
from sandbox.environment import SandboxEnvironment


@pytest.fixture
def sandbox():
    env = SandboxEnvironment()
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
