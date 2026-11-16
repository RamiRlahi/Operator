"""
Tools module for The Operator.
Implements 6 tools (3 read, 3 write) with:
- Strict Pydantic input schemas
- Idempotent writes
- Clear, actionable plain-text errors (no stack traces)
- Comprehensive execution logging (input, output, duration, timestamp)
- Policy enforcement and human checkpoint integration
"""

import json
import math
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Dict, List, Optional, Tuple
from pydantic import ValidationError

from agent.models import (
    CheckCustomerArgs,
    DraftReplyArgs,
    ExecuteActionArgs,
    GetTicketArgs,
    SearchKBArgs,
    ToolCall,
    ToolResult,
    UpdateStatusArgs,
)
from sandbox.environment import SandboxEnvironment


class WriteRejected(Exception):
    """A write lacked explicit approval."""


class ScopeViolation(Exception):
    """An operation targeted data outside the selected ticket."""


class ToolRegistry:
    def __init__(self, sandbox: SandboxEnvironment, checkpoint_handler: Optional[Callable] = None,
                 *, target_ticket_id: Optional[str] = None):
        self.sandbox = sandbox
        self.checkpoint_handler = checkpoint_handler
        self.target_ticket_id = target_ticket_id
        self.call_logs: List[ToolResult] = []

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Returns OpenAI-compatible function calling schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_ticket",
                    "description": "Retrieve ticket details by ID. Returns subject, sender, body, status, and tags.",
                    "parameters": GetTicketArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge_base",
                    "description": "Search internal company policies and SOPs (billing, security, shipping, orders).",
                    "parameters": SearchKBArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_customer_status",
                    "description": "Look up customer account, plan type, balance, and order history.",
                    "parameters": CheckCustomerArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_ticket_status",
                    "description": "Update the status and category tags of a ticket after approval. Idempotent write.",
                    "parameters": UpdateStatusArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "draft_reply",
                    "description": "Save an internal draft response for a ticket after approval. Idempotent write.",
                    "parameters": DraftReplyArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_action",
                    "description": (
                        "Execute high-impact action (SEND_EMAIL, ISSUE_REFUND, RESET_PASSWORD, CANCEL_ORDER). "
                        "Requires an idempotency_key and passes through human checkpoint approval before execution."
                    ),
                    "parameters": ExecuteActionArgs.model_json_schema(),
                },
            },
        ]

    def execute(self, tool_call: ToolCall) -> ToolResult:
        start_time = time.perf_counter()
        name = tool_call.name
        args = tool_call.arguments
        now_iso = datetime.now(timezone.utc).isoformat()

        # Dispatch with error boundary
        try:
            if (self.target_ticket_id and name in {"get_ticket", "update_ticket_status", "draft_reply", "execute_action"}
                    and args.get("ticket_id", self.target_ticket_id) != self.target_ticket_id):
                output = "This run is limited to the ticket selected by the operator."
                is_error = True
                err_type = "SecurityViolationError"

            elif name == "get_ticket":
                validated = GetTicketArgs(**args)
                output = self._get_ticket(validated)
                is_error = "Error:" in output
                err_type = "EmptyResultError" if is_error else None

            elif name == "search_knowledge_base":
                validated = SearchKBArgs(**args)
                output = self._search_kb(validated)
                is_error = "Error:" in output
                err_type = "EmptyResultError" if is_error else None

            elif name == "check_customer_status":
                validated = CheckCustomerArgs(**args)
                output = self._check_customer(validated)
                is_error = "Error:" in output
                err_type = "EmptyResultError" if is_error else None

            elif name == "update_ticket_status":
                validated = UpdateStatusArgs(**args)
                output = self._update_ticket_status(validated)
                is_error = "Error:" in output
                err_type = "WrongToolError" if is_error else None

            elif name == "draft_reply":
                validated = DraftReplyArgs(**args)
                output = self._draft_reply(validated)
                is_error = "Error:" in output
                err_type = "WrongToolError" if is_error else None

            elif name == "execute_action":
                validated = ExecuteActionArgs(**args)
                output, is_error, err_type = self._execute_action(validated)

            else:
                output = f"Error: Unknown tool '{name}'. Available tools: get_ticket, search_knowledge_base, check_customer_status, update_ticket_status, draft_reply, execute_action."
                is_error = True
                err_type = "WrongToolError"

        except WriteRejected as exc:
            output = str(exc)
            is_error = True
            err_type = "UserRejectionError"

        except ScopeViolation as exc:
            output = str(exc)
            is_error = True
            err_type = "SecurityViolationError"

        except ValidationError as ve:
            # Format validation error cleanly for LLM consumption
            errors_str = "; ".join([f"{e['loc']}: {e['msg']}" for e in ve.errors()])
            output = f"Bad arguments error for tool '{name}': {errors_str}. Please review schema and correct parameters."
            is_error = True
            err_type = "BadArgumentsError"

        except TimeoutError:
            output = f"Tool '{name}' timed out. Use the same operation key when retrying an approved write."
            is_error = True
            err_type = "TimeoutError"

        except Exception:
            output = f"Execution error in tool '{name}'. Please retry or inspect parameters."
            is_error = True
            err_type = "ToolDownError"

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result = ToolResult(
            tool_name=name,
            output=output,
            is_error=is_error,
            error_type=err_type,
            duration_ms=round(duration_ms, 2),
            timestamp=now_iso,
        )
        self.call_logs.append(result)
        return result

    def _require_write_approval(
        self, ticket_id: str, action_type: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None
    ) -> None:
        if self.checkpoint_handler is None:
            raise WriteRejected(f"Human Checkpoint DENIED action '{action_type}': no approval handler configured.")

        # Give the checkpoint a stable identifier and a separate copy of the write payload.
        serialized = json.dumps(payload, sort_keys=True)
        if idempotency_key is None:
            fingerprint = sha256(serialized.encode()).hexdigest()
            idempotency_key = f"{ticket_id}-{action_type}-{fingerprint}"
        approved, reason = self.checkpoint_handler(
            ticket_id=ticket_id,
            action_type=action_type,
            payload=json.loads(serialized),
            idempotency_key=idempotency_key,
        )
        if approved is not True:
            raise WriteRejected(
                f"Human Checkpoint DENIED action '{action_type}' for ticket '{ticket_id}'. "
                f"Reason given: {reason}. Action aborted."
            )

    # -----------------------------------------------------------------------
    # Tool Implementations
    # -----------------------------------------------------------------------

    def _get_ticket(self, args: GetTicketArgs) -> str:
        conn = self.sandbox.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticket_id, customer_id, sender_email, subject, body, status, tags FROM tickets WHERE ticket_id = ?",
            (args.ticket_id,),
        )
        row = cursor.fetchone()
        if not row:
            return f"Error: Ticket '{args.ticket_id}' not found in database. Please verify the ticket ID."

        # Notice: Encapsulate untrusted user-submitted ticket body safely
        body = row["body"].replace("<", "&lt;").replace(">", "&gt;")
        return (
            f"Ticket ID: {row['ticket_id']}\n"
            f"Customer ID: {row['customer_id']}\n"
            f"Sender: {row['sender_email']}\n"
            f"Subject: {row['subject']}\n"
            f"Status: {row['status']}\n"
            f"Tags: {row['tags']}\n"
            f"<UNTRUSTED_CUSTOMER_INPUT>\n"
            f"{body}\n"
            f"</UNTRUSTED_CUSTOMER_INPUT>"
        )

    def _search_kb(self, args: SearchKBArgs) -> str:
        conn = self.sandbox.get_connection()
        cursor = conn.cursor()
        q = f"%{args.query.strip().lower()}%"
        cursor.execute(
            "SELECT article_id, category, title, content FROM knowledge_base "
            "WHERE LOWER(category) LIKE ? OR LOWER(title) LIKE ? OR LOWER(content) LIKE ?",
            (q, q, q),
        )
        rows = cursor.fetchall()
        if not rows:
            return f"Error: No knowledge base articles matched query '{args.query}'. Available categories: billing, security, shipping, orders."

        results = []
        for r in rows:
            results.append(f"[{r['article_id']}] {r['title']} (Category: {r['category']}):\n{r['content']}")
        return "\n\n".join(results)

    def _check_customer(self, args: CheckCustomerArgs) -> str:
        conn = self.sandbox.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT customer_id, name, email, plan, balance, orders FROM customers WHERE customer_id = ? OR email = ?",
            (args.customer_id, args.customer_id),
        )
        row = cursor.fetchone()
        if not row:
            return f"Error: Customer record '{args.customer_id}' not found."
        if self.target_ticket_id:
            associated = conn.execute("SELECT customer_id FROM tickets WHERE ticket_id = ?", (self.target_ticket_id,)).fetchone()
            if associated is None or associated["customer_id"] != row["customer_id"]:
                raise ScopeViolation("Customer records are limited to the selected ticket.")

        orders = json.loads(row["orders"])
        orders_str = "\n".join([f"  - Order {o['order_id']}: {o['item']} (${o['amount']}) Status: {o['status']}" for o in orders])
        return (
            f"Customer ID: {row['customer_id']}\n"
            f"Name: {row['name']}\n"
            f"Email: {row['email']}\n"
            f"Plan: {row['plan']}\n"
            f"Account Balance: ${row['balance']:.2f}\n"
            f"Orders:\n{orders_str if orders_str else '  No orders on record.'}"
        )

    def _update_ticket_status(self, args: UpdateStatusArgs) -> str:
        conn = self.sandbox.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status, tags FROM tickets WHERE ticket_id = ?", (args.ticket_id,))
        row = cursor.fetchone()
        if not row:
            return f"Error: Cannot update non-existent ticket '{args.ticket_id}'."

        existing_status = row["status"]
        existing_tags = set(json.loads(row["tags"]))
        new_tags = set(args.tags)

        # Idempotency check: if status matches and all requested tags are already present, no-op
        if existing_status == args.status and new_tags.issubset(existing_tags):
            return (
                f"Idempotent update: Ticket '{args.ticket_id}' is already at status '{args.status}' "
                f"with tags {list(existing_tags)}. No database modification performed."
            )

        self._require_write_approval(
            args.ticket_id, "UPDATE_TICKET_STATUS", {"status": args.status, "add_tags": sorted(new_tags)}
        )
        # The operator may take time to approve. Re-read the current tags under a write transaction
        # so independent updates made during that pause are preserved.
        with conn:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT status, tags FROM tickets WHERE ticket_id = ?", (args.ticket_id,))
            row = cursor.fetchone()
            if row is None:
                return f"Error: Cannot update non-existent ticket '{args.ticket_id}'."
            existing_tags = set(json.loads(row["tags"]))
            if row["status"] == args.status and new_tags.issubset(existing_tags):
                return f"Idempotent update: Ticket '{args.ticket_id}' already matches. No database modification performed."
            merged_tags = sorted(existing_tags.union(new_tags))
            cursor.execute(
                "UPDATE tickets SET status = ?, tags = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (args.status, json.dumps(merged_tags), args.ticket_id),
            )
        return f"Success: Ticket '{args.ticket_id}' updated to status '{args.status}' with tags {merged_tags}."

    def _draft_reply(self, args: DraftReplyArgs) -> str:
        conn = self.sandbox.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_id FROM tickets WHERE ticket_id = ?", (args.ticket_id,))
        if not cursor.fetchone():
            return f"Error: Cannot draft reply for non-existent ticket '{args.ticket_id}'."

        values = (args.ticket_id, args.recipient, args.subject, args.body)
        match = "ticket_id = ? AND recipient = ? AND subject = ? AND body = ?"
        duplicate = f"Idempotent draft: Identical reply already saved for ticket '{args.ticket_id}'."
        cursor.execute(f"SELECT 1 FROM drafts WHERE {match}", values)
        if cursor.fetchone():
            return duplicate

        self._require_write_approval(args.ticket_id, "DRAFT_REPLY", args.model_dump(exclude={"ticket_id"}))
        with conn:
            cursor.execute(
                "INSERT INTO drafts (ticket_id, recipient, subject, body) SELECT ?, ?, ?, ? "
                "WHERE EXISTS (SELECT 1 FROM tickets WHERE ticket_id = ?) "
                f"AND NOT EXISTS (SELECT 1 FROM drafts WHERE {match})",
                (*values, args.ticket_id, *values),
            )
            if cursor.rowcount == 0:
                cursor.execute("SELECT 1 FROM tickets WHERE ticket_id = ?", (args.ticket_id,))
                if cursor.fetchone() is None:
                    return f"Error: Cannot draft reply for non-existent ticket '{args.ticket_id}'."
                return duplicate
        return f"Success: Draft reply saved for ticket '{args.ticket_id}' to recipient '{args.recipient}'."

    def _execute_action(self, args: ExecuteActionArgs) -> Tuple[str, bool, Optional[str]]:
        conn = self.sandbox.get_connection()
        amount = args.payload.get("amount")
        if args.action_type == "ISSUE_REFUND":
            if type(amount) not in (int, float) or not 0 < amount or (type(amount) is float and not math.isfinite(amount)):
                return "Refund amount must be a positive number.", True, "BadArgumentsError"
            if amount > 150:
                return f"Requested refund of ${amount:.2f} exceeds operator limit of $150.00.", True, "PolicyViolationError"
        elif args.action_type in ("RESET_PASSWORD", "SEND_EMAIL"):
            field = "target_email" if args.action_type == "RESET_PASSWORD" else "recipient"
            target = args.payload.get(field)
            if not isinstance(target, str) or not target.strip():
                return f"Provide a non-empty {field}.", True, "BadArgumentsError"
        else:
            order_id = args.payload.get("order_id")
            if not isinstance(order_id, str) or not order_id:
                return "Provide an order_id.", True, "BadArgumentsError"

        def check_action():
            existing = conn.execute(
                "SELECT ticket_id, action_type, payload FROM executed_actions WHERE idempotency_key = ?",
                (args.idempotency_key,),
            ).fetchone()
            if existing:
                if (existing["ticket_id"], existing["action_type"], json.loads(existing["payload"])) != (
                    args.ticket_id, args.action_type, args.payload
                ):
                    return ("Idempotency key already belongs to a different action.", True, "BadArgumentsError"), None
                return ("Idempotency Guard: Duplicate execution blocked safely.", False, None), None

            customer = conn.execute(
                "SELECT c.customer_id, c.email, c.orders FROM tickets t "
                "JOIN customers c ON c.customer_id = t.customer_id WHERE t.ticket_id = ?",
                (args.ticket_id,),
            ).fetchone()
            if customer is None:
                return (f"Ticket or customer for '{args.ticket_id}' not found.", True, "EmptyResultError"), None
            if args.action_type in ("RESET_PASSWORD", "SEND_EMAIL") and target.strip().casefold() != customer["email"].casefold():
                return ("Security policy violation: recipient must match the registered customer.", True, "SecurityViolationError"), None
            if args.action_type == "CANCEL_ORDER":
                orders = json.loads(customer["orders"])
                order = next((item for item in orders if item["order_id"] == order_id), None)
                if order is None:
                    return ("Order is not associated with this ticket's customer.", True, "SecurityViolationError"), None
                if order["status"] not in ("PENDING", "PROCESSING"):
                    return ("Only pending or processing orders can be cancelled.", True, "PolicyViolationError"), None
                order["status"] = "CANCELLED"
                return None, (customer["customer_id"], json.dumps(orders))
            return None, (customer["customer_id"], None)

        result, _ = check_action()
        if result is not None:
            return result
        self._require_write_approval(args.ticket_id, args.action_type, args.payload, args.idempotency_key)

        with conn:
            conn.execute("BEGIN IMMEDIATE")
            result, customer_state = check_action()
            if result is not None:
                return result
            customer_id, orders = customer_state
            conn.execute(
                "INSERT INTO executed_actions (idempotency_key, ticket_id, action_type, payload) VALUES (?, ?, ?, ?)",
                (args.idempotency_key, args.ticket_id, args.action_type, json.dumps(args.payload, allow_nan=False)),
            )
            if args.action_type == "CANCEL_ORDER":
                conn.execute("UPDATE customers SET orders = ? WHERE customer_id = ?", (orders, customer_id))
            elif args.action_type == "ISSUE_REFUND":
                conn.execute("UPDATE customers SET balance = balance + ? WHERE customer_id = ?", (amount, customer_id))

        return f"Success: Action '{args.action_type}' committed in sandbox.", False, None
