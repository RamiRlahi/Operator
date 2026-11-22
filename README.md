# The Operator: Enterprise Autonomous Operations & Triage Agent

**CS496 AI Engineering — Project 3**  
*Mediterranean Institute of Technology (MedTech) — Fall 2026*  
*Instructor: Dr. Abdeldjalil Labed*

---

## 1. Quick Start

### One Setup Command
```bash
python -m pip install -r requirements.txt && python sandbox/reset.py
```

### One Run Command
```bash
python main.py --ticket TKT-101
```
Requires Python 3.10 or newer. On Windows, `py` can replace `python` in the commands.

This command uses the offline model by default and consumes no API credits. Each new status change, draft, or operational action prompts for its own approval. A denied action ends the run. An earlier approved action may already be saved in the sandbox.

### Run Evaluation Suite (35 Scenarios)
```bash
python eval/runner.py
```

### Run Full Test Suite (pytest)
```bash
pytest -v
```

---

## 2. Architecture & Core Components

The Operator is an autonomous agent designed to triage incoming customer support and operations tickets, look up policies, inspect customer history, and execute state-modifying actions safely.

```
                          ┌───────────────────────────┐
                          │   ReAct Loop (Plan-Act)   │
                          └─────────────┬─────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           ▼                            ▼                            ▼
   ┌───────────────┐            ┌───────────────┐            ┌───────────────┐
   │  Read Tools   │            │  Write Tools  │            │  Human Check  │
   │ - get_ticket  │            │ - update_stat │            │  Point Gate   │
   │ - search_kb   │            │ - draft_reply │            │  [y/N prompt] │
   │ - check_cust  │            │ - exec_action │            └───────┬───────┘
   └───────┬───────┘            └───────┬───────┘                    │
           │                            │ (Idempotency Key)          ▼
           └────────────────────────────┴────────────────────► ┌───────────┐
                                                               │  Sandbox  │
                                                               │  SQLite   │
                                                               └───────────┘
```

1. **Agent Tools (`agent/tools.py`)**:
   - 6 tools (3 read, 3 write) with strict Pydantic input validation.
   - Idempotent writes: duplicate requests with the same idempotency key are safely blocked without repeated database side effects.
   - Clear text error feedback: errors return actionable diagnostic text without stack traces.
2. **Loop & Stopping Conditions (`agent/loop.py`)**:
   - The loop rechecks the attempt count and estimated spend each turn. It also stops when it sees a cycle or a final answer:
     - Hard step limit (`max_steps=10`)
     - Estimated dollar threshold checked between attempts
     - Action cycle detector (`max_cycles=2` identical repeating actions)
     - Done-rule (`Final Answer:`)
3. **Sandbox Environment (`sandbox/`)**:
   - Isolated SQLite database storing tickets, customers, knowledge base, and executed actions.
   - One-command reset script (`python sandbox/reset.py`) restores baseline seed state instantly.
4. **Human Checkpoint Gatekeeper (`agent/checkpoint.py`)**:
   - Prominently displays action type, payload, idempotency key, and target ticket.
   - Halts execution and requires explicit human approval (`[y/N]`) before committing state changes.
5. **Threat Model & Prompt Injection Defence (`threat_model.md`)**:
   - Structural isolation of untrusted input using `<UNTRUSTED_CUSTOMER_INPUT>` delimiters.
   - Tool-level refund limits, registered-recipient checks and approval. The sandbox records email and reset requests in SQLite.
   - Seven offline injection scenarios verify escalation and absence of committed operational actions.

---

## 3. Offline Evaluation

```bash
python main.py --eval
python -m pytest -q
```

The benchmark starts each scenario in a fresh test state in a temporary SQLite database. It checks the order of expected calls, ticket identity, forbidden calls, stop status and selected database outcomes. It deliberately triggers invalid arguments, a missing knowledge-base result and a timeout. The JSON report includes tool arguments, observations, latencies, errors, approvals and token estimates.

The course report is in `report.pdf`. Start with `WALKTHROUGH.md` for a guided demo and an explanation of each module.

## 4. Bloomi and Cost

Offline runs use zero API credits. Offline token counts and USD values are illustrative. The runner projects the average estimated cost across 100 comparable tasks.

The optional live client expects an OpenAI-compatible chat-completions endpoint. Verify the course's API base URL, model, allowance and pricing. Copy `.env.example` to `.env`, fill it locally and keep the key private. Set `MAX_STEPS=1` for a first connectivity check through a real task, then raise it only if needed. Run `python main.py --live --ticket TKT-101` once configured.

Live mode has a six-attempt default, 500 output tokens per request, a 30-second SDK timeout and zero automatic retries. The estimated dollar threshold is checked between requests and a single response can take it over the threshold. The course's gateway and live usage were not verified in the delivered build.

## 5. Repository Structure

```
ailab/
├── README.md                   # Setup, run commands, results, contributions
├── main.py                     # Main CLI entry point
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── errors.md                   # Error taxonomy and failure recovery strategies
├── threat_model.md             # Threat model for indirect prompt injection
├── postmortem.md               # Honest engineering analysis of bugs & learnings
├── .env.example                # Template configuration (no secrets in repo)
├── agent/
│   ├── __init__.py
│   ├── models.py               # Pydantic schemas for tools, steps, trajectories
│   ├── tools.py                # 6 tools with validation, logging, idempotency
│   ├── loop.py                 # ReAct Plan-Act loop with stopping conditions
│   ├── checkpoint.py           # Human-in-the-loop approval gatekeeper
│   ├── prompts.py              # System prompt and instruction/data isolation
│   └── llm.py                  # Dual LLM provider (OpenAI API + Mock ReAct)
├── sandbox/
│   ├── environment.py          # Isolated SQLite database environment
│   ├── reset.py                # Database reset script
│   └── data/                   # Sandbox database directory
├── eval/
│   ├── __init__.py
│   ├── scenarios.py            # 35 test scenarios across 5 cohorts
│   ├── runner.py               # Trajectory evaluation runner
│   ├── injection_cases.py      # 7 adversarial prompt injection vectors
│   └── results/
│       └── eval_report.json    # Full evaluation report JSON
└── tests/
    ├── test_stopping_condition.py  # Proof that agent cannot run forever
    ├── test_idempotency.py         # Proof that writes do not duplicate
    ├── test_checkpoint.py          # Human approval gatekeeper tests
    ├── test_injections.py          # Indirect prompt injection tests
    └── test_error_recovery.py      # Error taxonomy unit tests
```

---

## 6. Contributions Section

- **Architecture & System Design**: Dual LLM execution engine, ReAct loop with multi-layer stopping bounds, SQLite sandbox environment.
- **Tool Development & Safety Guardrails**: Implementation of 6 tools with Pydantic validation, deterministic idempotency keys, and human-in-the-loop approval gate.
- **Evaluation & Security**: Construction of 35 benchmark scenarios, 7 adversarial prompt injection vectors, trajectory metrics calculator, and error taxonomy suite.
- **Documentation**: README, threat model, error taxonomy, and engineering postmortem.

Add the team members’ names next to the work they personally completed before submission.
