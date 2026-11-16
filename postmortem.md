# Postmortem

## The approval gap

The initial checkpoint covered only operational actions. A status update or draft could change SQLite without an approval, and constructing a registry without a handler let high-impact actions bypass the gate too. We factored the approval check into one tool method and verified that each write waits for explicit approval. The demo now shows what happens if an operator approves a refund and then declines the status update. SQLite retains the first operation because each proposal is approved separately.

## The false pass

An invoice-copy ticket ended with a success status despite having credited a $120 sandbox refund. The simulator defaulted to a refund, and the evaluator trusted the final status. We changed the simulator to base operational writes on ticket intent and made the runner check SQLite. The invoice case now expects zero committed actions. The refund, reset and cancellation cases check their action type and key payload values.

## Failure recovery and stopping

The early recovery fixtures only mentioned the error in natural language. The benchmark now injects an invalid read, empty policy search and timeout and verifies that each failure appeared in the trace. We also discovered that a cycle can consume a model response without adding a tool step, so we count model attempts separately. The spend threshold remains an estimate checked between calls. The maximum number of live attempts is the hard limit.

## Provider usage

We removed a startup ping that used an API request before the task began. The default run is offline, and the live adapter requires explicit settings. Its request construction was verified with a mock transport. Live Bloomi routing, quotas and model behaviour depend on the verified course configuration and were not measured.

## What the figures still leave open

Offline success measures the seeded scenarios and their declared assertions. Extra tool calls lower the trajectory score, and some fixtures allow more than one valid way to progress. The offline simulator's injection results do not establish how a live model responds. A small live spot-check and a fuller argument-level benchmark would provide the next evidence.
