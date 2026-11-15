# The Operator: Enterprise Autonomous Operations & Triage Agent

**CS496 AI Engineering — Project 3**  
*Mediterranean Institute of Technology (MedTech) — Fall 2026*  
*Instructor: Dr. Abdeldjalil Labed*

---

## 1. Quick Start

### One Setup Command
```bash
pip install -r requirements.txt && python sandbox/reset.py
```

### One Run Command
```bash
python main.py --ticket TKT-101
```
*(Runs interactive triage with human checkpoint approval gate)*

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
   - Guaranteed mathematical termination enforced by three independent bounds:
     - Hard step limit (`max_steps=10`)
     - Monetary budget limit (`max_budget_usd=$0.25`)
     - Action cycle detector (`max_cycles=2` identical repeating actions)
     - Done-rule (`Final Answer:`)
3. **Sandbox Environment (`sandbox/`)**:
   - Isolated SQLite database storing tickets, customers, knowledge base, and executed actions.
   - One-command reset script (`python sandbox/reset.py`) restores baseline seed state instantly.
4. **Human Checkpoint Gatekeeper (`agent/checkpoint.py`)**:
   - Prominently displays action type, payload, idempotency key, and target ticket.
   - Halts execution and requires explicit human approval (`[y/N]`) before committing state changes.
5. **Threat Model & Prompt Injection Defense (`threat_model.md`)**:
   - Structural isolation of untrusted input using `<UNTRUSTED_CUSTOMER_INPUT>` delimiters.
   - Hard policy constraints preventing unauthorized refunds over $150.00 and unauthorized email dispatches.
   - Evaluated against 7 adversarial attack vectors with 100% block rate.

---

## 3. Evaluation Results

Results from evaluating the agent across all 35 benchmark scenarios (`eval/results/eval_report.json`):

| Evaluation Metric | Measured Result | Assignment Target | Status |
|---|---|---|---|
| **Total Test Scenarios** | **35 scenarios** | ≥ 30 scenarios | Passed |
| **Overall Task Success Rate** | **100.0%** (35/35) | High | Passed |
| **Per-Step Accuracy** | **56.43%** | Path correctness | Passed |
| **Tool-Call Precision** | **98.57%** | Schema adherence | Passed |
| **Average Wasted Steps / Task** | **1.80 steps** | Minimal overhead | Passed |
| **Recovery-After-Failure Rate** | **100.0%** (6/6) | ≥ 80% | Passed |
| **Prompt Injection Defense** | **100.0%** (7/7 blocked) | 5+ test cases | Passed |
| **Stop Rule Violations** | **0 violations** | Never exceeded | Passed |
| **Latency p50 / p95** | **0.0092s / 0.0178s** | Responsive | Passed |
| **Average Cost per Task** | **$0.00082** | < $0.05 | Passed |
| **Cost at 100× Scale** | **$0.0825** | Cost model | Passed |

---

## 4. Cost Model

Token usage is measured per step and computed using `gpt-4o-mini` pricing ($0.15 / 1M input tokens, $0.60 / 1M output tokens):
- **Average Tokens per Task**: ~5,200 tokens
- **Average Cost per Task**: **$0.00082 USD** (less than one tenth of a cent per ticket)
- **Cost for 100 Tasks**: **$0.0825 USD**
- **Cost for 10,000 Tasks**: **$8.25 USD**

---

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
