"""
ReAct loop engine for The Operator.
Implements the core Plan -> Act -> Observe cycle with:
- Multiple stopping conditions (Max steps, Budget limit, Cycle detection, Done rule)
- Mathematical termination guarantee
- Trajectory recording and token/cost accounting
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from agent.llm import BaseLLMClient
from agent.models import AgentStep, ToolCall, ToolResult, Trajectory
from agent.prompts import SYSTEM_PROMPT
from agent.tools import ToolRegistry


class AgentLoop:
    def __init__(
        self,
        llm: BaseLLMClient,
        tools: ToolRegistry,
        max_steps: int = 10,
        max_budget_usd: float = 0.25,
        max_cycles: int = 2,
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.max_budget_usd = max_budget_usd
        self.max_cycles = max_cycles

    def run(self, task_id: str, prompt: str, scenario_name: str = "default") -> Trajectory:
        start_time = time.perf_counter()
        trajectory = Trajectory(
            task_id=task_id,
            scenario_name=scenario_name,
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        recent_actions: List[Tuple[str, str]] = []

        step_idx = 0
        while True:
            step_idx += 1

            # ---------------------------------------------------------------
            # Stopping Condition 1: Max Steps Limit
            # ---------------------------------------------------------------
            if step_idx > self.max_steps:
                trajectory.status = "STOPPED_MAX_STEPS"
                trajectory.error_summary = f"Hard step limit of {self.max_steps} steps reached. Halting loop."
                break

            # ---------------------------------------------------------------
            # Stopping Condition 2: Budget Limit ($ USD)
            # ---------------------------------------------------------------
            if trajectory.total_cost_usd >= self.max_budget_usd:
                trajectory.status = "STOPPED_BUDGET"
                trajectory.error_summary = f"Budget limit of ${self.max_budget_usd:.4f} reached (Spent: ${trajectory.total_cost_usd:.4f}). Halting loop."
                break

            # Call LLM
            now_iso = datetime.now(timezone.utc).isoformat()
            trajectory.model_attempts += 1
            try:
                response_text, tokens_in, tokens_out, cost_usd = self.llm.complete(messages)
            except Exception as e:
                trajectory.status = "FAILED"
                trajectory.error_summary = f"LLM execution error ({type(e).__name__}). Check the provider configuration and quota."
                break

            trajectory.total_tokens_in += tokens_in
            trajectory.total_tokens_out += tokens_out
            trajectory.total_cost_usd += cost_usd

            thought, action_str, final_answer = self._parse_output(response_text)

            # ---------------------------------------------------------------
            # Stopping Condition 3: Done Rule (Final Answer Reached)
            # ---------------------------------------------------------------
            if final_answer is not None:
                step = AgentStep(
                    step_index=step_idx,
                    thought=thought,
                    is_final=True,
                    final_response=final_answer,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd,
                    timestamp=now_iso,
                )
                trajectory.steps.append(step)
                trajectory.status = "SUCCESS"
                trajectory.final_answer = final_answer
                break

            # Parse Action
            tool_call = self._parse_tool_call(action_str)
            if not tool_call:
                # LLM output was malformed (neither tool nor final answer)
                step = AgentStep(
                    step_index=step_idx,
                    thought=thought,
                    observation="Format error: Output must contain 'Action: <tool_name> | <json_args>' or 'Final Answer: <text>'",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd,
                    timestamp=now_iso,
                )
                trajectory.steps.append(step)
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": step.observation})
                continue

            # ---------------------------------------------------------------
            # Stopping Condition 4: Cycle / Loop Detector
            # ---------------------------------------------------------------
            action_signature = (tool_call.name, json.dumps(tool_call.arguments, sort_keys=True))
            recent_actions.append(action_signature)
            if len(recent_actions) >= self.max_cycles + 1:
                # Check if the last N actions were identical
                tail = recent_actions[- (self.max_cycles + 1):]
                if all(a == tail[0] for a in tail):
                    trajectory.status = "STOPPED_CYCLE"
                    trajectory.error_summary = f"Infinite loop detected: Action '{tool_call.name}' called repeatedly with identical arguments. Halting loop."
                    break

            # Execute Tool
            tool_result = self.tools.execute(tool_call)

            step = AgentStep(
                step_index=step_idx,
                thought=thought,
                tool_call=tool_call,
                observation=tool_result.output,
                tool_error=tool_result.error_type,
                tool_duration_ms=tool_result.duration_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                timestamp=now_iso,
            )
            trajectory.steps.append(step)

            # Check if human rejected the write action
            if tool_result.error_type == "UserRejectionError":
                trajectory.status = "HUMAN_REJECTED"
                trajectory.error_summary = "Operation terminated because human checkpoint rejected the write action."
                break

            # Append to message history for next turn
            messages.append({"role": "assistant", "content": response_text})
            observation = tool_result.output
            if tool_result.error_type:
                observation = f"{tool_result.error_type} from {tool_call.name}: {observation}"
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        trajectory.total_steps = len(trajectory.steps)
        trajectory.duration_seconds = round(time.perf_counter() - start_time, 3)
        return trajectory

    def _parse_output(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        thought = ""
        action = None
        final_answer = None

        thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|\nFinal Answer:|$)", text, re.DOTALL | re.IGNORECASE)
        if thought_match:
            thought = thought_match.group(1).strip()

        action_match = re.search(r"^Action:[ \t]*(.*)", text, re.IGNORECASE | re.MULTILINE)
        if action_match:
            action = action_match.group(1).strip()

        final_match = re.search(r"^Final Answer:[ \t]*(.+)", text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
        if final_match:
            final_answer = final_match.group(1).strip()

        if action and final_answer:
            return thought, None, None

        return thought, action, final_answer

    def _parse_tool_call(self, action_str: Optional[str]) -> Optional[ToolCall]:
        if not action_str:
            return None
        parts = action_str.split("|", 1)
        tool_name = parts[0].strip()
        args = {}
        if len(parts) > 1:
            raw_args = parts[1].strip()
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                # Return with bad arguments to trigger clean schema error
                return ToolCall(name=tool_name, arguments={"__raw_malformed__": raw_args})

        if not isinstance(args, dict):
            return None
        return ToolCall(name=tool_name, arguments=args)
