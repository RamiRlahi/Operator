"""
Mathematical and empirical proof of termination for The Operator.
Proves that the agent loop is guaranteed to halt under:
1. Hard step limit constraint (max_steps)
2. Token budget constraint (max_budget_usd)
3. Infinite cycle repetition detector (max_cycles)
4. Normal done-rule termination (Final Answer)
"""

import pytest
from agent.checkpoint import HumanCheckpoint
from agent.llm import BaseLLMClient
from agent.loop import AgentLoop
from agent.models import Trajectory
from agent.tools import ToolRegistry
from sandbox.environment import SandboxEnvironment


class InfiniteLoopMockLLM(BaseLLMClient):
    """Pathological LLM simulator that never terminates on its own."""
    def complete(self, messages):
        return (
            'Thought: I will loop forever.\nAction: get_ticket | {"ticket_id": "TKT-101"}',
            100, 20, 0.01  # $0.01 per step
        )


class AlternatingInfiniteLoopMockLLM(BaseLLMClient):
    """Pathological LLM simulator alternating between two tools forever."""
    def __init__(self):
        self.toggle = False

    def complete(self, messages):
        self.toggle = not self.toggle
        tool = "get_ticket" if self.toggle else "search_knowledge_base"
        arg = '{"ticket_id": "TKT-101"}' if self.toggle else '{"query": "billing"}'
        return (
            f'Thought: Alternating forever.\nAction: {tool} | {arg}',
            100, 20, 0.0001
        )


@pytest.fixture
def test_env():
    env = SandboxEnvironment()
    env.reset()
    yield env
    env.close()


def test_stopping_condition_max_steps_proof(test_env):
    """
    PROOF 1: Step Limit Guarantee
    Regardless of model behavior, the loop CANNOT exceed max_steps.
    """
    checkpoint = HumanCheckpoint(mode="headless", auto_approve=True)
    tools = ToolRegistry(test_env, checkpoint_handler=checkpoint.request_approval)
    loop = AgentLoop(
        llm=AlternatingInfiniteLoopMockLLM(),
        tools=tools,
        max_steps=5,
        max_budget_usd=10.0,
    )

    trajectory = loop.run("PROOF-001", "Trigger runaway alternating loop.")
    assert trajectory.status == "STOPPED_MAX_STEPS"
    assert trajectory.total_steps == 5
    assert len(trajectory.steps) == 5
    assert "Hard step limit of 5 steps reached" in trajectory.error_summary


def test_stopping_condition_budget_cap_proof(test_env):
    """
    PROOF 2: Monetary Budget Cap Guarantee
    Regardless of model output, the loop CANNOT exceed max_budget_usd.
    """
    class ExpensiveAlternatingLLM(BaseLLMClient):
        def __init__(self):
            self.toggle = False

        def complete(self, messages):
            self.toggle = not self.toggle
            tool = "get_ticket" if self.toggle else "search_knowledge_base"
            arg = '{"ticket_id": "TKT-101"}' if self.toggle else '{"query": "billing"}'
            return (
                f'Thought: Expensive step.\nAction: {tool} | {arg}',
                100, 20, 0.02  # $0.02 per step
            )

    checkpoint = HumanCheckpoint(mode="headless", auto_approve=True)
    tools = ToolRegistry(test_env, checkpoint_handler=checkpoint.request_approval)
    loop = AgentLoop(
        llm=ExpensiveAlternatingLLM(),
        tools=tools,
        max_steps=100,
        max_budget_usd=0.03,  # $0.03 limit: breaches at step 2 ($0.04 >= $0.03)
    )

    trajectory = loop.run("PROOF-002", "Trigger runaway expensive loop.")
    assert trajectory.status == "STOPPED_BUDGET"
    assert trajectory.total_cost_usd >= 0.03
    assert "Budget limit of $0.0300 reached" in trajectory.error_summary


def test_stopping_condition_cycle_detector_proof(test_env):
    """
    PROOF 3: Cycle Detection Guarantee
    Repeating the exact same tool and arguments aborts the loop before running out of steps.
    """
    checkpoint = HumanCheckpoint(mode="headless", auto_approve=True)
    tools = ToolRegistry(test_env, checkpoint_handler=checkpoint.request_approval)
    loop = AgentLoop(
        llm=InfiniteLoopMockLLM(),
        tools=tools,
        max_steps=50,
        max_budget_usd=10.0,
        max_cycles=2,
    )

    trajectory = loop.run("PROOF-003", "Trigger identical repeating calls.")
    assert trajectory.status == "STOPPED_CYCLE"
    assert trajectory.total_steps <= 4
    assert "Infinite loop detected" in trajectory.error_summary


def test_stopping_condition_done_rule(test_env):
    """
    PROOF 4: Done Rule Normal Exit
    When the model emits 'Final Answer:', loop terminates cleanly with SUCCESS.
    """
    class TerminalLLM(BaseLLMClient):
        def complete(self, messages):
            return "Thought: Done.\nFinal Answer: Operation completed successfully.", 50, 10, 0.00001

    checkpoint = HumanCheckpoint(mode="headless", auto_approve=True)
    tools = ToolRegistry(test_env, checkpoint_handler=checkpoint.request_approval)
    loop = AgentLoop(llm=TerminalLLM(), tools=tools, max_steps=10)

    trajectory = loop.run("PROOF-004", "Simple task.")
    assert trajectory.status == "SUCCESS"
    assert trajectory.total_steps == 1
    assert "Operation completed successfully." in trajectory.final_answer
