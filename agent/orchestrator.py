import json
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

from config import OPENAI_API_KEY, LLM_API_BASE, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, MAX_TOOL_CALLS_PER_TURN
import httpx
from agent.prompts import SYSTEM_PROMPT, build_context_prompt
from tools.registry import ToolRegistry
from tools.handlers import ToolHandlers
from tools.mock_db import MockDB
from rag.engine import RAGEngine
from policy.engine import PolicyEngine, PolicyResult


@dataclass
class AgentStep:
    step_type: str  # "rag_retrieval", "tool_call", "policy_check", "llm_response", "escalation"
    detail: dict
    result: Optional[dict] = None


@dataclass
class AgentResponse:
    """Complete response from the agent."""
    message: str  # The customer-facing message
    steps: list[AgentStep] = field(default_factory=list)  # Full reasoning trace
    escalations: list[dict] = field(default_factory=list)  # Actions needing human approval
    actions_taken: list[dict] = field(default_factory=list)  # Actions that were executed
    citations: list[dict] = field(default_factory=list)  # Policy citations


class AgentOrchestrator:
    def __init__(self):
        self.db = MockDB()
        self.handlers = ToolHandlers(self.db)
        self.tool_registry = ToolRegistry(self.handlers)
        self.rag = RAGEngine()
        self.policy = PolicyEngine()

        if LLM_API_BASE and LLM_API_BASE.startswith("http://10."):
            # Internal server → bypass proxy
            http_client = httpx.Client(timeout=120.0, trust_env=False)
        else:
            # Other external endpoints → use proxy if configured
            http_client = httpx.Client(timeout=120.0, trust_env=True)
        
        client_kwargs = {
            "api_key": OPENAI_API_KEY,
            "http_client": http_client
        }
        if LLM_API_BASE:
            client_kwargs["base_url"] = LLM_API_BASE
        self.client = OpenAI(**client_kwargs)

        # Index knowledge base on startup
        self.rag.index_knowledge_base()

    def process_message(self, customer_message: str, customer_id: Optional[str] = None) -> AgentResponse:
        steps: list[AgentStep] = []
        escalations: list[dict] = []
        actions_taken: list[dict] = []
        citations: list[dict] = []

        # ---- Step 1: RAG Retrieval ----
        rag_results = self.rag.retrieve(customer_message)
        rag_step = AgentStep(
            step_type="rag_retrieval",
            detail={"query": customer_message, "results_count": len(rag_results)},
            result={"contexts": [{"source": r["source"], "section": r["section"],
                                   "score": r["relevance_score"]} for r in rag_results]},
        )
        steps.append(rag_step)
        citations = [{"source": r["source"], "section": r["section"]} for r in rag_results]

        # ---- Step 2: Build messages for LLM ----
        context_prompt = build_context_prompt(rag_results)
        
        # Combine system prompt with RAG context into a single system message
        full_system_prompt = SYSTEM_PROMPT
        if context_prompt:
            full_system_prompt = f"{SYSTEM_PROMPT}\n\n{context_prompt}"
        if customer_id:
            full_system_prompt = f"{full_system_prompt}\n\nCurrent customer ID: {customer_id}"
        
        messages = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": customer_message}
        ]

        # ---- Step 3: Agent Loop (LLM ↔ Tools) ----
        tool_call_count = 0

        while tool_call_count < MAX_TOOL_CALLS_PER_TURN:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=self.tool_registry.get_schemas(),
                tool_choice="auto",
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )

            choice = response.choices[0]

            # If LLM wants to call tools
            if choice.message.tool_calls:
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    tool_call_count += 1

                    # ---- Policy Check (before execution) ----
                    policy_result = self._check_policy(
                        tool_name, tool_args, customer_message
                    )

                    policy_step = AgentStep(
                        step_type="policy_check",
                        detail={"tool": tool_name, "args": tool_args},
                        result={
                            "allowed": policy_result.allowed,
                            "reason": policy_result.reason,
                            "risk_level": policy_result.risk_level,
                        },
                    )
                    steps.append(policy_step)

                    if policy_result.allowed:
                        # ---- Execute Tool ----
                        tool_result = self.tool_registry.call(tool_name, tool_args)

                        tool_step = AgentStep(
                            step_type="tool_call",
                            detail={"tool": tool_name, "args": tool_args},
                            result=tool_result,
                        )
                        steps.append(tool_step)
                        actions_taken.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": tool_result,
                            "policy": policy_result.reason,
                        })

                        # Send result back to LLM
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result),
                        })
                    else:
                        # ---- Escalation ----
                        escalation = {
                            "action": tool_name,
                            "args": tool_args,
                            "reason": policy_result.reason,
                            "risk_level": policy_result.risk_level,
                            "priority": policy_result.escalation_priority,
                            "policy_references": policy_result.policy_references,
                        }
                        escalations.append(escalation)

                        esc_step = AgentStep(
                            step_type="escalation",
                            detail=escalation,
                        )
                        steps.append(esc_step)

                        # Tell LLM the action was blocked
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({
                                "blocked": True,
                                "reason": policy_result.reason,
                                "action_needed": "Human approval required. A support ticket has been created for review.",
                                "risk_level": policy_result.risk_level,
                            }),
                        })

                continue  # Loop back for LLM to process tool results

            # LLM produced a final text response
            final_message = choice.message.content or ""

            llm_step = AgentStep(
                step_type="llm_response",
                detail={"message_length": len(final_message)},
            )
            steps.append(llm_step)

            return AgentResponse(
                message=final_message,
                steps=steps,
                escalations=escalations,
                actions_taken=actions_taken,
                citations=citations,
            )

        # Safety: max tool calls reached
        return AgentResponse(
            message="I apologize, but I'm having difficulty processing your request. "
                    "Let me connect you with our support team for further assistance.",
            steps=steps,
            escalations=escalations,
            actions_taken=actions_taken,
            citations=citations,
        )

    def _check_policy(self, tool_name: str, tool_args: dict,
                      customer_message: str) -> PolicyResult:
        if tool_name == "process_refund":
            order_data = {}
            order_id = tool_args.get("order_id", "")
            if order_id:
                order = self.db.get_order(order_id)
                if order:
                    order_data = order

            customer_id = order_data.get("customer_id", "")
            customer_data = self.db.get_customer(customer_id) if customer_id else None
            recent_refunds = self.db.get_recent_refunds(customer_id) if customer_id else 0

            return self.policy.check_refund(
                amount=tool_args.get("amount", 0),
                order_data=order_data,
                customer_data=customer_data,
                recent_refund_count=recent_refunds,
                customer_message=customer_message,
            )

        elif tool_name == "cancel_subscription":
            sub_id = tool_args.get("subscription_id", "")
            sub_data = self.db.get_subscription(sub_id) if sub_id else {}
            if not sub_data:
                sub_data = {}

            return self.policy.check_cancellation(
                subscription_data=sub_data,
                customer_message=customer_message,
            )

        elif tool_name == "create_support_ticket":
            return self.policy.check_ticket_creation(
                priority=tool_args.get("priority", "medium"),
                ticket_type=tool_args.get("ticket_type", "general_inquiry"),
            )

        elif tool_name == "send_notification":
            return self.policy.check_notification(
                channel=tool_args.get("channel", ""),
                message=tool_args.get("message", ""),
            )

        # Default: allow read-only tools
        return PolicyResult(
            allowed=True,
            reason="Read-only operation — no policy restriction.",
            risk_level="low",
        )

    def get_actions_log(self) -> list[dict]:
        """Get the complete audit trail."""
        return self.db.get_actions_log()
