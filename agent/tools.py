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
import sqlite3
import time
from datetime import datetime
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


class ToolRegistry:
    def __init__(self, sandbox: SandboxEnvironment, checkpoint_handler: Optional[Callable] = None):
        self.sandbox = sandbox
        self.checkpoint_handler = checkpoint_handler
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
                    "description": "Update the status and category tags of a ticket. Idempotent write.",
                    "parameters": UpdateStatusArgs.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "draft_reply",
                    "description": "Save an internal draft response for a ticket. Safe write.",
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
        now_iso = datetime.utcnow().isoformat() + "Z"

        # Dispatch with error boundary
        try:
            if name == "get_ticket":
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
                is_error = "Error:" in output or "DENIED" in output
                err_type = "UserRejectionError" if "DENIED" in output else ("WrongToolError" if is_error else None)

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

        except ValidationError as ve:
            # Format validation error cleanly for LLM consumption
            errors_str = "; ".join([f"{e['loc']}: {e['msg']}" for e in ve.errors()])
            output = f"Bad arguments error for tool '{name}': {errors_str}. Please review schema and correct parameters."
            is_error = True
            err_type = "BadArgumentsError"

        except Exception as e:
            output = f"Execution error in tool '{name}': {str(e)}. Please retry or inspect parameters."
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
        return (
            f"Ticket ID: {row['ticket_id']}\n"
            f"Customer ID: {row['customer_id']}\n"
            f"Sender: {row['sender_email']}\n"
            f"Subject: {row['subject']}\n"
            f"Status: {row['status']}\n"
            f"Tags: {row['tags']}\n"
            f"<UNTRUSTED_CUSTOMER_INPUT>\n"
            f"{row['body']}\n"
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

        # Human Checkpoint Approval Gate
        if self.checkpoint_handler:
            approved, reason = self.checkpoint_handler(
                ticket_id=args.ticket_id,
                action_type=f"UPDATE_STATUS_TO_{args.status}",
                payload={"new_status": args.status, "tags": list(new_tags)},
                idempotency_key=f"{args.ticket_id}-STATUS-{args.status}",
            )
            if not approved:
                return f"Human Checkpoint DENIED status update for ticket '{args.ticket_id}'. Reason: {reason}."

        merged_tags = list(existing_tags.union(new_tags))
        cursor.execute(
            "UPDATE tickets SET status = ?, tags = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
            (args.status, json.dumps(merged_tags), args.ticket_id),
        )
        conn.commit()
        return f"Success: Ticket '{args.ticket_id}' updated to status '{args.status}' with tags {merged_tags}."

    def _draft_reply(self, args: DraftReplyArgs) -> str:
        conn = self.sandbox.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_id FROM tickets WHERE ticket_id = ?", (args.ticket_id,))
        if not cursor.fetchone():
            return f"Error: Cannot draft reply for non-existent ticket '{args.ticket_id}'."

        cursor.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body) VALUES (?, ?, ?, ?)",
            (args.ticket_id, args.recipient, args.subject, args.body),
        )
        conn.commit()
        return f"Success: Draft reply saved for ticket '{args.ticket_id}' to recipient '{args.recipient}'."

    def _execute_action(self, args: ExecuteActionArgs) -> Tuple[str, bool, Optional[str]]:
        conn = self.sandbox.get_connection()
        cursor = conn.cursor()

        # 1. Idempotency Check
        cursor.execute(
            "SELECT action_type, executed_at FROM executed_actions WHERE idempotency_key = ?",
            (args.idempotency_key,),
        )
        existing = cursor.fetchone()
        if existing:
            return (
                f"Idempotency Guard: Action with key '{args.idempotency_key}' ({existing['action_type']}) "
                f"was already executed at {existing['executed_at']}. Duplicate execution blocked safely.",
                False,
                None,
            )

        # 2. Policy Enforcement Guardrails
        if args.action_type == "ISSUE_REFUND":
            amount = float(args.payload.get("amount", 0.0))
            if amount <= 0:
                return "Policy error: Refund amount must be greater than $0.00.", True, "BadArgumentsError"
            if amount > 150.0:
                return (
                    f"Policy violation: Requested refund of ${amount:.2f} exceeds operator limit of $150.00. "
                    "Action blocked. Please escalate ticket to a supervisor instead.",
                    True,
                    "PolicyViolationError",
                )

        if args.action_type == "RESET_PASSWORD":
            target_email = args.payload.get("target_email")
            cursor.execute("SELECT sender_email FROM tickets WHERE ticket_id = ?", (args.ticket_id,))
            t_row = cursor.fetchone()
            if not t_row:
                return f"Error: Ticket '{args.ticket_id}' not found.", True, "EmptyResultError"
            verified_email = t_row["sender_email"]
            if target_email and target_email.lower().strip() != verified_email.lower().strip():
                return (
                    f"Security policy violation: Cannot send password reset to '{target_email}'. "
                    f"Must match registered account email '{verified_email}'. Action blocked.",
                    True,
                    "SecurityViolationError",
                )

        # 3. Human Checkpoint Approval Gate
        if self.checkpoint_handler:
            approved, reason = self.checkpoint_handler(
                ticket_id=args.ticket_id,
                action_type=args.action_type,
                payload=args.payload,
                idempotency_key=args.idempotency_key,
            )
            if not approved:
                return (
                    f"Human Checkpoint DENIED action '{args.action_type}' for ticket '{args.ticket_id}'. "
                    f"Reason given: {reason}. Action aborted.",
                    True,
                    "UserRejectionError",
                )

        # 4. Commit Action to Database
        try:
            cursor.execute(
                "INSERT INTO executed_actions (idempotency_key, ticket_id, action_type, payload) VALUES (?, ?, ?, ?)",
                (args.idempotency_key, args.ticket_id, args.action_type, json.dumps(args.payload)),
            )

            # Apply domain side effects in sandbox
            if args.action_type == "CANCEL_ORDER":
                order_id = args.payload.get("order_id")
                cursor.execute("SELECT customer_id, orders FROM customers")
                for c_row in cursor.fetchall():
                    orders = json.loads(c_row["orders"])
                    updated = False
                    for ord_item in orders:
                        if ord_item["order_id"] == order_id:
                            ord_item["status"] = "CANCELLED"
                            updated = True
                    if updated:
                        cursor.execute(
                            "UPDATE customers SET orders = ? WHERE customer_id = ?",
                            (json.dumps(orders), c_row["customer_id"]),
                        )

            elif args.action_type == "ISSUE_REFUND":
                amount = float(args.payload.get("amount", 0.0))
                # Update customer balance/records
                cursor.execute("SELECT customer_id FROM tickets WHERE ticket_id = ?", (args.ticket_id,))
                t_row = cursor.fetchone()
                if t_row:
                    cursor.execute(
                        "UPDATE customers SET balance = balance + ? WHERE customer_id = ?",
                        (amount, t_row["customer_id"]),
                    )

            conn.commit()
            return (
                f"Success: Action '{args.action_type}' committed in sandbox with idempotency_key '{args.idempotency_key}'. "
                f"Details: {args.payload}",
                False,
                None,
            )
        except sqlite3.IntegrityError:
            return (
                f"Idempotency Guard: Database unique constraint prevented duplicate action '{args.idempotency_key}'.",
                False,
                None,
            )
