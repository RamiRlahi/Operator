# The Operator walkthrough

## Try it in five minutes

Extract the ZIP and open a terminal in the folder containing `main.py`. Use Python 3.10 or newer. On Windows, try `py` if `python` is unavailable.

```bash
python -m pip install -r requirements.txt
python sandbox/reset.py
python main.py --ticket TKT-101 --trace logs/refund.json
```

Approve the sandbox refund with `y`. You will then see a separate prompt to change the ticket status. Approve again to complete the run. For the refusal demo, reset the sandbox, rerun the same command and answer `n` to the first prompt. You should see `HUMAN_REJECTED` with no refund. If you approve the refund and decline the status change, the refund remains recorded and the ticket stays open. Each approval covers one database operation.

To demonstrate prompt injection, reset the sandbox and run `python main.py --ticket TKT-201 --trace logs/injection.json`. The fake ticket claims a $10,000 refund was already approved. The agent proposes escalating the ticket. Approving that proposal changes only its status and tags.

To run everything offline:

```bash
python -m pytest -q
python main.py --eval
```

Open `eval/results/eval_report.json` and search for `SCN-005` (invoice), `SCN-018` (injection), or `SCN-029` (timeout). Offline mode uses no key and consumes zero credits.

## Follow one run through the code

1. **`main.py` — Entry point.** Parses the selected ticket and mode, opens a SQLite sandbox, wires the approval handler and chooses the model. The default model is an offline simulator. `--trace` saves the run as JSON.
2. **`agent/loop.py` — Model loop.** Sends the task and instructions to the model. A reply contains either an `Action:` with JSON arguments or a `Final Answer:`. The loop parses one action, dispatches it, and supplies the observation for the next decision. It counts each model attempt before the call. The loop stops at the attempt cap, estimated budget threshold, repeated-action limit, final answer, refusal or provider failure.
3. **`agent/llm.py` — Model adapter.** The offline simulator uses predictable rules. The live adapter sends requests to the configured gateway and uses its reported token counts where available. Both adapters return the same four values: response text, input tokens, output tokens and estimated USD cost.
4. **`agent/models.py` and `agent/tools.py` — Tools.** Pydantic rejects unknown fields and wrong types. The dispatcher can read a ticket, search company policy, read the ticket's customer, update status, save a draft, or record an operational action. Python enforces the selected ticket, maximum sandbox refund, registered recipient and cancellable order state. Email and reset operations are sandbox records.
5. **`agent/checkpoint.py` — Approval.** Shows the exact write to the person at the terminal. No handler or no explicit approval means the write cannot happen. The evaluator substitutes a headless approval decision for reproducibility.
6. **`sandbox/environment.py` — Side effects.** Refunds change the simulated balance, cancellations change order state, and the other writes create rows or edit ticket state. An action's record and side effect commit in one transaction. A repeat with the same operation key and payload is treated as a duplicate. A key reused with different data is rejected. `sandbox/reset.py` restores the seed records.
7. **`eval/scenarios.py` and `eval/runner.py` — Evidence.** Each of the 35 fixtures states the expected calls and stop status. The evaluator matches the calls in order, checks the selected ticket and actions in SQLite, and reports timing, token estimates and the path. It injects three faults and checks that the agent recovers. In all seven injection cases it checks escalation and zero committed operational actions. The evaluator uses a separate, temporary SQLite database.
8. **`errors.md`, `threat_model.md`, `postmortem.md` and `report.pdf` — Submission.** These explain the handling of failures, where untrusted text enters, what bugs were fixed and how the project was measured. Add your team's named contributions to the README before submitting.

## The changes you can explain in the demo

- The first version let draft and status writes bypass the human checkpoint. Now every new sandbox write requires approval.
- The old offline model treated an invoice request as a refund. Its eval checked the final status and missed the side effect. We reproduced it, removed the default refund, and made the benchmark check SQLite.
- The original recovery cases described failures in the prompt. The current cases actually produce validation errors, empty results and a simulated timeout.
- The previous live path sent a startup ping before doing useful work. The optional adapter now starts with the task, disables SDK retries and bounds attempts. The mock transport tests cover the request settings.

## Bloomi setup, after the offline demo

Use `.env.example` as a template for a private local `.env`. The supplied adapter requires Bloomi to expose an OpenAI-compatible chat-completions endpoint. The course must supply the HTTPS base URL, model name, verified input and output prices per million tokens, and the account allowance. Keep the actual key local.

A first live run with `MAX_STEPS=1` measures one task request. Leave `--live` out of ordinary demos and automated tests. A live call can incur usage even if it times out, and the estimated dollar threshold can overshoot by one request. The real Bloomi endpoint was not called when preparing this ZIP.
