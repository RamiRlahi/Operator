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
import math
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import dotenv
dotenv.load_dotenv()

from agent.checkpoint import HumanCheckpoint
from agent.llm import MockDeterministicLLMClient, OpenAILLMClient
from agent.loop import AgentLoop
from agent.tools import ToolRegistry
from eval.runner import EvalRunner
from sandbox.environment import SandboxEnvironment


def run_interactive(ticket_id: str, use_live_api: bool = False, trace_path: Path | None = None):
    print("\n" + "=" * 65)
    print(f"       STARTING THE OPERATOR (Target: {ticket_id})")
    print("=" * 65)

    if use_live_api:
        api_key = os.getenv("BLOOMI_API_KEY", "").strip()
        base_url = os.getenv("BLOOMI_BASE_URL", "").strip()
        model = os.getenv("BLOOMI_MODEL", "").strip()
        if not all((api_key, base_url, model)) or api_key.startswith("your_"):
            raise SystemExit("--live requires BLOOMI_API_KEY, BLOOMI_BASE_URL and BLOOMI_MODEL in your local .env.")
        if urlparse(base_url).scheme != "https" or not urlparse(base_url).hostname:
            raise SystemExit("BLOOMI_BASE_URL must be an HTTPS API base URL.")
        try:
            input_rate = float(os.environ["BLOOMI_INPUT_USD_PER_MILLION"])
            output_rate = float(os.environ["BLOOMI_OUTPUT_USD_PER_MILLION"])
            if not all(math.isfinite(rate) and rate >= 0 for rate in (input_rate, output_rate)):
                raise ValueError
        except (KeyError, ValueError):
            raise SystemExit("Set the verified Bloomi input and output USD rates per million tokens before running live.")
        llm = OpenAILLMClient(api_key=api_key, base_url=base_url, model=model,
                             input_rate=input_rate, output_rate=output_rate)
        print(f"[LLM] Using live API with model {model}.")
    else:
        print("[LLM] Using Deterministic ReAct LLM Engine.")
        llm = MockDeterministicLLMClient()

    max_steps = int(os.getenv("MAX_STEPS", "6" if use_live_api else "10"))
    budget = float(os.getenv("BUDGET_LIMIT_USD", "0.01" if use_live_api else "0.25"))
    if max_steps < 1 or not math.isfinite(budget) or budget <= 0:
        raise SystemExit("MAX_STEPS and BUDGET_LIMIT_USD must be positive.")
    env = SandboxEnvironment()
    checkpoint = HumanCheckpoint(mode="interactive")
    tools = ToolRegistry(env, checkpoint_handler=checkpoint.request_approval, target_ticket_id=ticket_id)

    loop = AgentLoop(llm=llm, tools=tools, max_steps=max_steps, max_budget_usd=budget)
    prompt = f"Please inspect, triage, and resolve customer support ticket {ticket_id}."

    print(f"[Loop] Running with Max Steps: {max_steps}, Budget: ${budget:.2f}")
    trajectory = loop.run(task_id=f"RUN-{ticket_id}", prompt=prompt)
    env.close()

    if trace_path:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(trajectory.model_dump_json(indent=2), encoding="utf-8")

    print("\n" + "-" * 65)
    print(f"TRAJECTORY COMPLETED: Status = {trajectory.status}")
    print(f"Total Steps Executed: {trajectory.total_steps}")
    print(f"Model Attempts:       {trajectory.model_attempts}")
    print(f"Estimated Cost:       ${trajectory.total_cost_usd:.5f}")
    print(f"Duration:             {trajectory.duration_seconds}s")
    if trajectory.final_answer:
        print(f"\nFinal Answer:\n{trajectory.final_answer}")
    elif trajectory.error_summary:
        print(f"\nTermination Notice:\n{trajectory.error_summary}")
    print("=" * 65 + "\n")
    return 1 if trajectory.status == "FAILED" else 0


def main():
    parser = argparse.ArgumentParser(description="The Operator - Autonomous Triage and Remediator")
    parser.add_argument("--ticket", type=str, default="TKT-101", help="Ticket ID to process (default: TKT-101)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--eval", action="store_true", help="Run the offline evaluation suite")
    mode.add_argument("--reset", action="store_true", help="Reset sandbox database")
    mode.add_argument("--live", action="store_true", help="Use the configured Bloomi endpoint")
    parser.add_argument("--trace", type=Path, help="Save the interactive run's trajectory as JSON")
    args = parser.parse_args()

    if args.reset:
        env = SandboxEnvironment()
        env.reset()
        print("[Sandbox] Database reset to baseline.")
        env.close()
        return

    if args.eval:
        runner = EvalRunner()
        report = runner.run_all()
        return 0 if all(item["passed"] for item in report["scenario_results"]) else 1

    if not re.fullmatch(r"TKT-[A-Za-z0-9_-]+", args.ticket):
        parser.error("--ticket must be a ticket ID, such as TKT-101")
    return run_interactive(args.ticket, use_live_api=args.live, trace_path=args.trace)


if __name__ == "__main__":
    raise SystemExit(main())
