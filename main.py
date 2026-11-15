"""
The Operator - Main CLI Entry Point
Run interactive agent triage or trigger evaluation benchmark.

Usage:
    python main.py                      # Interactive triage of default ticket TKT-101
    python main.py --ticket TKT-102     # Interactive triage of specific ticket
    python main.py --eval               # Run the 35-scenario evaluation suite
    python main.py --reset              # Reset sandbox database to baseline
"""

import argparse
import os
import sys
from pathlib import Path

import dotenv
dotenv.load_dotenv()

from agent.checkpoint import HumanCheckpoint
from agent.llm import MockDeterministicLLMClient, OpenAILLMClient
from agent.loop import AgentLoop
from agent.tools import ToolRegistry
from eval.runner import EvalRunner
from sandbox.environment import SandboxEnvironment


def run_interactive(ticket_id: str, use_live_api: bool = False):
    print("\n" + "=" * 65)
    print(f"       STARTING THE OPERATOR (Target: {ticket_id})")
    print("=" * 65)

    env = SandboxEnvironment()
    checkpoint = HumanCheckpoint(mode="interactive")
    tools = ToolRegistry(env, checkpoint_handler=checkpoint.request_approval)

    # Determine LLM backend
    api_key = os.getenv("OPENAI_API_KEY", "")
    llm = None
    if use_live_api and api_key and not api_key.startswith("your_"):
        try:
            print("[LLM] Attempting connection to OpenAI API (gpt-4o-mini)...")
            llm = OpenAILLMClient()
            # Fast test ping
            llm.complete([{"role": "user", "content": "ping"}])
            print("[LLM] OpenAI API connected successfully.")
        except Exception as e:
            print(f"[LLM] OpenAI connection failed ({type(e).__name__}: {e}).")
            print("[LLM] Falling back to Deterministic ReAct LLM Engine.")
            llm = MockDeterministicLLMClient()
    else:
        print("[LLM] Using Deterministic ReAct LLM Engine.")
        llm = MockDeterministicLLMClient()

    max_steps = int(os.getenv("MAX_STEPS", "10"))
    budget = float(os.getenv("BUDGET_LIMIT_USD", "0.25"))

    loop = AgentLoop(llm=llm, tools=tools, max_steps=max_steps, max_budget_usd=budget)
    prompt = f"Please inspect, triage, and resolve customer support ticket {ticket_id}."

    print(f"[Loop] Running with Max Steps: {max_steps}, Budget: ${budget:.2f}")
    trajectory = loop.run(task_id=f"RUN-{ticket_id}", prompt=prompt)

    print("\n" + "-" * 65)
    print(f"TRAJECTORY COMPLETED: Status = {trajectory.status}")
    print(f"Total Steps Executed: {trajectory.total_steps}")
    print(f"Total Cost:           ${trajectory.total_cost_usd:.5f}")
    print(f"Duration:             {trajectory.duration_seconds}s")
    if trajectory.final_answer:
        print(f"\nFinal Answer:\n{trajectory.final_answer}")
    elif trajectory.error_summary:
        print(f"\nTermination Notice:\n{trajectory.error_summary}")
    print("=" * 65 + "\n")
    env.close()


def main():
    parser = argparse.ArgumentParser(description="The Operator - Autonomous Triage and Remediator")
    parser.add_argument("--ticket", type=str, default="TKT-101", help="Ticket ID to process (default: TKT-101)")
    parser.add_argument("--eval", action="store_true", help="Run 35-scenario evaluation suite")
    parser.add_argument("--reset", action="store_true", help="Reset sandbox database")
    parser.add_argument("--live", action="store_true", help="Force live OpenAI API calls")
    args = parser.parse_args()

    if args.reset:
        env = SandboxEnvironment()
        env.reset()
        print("[Sandbox] Database reset to baseline.")
        env.close()
        return

    if args.eval:
        runner = EvalRunner()
        runner.run_all()
        return

    run_interactive(args.ticket, use_live_api=args.live)


if __name__ == "__main__":
    main()
