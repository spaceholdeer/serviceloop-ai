"""Customer Service Agent 的 LangGraph 工具调用工作流。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from langchain.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from openai import OpenAIError
from pydantic import SecretStr

from app.core.config import get_deepseek_settings
from app.services.data import DataService
from app.services.human import HumanService
from app.services.knowledge import KnowledgeService
from app.services.logistics import LogisticsService
from app.services.order import OrderService
from app.services.ticket import TicketService

SYSTEM_PROMPT = """你是 ServiceLoop 的一线客户服务 Agent。

规则：
1. 订单、物流、知识和工单事实必须来自工具，不能猜测。
2. 查询订单或物流时只需要向工具提供订单号；客户身份由系统注入。
3. 用户明确要求人工，或明确要求执行退款、退货操作时，调用 request_human_handoff。
   “退款政策是什么”“退货条款有哪些”等信息咨询不是执行申请，必须先查询知识。
4. 资料不足、工具失败或业务规则无法确定时调用 request_human_handoff。
   reason_code 使用 refund_request、knowledge_insufficient、policy_unclear、tool_failed 或 risk_case。
5. 工具已经返回的信息不要重复查询。
6. 能解决时使用简洁中文回答，并明确引用订单、物流或知识结果。
"""

QUERY_REWRITE_PROMPT = """你负责把客服检索问题改写成一个独立、明确的问题。

要求：
1. 保留商品型号、订单号、时间、金额和否定含义，不得添加用户没有提供的事实。
2. 消除“这个、那个、还能搞吗”等依赖上下文的表达。
3. 只输出改写后的问题，不要解释，不要回答问题。
"""

EVIDENCE_DECISION_PROMPT = """你是客服工作流的证据决策节点。结合用户问题的意图、
知识检索片段和 Rerank 分数，决定下一步，但不能补充证据中不存在的业务事实。

可选 action：
- answer：检索文字直接覆盖用户问题，可以让客服 Agent 基于证据回答；
- clarify：用户问题缺少商品、时间、订单或具体诉求等关键信息，应先追问；
- handoff：证据为空、相互冲突或不足以确定业务规则，应转人工。

注意：
1. Rerank 分数是相关性信号，不是单独的转人工开关。
2. “退款/退货政策是什么”属于 policy_inquiry，不等于执行退款或退货。
3. 只有用户明确要求办理退款、退货，才属于 refund_action。
4. answer 必须能指出检索文字如何覆盖问题；拿不准时选择 clarify 或 handoff。
5. 只输出一个 JSON 对象，不要 Markdown：
{"intent":"policy_inquiry|refund_action|order_query|product_query|unclear|other",
 "action":"answer|clarify|handoff",
 "reason":"简短理由",
 "clarifying_question":"仅 clarify 时填写",
 "reason_code":"仅 handoff 时填写 knowledge_insufficient 或 policy_unclear"}
"""

DEFAULT_MIN_RERANK_SCORE = 0.35
KNOWLEDGE_GAP_REASON_CODES = {
    "knowledge_not_found",
    "low_knowledge_relevance",
    "knowledge_insufficient",
    "policy_unclear",
}
EXPLICIT_HUMAN_PHRASES = (
    "转人工",
    "人工客服",
    "真人客服",
    "找客服",
    "找人工",
    "人工处理",
    "人工介入",
    "人工接管",
    "human agent",
)
EVIDENCE_HANDOFF_REASON_CODES = {"knowledge_insufficient", "policy_unclear"}


class CustomerServiceState(MessagesState, total=False):
    conversation_id: str
    customer_id: str
    step_count: int
    tool_events: list[dict[str, Any]]
    handoff_required: bool
    handoff_reason: str | None
    handoff: dict[str, Any] | None
    original_query: str | None
    rewritten_query: str | None
    rewrite_count: int
    rewrite_required: bool
    evidence_review_required: bool
    evidence_action: str | None
    evidence_decision: dict[str, Any] | None
    customer_intent: str | None
    retrieval_attempts: list[dict[str, Any]]
    knowledge_gap_assessment: dict[str, Any] | None
    knowledge_gap_candidate: dict[str, Any] | None
    final_answer: str | None


@dataclass(slots=True)
class CustomerServiceDependencies:
    knowledge: KnowledgeService = field(default_factory=KnowledgeService)
    order: OrderService = field(default_factory=OrderService)
    logistics: LogisticsService = field(default_factory=LogisticsService)
    ticket: TicketService = field(default_factory=TicketService)
    human: HumanService = field(default_factory=HumanService)
    data: DataService = field(default_factory=DataService)


def create_deepseek_chat_model() -> ChatOpenAI:
    api_key, model = get_deepseek_settings()
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url="https://api.deepseek.com",
        temperature=0,
    )


def _message_text(message: AnyMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _latest_customer_question(messages: list[AnyMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return _message_text(message)
    return ""


def _history_message(item: dict[str, str]) -> AnyMessage:
    """把数据库中的简化消息转换成 LangChain 消息。"""

    role = item.get("role")
    content = item.get("content", "")
    if role == "customer":
        return HumanMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    return AIMessage(content=content)


def _decode_tool_result(message: ToolMessage) -> dict[str, Any]:
    if getattr(message, "status", "success") == "error":
        return {
            "ok": False,
            "data": None,
            "error_code": "tool_failed",
            "message": _message_text(message),
        }
    content = message.content
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError:
            return {"ok": True, "data": content, "error_code": None}
        if isinstance(decoded, dict):
            return decoded
    return {"ok": True, "data": content, "error_code": None}


def _decode_json_object(text: str) -> dict[str, Any]:
    """容忍模型附带代码围栏，但只接受一个 JSON 对象。"""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("evidence decision is not a JSON object")
    decoded = json.loads(cleaned[start : end + 1])
    if not isinstance(decoded, dict):
        raise TypeError("evidence decision must be an object")
    return decoded


class CustomerServiceAgent:
    def __init__(
        self,
        *,
        model: Any | None = None,
        dependencies: CustomerServiceDependencies | None = None,
        max_steps: int = 6,
        min_rerank_score: float = DEFAULT_MIN_RERANK_SCORE,
    ):
        self.dependencies = dependencies or CustomerServiceDependencies()
        self.max_steps = max_steps
        self.min_rerank_score = float(min_rerank_score)
        self.tools = self._build_tools()
        self.raw_model = model or create_deepseek_chat_model()
        self.model = self.raw_model.bind_tools(self.tools)
        self.graph = self._build_graph()

    def _build_tools(self) -> list[BaseTool]:
        dependencies = self.dependencies

        @tool("search_knowledge")
        def search_knowledge(query: str) -> dict:
            """检索售后政策、产品说明和服务规则；只能返回已有知识证据。"""

            hits = dependencies.knowledge.search(query, limit=5)
            return {"ok": True, "data": {"hits": hits}, "error_code": None}

        @tool("get_order")
        def get_order(order_id: str, runtime: ToolRuntime) -> dict:
            """根据订单号查询当前客户自己的订单。"""

            return dependencies.order.get_order(
                customer_id=str(runtime.state["customer_id"]),
                order_id=order_id,
            )

        @tool("get_logistics")
        def get_logistics(order_id: str, runtime: ToolRuntime) -> dict:
            """根据订单号查询当前客户自己的物流轨迹和预计送达时间。"""

            return dependencies.logistics.get_logistics(
                customer_id=str(runtime.state["customer_id"]),
                order_id=order_id,
            )

        @tool("create_ticket")
        def create_ticket(
            issue: str,
            runtime: ToolRuntime,
            category: str = "general",
        ) -> dict:
            """在问题需要后续处理但无需立即人工聊天时创建客服工单。"""

            return dependencies.ticket.create_ticket(
                customer_id=str(runtime.state["customer_id"]),
                conversation_id=str(runtime.state["conversation_id"]),
                issue=issue,
                category=category,
            )

        @tool("request_human_handoff")
        def request_human_handoff(
            reason_code: str,
            agent_summary: str,
            runtime: ToolRuntime,
        ) -> dict:
            """资料不足、工具失败或风险较高时创建人工接管任务。"""

            state = runtime.state
            messages = list(state["messages"])
            return dependencies.human.request_handoff(
                customer_id=str(state["customer_id"]),
                conversation_id=str(state["conversation_id"]),
                reason_code=reason_code,
                agent_summary=agent_summary,
                customer_question=_latest_customer_question(messages),
                context_package={"tool_events": list(state.get("tool_events", []))},
            )

        return [
            search_knowledge,
            get_order,
            get_logistics,
            create_ticket,
            request_human_handoff,
        ]

    def _prepare(self, state: CustomerServiceState) -> dict[str, Any]:
        question = _latest_customer_question(list(state["messages"]))
        self.dependencies.data.record_message(
            conversation_id=state["conversation_id"],
            role="customer",
            content=question,
            source="customer",
        )
        normalized_question = question.casefold()
        handoff_reason = None
        if any(phrase in normalized_question for phrase in EXPLICIT_HUMAN_PHRASES):
            handoff_reason = "user_requested_human"

        return {
            "step_count": state.get("step_count", 0),
            "tool_events": list(state.get("tool_events", [])),
            "handoff_required": handoff_reason is not None,
            "handoff_reason": handoff_reason,
            "handoff": None,
            "original_query": None,
            "rewritten_query": None,
            "rewrite_count": 0,
            "rewrite_required": False,
            "evidence_review_required": False,
            "evidence_action": None,
            "evidence_decision": None,
            "customer_intent": None,
            "retrieval_attempts": [],
            "knowledge_gap_assessment": None,
            "knowledge_gap_candidate": None,
        }

    @staticmethod
    def _route_initial(state: CustomerServiceState) -> Literal["agent", "assess_handoff"]:
        return "assess_handoff" if state.get("handoff_required") else "agent"

    def _call_agent(self, state: CustomerServiceState) -> dict[str, Any]:
        response = self.model.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
        return {
            "messages": [response],
            "step_count": state.get("step_count", 0) + 1,
        }

    def _record_tool_calls(self, state: CustomerServiceState) -> dict[str, Any]:
        messages = list(state["messages"])
        last_agent_index = next(
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], AIMessage) and messages[index].tool_calls
        )
        calls = {call["id"]: call for call in messages[last_agent_index].tool_calls}
        tool_messages = [
            message
            for message in messages[last_agent_index + 1 :]
            if isinstance(message, ToolMessage)
        ]

        new_events: list[dict[str, Any]] = []
        new_retrieval_attempts: list[dict[str, Any]] = []
        handoff_required = False
        handoff_reason: str | None = None
        handoff: dict[str, Any] | None = None
        rewrite_required = False
        evidence_review_required = False
        original_query = state.get("original_query")

        for message in tool_messages:
            call = calls.get(message.tool_call_id, {})
            result = _decode_tool_result(message)
            tool_name = str(call.get("name") or message.name or "unknown")
            event = {
                "conversation_id": state["conversation_id"],
                "tool_call_id": message.tool_call_id,
                "service_name": tool_name,
                "input": call.get("args", {}),
                "result": result,
                "status": "succeeded" if result.get("ok") else "failed",
            }
            self.dependencies.data.record_tool_call(event)
            new_events.append(event)

            if tool_name == "request_human_handoff" and result.get("ok"):
                handoff_required = True
                handoff_reason = str(call.get("args", {}).get("reason_code") or "agent_requested")
                handoff = result.get("data")
            elif tool_name == "search_knowledge" and result.get("ok"):
                hits = (result.get("data") or {}).get("hits", [])
                scores = [float(hit.get("rerank_score", 0.0)) for hit in hits]
                best_score = max(scores) if scores else None
                query = str((call.get("args") or {}).get("query") or "").strip()
                new_retrieval_attempts.append(
                    {
                        "query": query,
                        "hit_count": len(hits),
                        "best_rerank_score": best_score,
                        "minimum_rerank_score": self.min_rerank_score,
                        "attempt": state.get("rewrite_count", 0) + 1,
                    }
                )
                insufficient = not hits or best_score is None or best_score < self.min_rerank_score
                if insufficient:
                    if state.get("rewrite_count", 0) == 0:
                        rewrite_required = True
                        original_query = original_query or query
                    else:
                        evidence_review_required = True
            elif result.get("error_code") == "tool_failed":
                handoff_required = True
                handoff_reason = "tool_failed"

        return {
            "tool_events": [*state.get("tool_events", []), *new_events],
            "handoff_required": handoff_required,
            "handoff_reason": handoff_reason,
            "handoff": handoff,
            "original_query": original_query,
            "rewrite_required": rewrite_required,
            "evidence_review_required": evidence_review_required,
            "retrieval_attempts": [
                *state.get("retrieval_attempts", []),
                *new_retrieval_attempts,
            ],
        }

    def _route_after_tools(
        self, state: CustomerServiceState
    ) -> Literal["agent", "rewrite_query", "decide_evidence", "assess_handoff"]:
        if state.get("handoff_required") or state.get("step_count", 0) >= self.max_steps:
            return "assess_handoff"
        if state.get("rewrite_required"):
            return "rewrite_query"
        if state.get("evidence_review_required"):
            return "decide_evidence"
        return "agent"

    def _rewrite_query(self, state: CustomerServiceState) -> dict[str, Any]:
        original_query = state.get("original_query") or _latest_customer_question(
            list(state["messages"])
        )
        customer_question = _latest_customer_question(list(state["messages"]))
        try:
            response = self.raw_model.invoke(
                [
                    SystemMessage(content=QUERY_REWRITE_PROMPT),
                    HumanMessage(
                        content=(
                            f"用户原始问题：{customer_question}\n当前检索问题：{original_query}"
                        )
                    ),
                ]
            )
            rewritten_query = _message_text(response).strip().strip('"“”')
        except (OpenAIError, RuntimeError, ValueError):
            return {
                "rewrite_count": 1,
                "rewrite_required": False,
                "handoff_required": True,
                "handoff_reason": "query_rewrite_failed",
            }

        if not rewritten_query:
            rewritten_query = original_query
        tool_call_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_knowledge",
                    "args": {"query": rewritten_query},
                    "id": f"rewrite-search-{uuid4().hex}",
                    "type": "tool_call",
                }
            ],
        )
        return {
            "messages": [tool_call_message],
            "rewritten_query": rewritten_query,
            "rewrite_count": 1,
            "rewrite_required": False,
        }

    @staticmethod
    def _route_after_rewrite(
        state: CustomerServiceState,
    ) -> Literal["tools", "assess_handoff"]:
        return "assess_handoff" if state.get("handoff_required") else "tools"

    def _decide_evidence(self, state: CustomerServiceState) -> dict[str, Any]:
        searches: list[dict[str, Any]] = []
        for event in state.get("tool_events", []):
            if event.get("service_name") != "search_knowledge":
                continue
            result = event.get("result") or {}
            hits = (result.get("data") or {}).get("hits", []) if result.get("ok") else []
            searches.append(
                {
                    "query": (event.get("input") or {}).get("query"),
                    "hits": [
                        {
                            "document_id": hit.get("document_id"),
                            "text": str(hit.get("text") or "")[:600],
                            "rerank_score": hit.get("rerank_score"),
                        }
                        for hit in hits[:3]
                    ],
                }
            )

        payload = {
            "customer_question": _latest_customer_question(list(state["messages"])),
            "minimum_rerank_score": self.min_rerank_score,
            "retrieval_attempts": list(state.get("retrieval_attempts", [])),
            "searches": searches,
        }
        try:
            response = self.raw_model.invoke(
                [
                    SystemMessage(content=EVIDENCE_DECISION_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
            decoded = _decode_json_object(_message_text(response))
            action = str(decoded.get("action") or "").strip().lower()
            if action not in {"answer", "clarify", "handoff"}:
                raise ValueError("unsupported evidence action")
        except (json.JSONDecodeError, OpenAIError, RuntimeError, TypeError, ValueError):
            decoded = {
                "intent": "unclear",
                "action": "handoff",
                "reason": "证据决策失败，无法安全自动回答",
                "reason_code": "knowledge_insufficient",
            }
            action = "handoff"

        intent = str(decoded.get("intent") or "other").strip() or "other"
        reason = str(decoded.get("reason") or "未提供决策理由").strip()
        decision = {
            "intent": intent,
            "action": action,
            "reason": reason,
            "clarifying_question": decoded.get("clarifying_question"),
            "reason_code": decoded.get("reason_code"),
            "retrieval_attempts": list(state.get("retrieval_attempts", [])),
        }
        common = {
            "evidence_review_required": False,
            "evidence_action": action,
            "evidence_decision": decision,
            "customer_intent": intent,
        }

        if action == "answer":
            directive = SystemMessage(
                content=(
                    "证据决策节点允许继续回答。"
                    f"用户意图：{intent}；理由：{reason}。"
                    "只能使用已经返回的工具证据，不得补充或猜测条款。"
                )
            )
            return {**common, "messages": [directive], "handoff_required": False}

        if action == "clarify":
            question = str(decoded.get("clarifying_question") or "").strip()
            if not question:
                question = "为了准确查询，请补充商品型号和你想了解的具体条款。"
            return {
                **common,
                "messages": [AIMessage(content=question)],
                "handoff_required": False,
            }

        reason_code = str(decoded.get("reason_code") or "knowledge_insufficient")
        if reason_code not in EVIDENCE_HANDOFF_REASON_CODES:
            reason_code = "knowledge_insufficient"
        return {
            **common,
            "handoff_required": True,
            "handoff_reason": reason_code,
        }

    @staticmethod
    def _route_after_evidence(
        state: CustomerServiceState,
    ) -> Literal["agent", "finalize", "assess_handoff"]:
        action = state.get("evidence_action")
        if action == "answer":
            return "agent"
        if action == "clarify":
            return "finalize"
        return "assess_handoff"

    def _assess_knowledge_gap(self, state: CustomerServiceState) -> dict[str, Any]:
        reason = state.get("handoff_reason") or "max_steps_exceeded"
        knowledge_searches: list[dict[str, Any]] = []
        knowledge_evidence_missing = False

        for event in state.get("tool_events", []):
            if event.get("service_name") != "search_knowledge":
                continue
            result = event.get("result") or {}
            hits = (result.get("data") or {}).get("hits", []) if result.get("ok") else []
            scores = [float(hit.get("rerank_score", 0.0)) for hit in hits]
            best_score = max(scores) if scores else None
            knowledge_searches.append(
                {
                    "query": (event.get("input") or {}).get("query"),
                    "hit_count": len(hits),
                    "best_rerank_score": best_score,
                    "minimum_rerank_score": self.min_rerank_score,
                }
            )
            if not hits or best_score is None or best_score < self.min_rerank_score:
                knowledge_evidence_missing = True

        is_knowledge_gap = reason in KNOWLEDGE_GAP_REASON_CODES or knowledge_evidence_missing
        evidence = {
            "handoff_reason": reason,
            "knowledge_searches": knowledge_searches,
            "original_query": state.get("original_query"),
            "rewritten_query": state.get("rewritten_query"),
            "rewrite_count": state.get("rewrite_count", 0),
            "retrieval_attempts": list(state.get("retrieval_attempts", [])),
            "customer_intent": state.get("customer_intent"),
            "evidence_decision": state.get("evidence_decision"),
            "decision": (
                "knowledge_missing_or_insufficient"
                if is_knowledge_gap
                else "handoff_not_caused_by_knowledge"
            ),
        }
        recorded = self.dependencies.data.record_knowledge_gap_assessment(
            conversation_id=state["conversation_id"],
            customer_question=_latest_customer_question(list(state["messages"])),
            handoff_reason=reason,
            is_knowledge_gap=is_knowledge_gap,
            evidence=evidence,
        )
        handoff = state.get("handoff")
        if handoff is not None:
            handoff.setdefault("context_package", {})["knowledge_gap_assessment"] = recorded[
                "assessment"
            ]
        return {
            "handoff_required": True,
            "handoff_reason": reason,
            "handoff": handoff,
            "knowledge_gap_assessment": recorded["assessment"],
            "knowledge_gap_candidate": recorded["candidate"],
        }

    def _finalize(self, state: CustomerServiceState) -> dict[str, Any]:
        answer = _message_text(list(state["messages"])[-1])
        self.dependencies.data.record_message(
            conversation_id=state["conversation_id"],
            role="assistant",
            content=answer,
            source="customer_service_agent",
        )
        return {"final_answer": answer}

    def _handoff(self, state: CustomerServiceState) -> dict[str, Any]:
        reason = state.get("handoff_reason") or "max_steps_exceeded"
        handoff = state.get("handoff")
        if handoff is None:
            result = self.dependencies.human.request_handoff(
                customer_id=state["customer_id"],
                conversation_id=state["conversation_id"],
                reason_code=reason,
                agent_summary=f"Customer Service Agent 转人工：{reason}",
                customer_question=_latest_customer_question(list(state["messages"])),
                context_package={
                    "tool_events": list(state.get("tool_events", [])),
                    "knowledge_gap_assessment": state.get("knowledge_gap_assessment"),
                    "evidence_decision": state.get("evidence_decision"),
                },
            )
            handoff = result["data"]

        answer = "这个问题需要人工客服进一步确认，我已经为你创建人工接管任务。"
        message = AIMessage(content=answer)
        self.dependencies.data.record_message(
            conversation_id=state["conversation_id"],
            role="assistant",
            content=answer,
            source="customer_service_agent",
        )
        return {
            "messages": [message],
            "handoff_required": True,
            "handoff_reason": reason,
            "handoff": handoff,
            "final_answer": answer,
        }

    def _build_graph(self):
        builder = StateGraph(CustomerServiceState)
        builder.add_node("prepare", self._prepare)
        builder.add_node("agent", self._call_agent)
        builder.add_node("tools", ToolNode(self.tools, handle_tool_errors=True))
        builder.add_node("record_tools", self._record_tool_calls)
        builder.add_node("rewrite_query", self._rewrite_query)
        builder.add_node("decide_evidence", self._decide_evidence)
        builder.add_node("assess_handoff", self._assess_knowledge_gap)
        builder.add_node("finalize", self._finalize)
        builder.add_node("handoff", self._handoff)

        builder.add_edge(START, "prepare")
        builder.add_conditional_edges("prepare", self._route_initial)
        builder.add_conditional_edges(
            "agent",
            tools_condition,
            {"tools": "tools", END: "finalize"},
        )
        builder.add_edge("tools", "record_tools")
        builder.add_conditional_edges("record_tools", self._route_after_tools)
        builder.add_conditional_edges("rewrite_query", self._route_after_rewrite)
        builder.add_conditional_edges("decide_evidence", self._route_after_evidence)
        builder.add_edge("assess_handoff", "handoff")
        builder.add_edge("finalize", END)
        builder.add_edge("handoff", END)
        return builder.compile()

    def invoke(
        self,
        *,
        conversation_id: str,
        customer_id: str,
        message: str,
        history: Sequence[dict[str, str]] = (),
    ) -> CustomerServiceState:
        messages = [*(_history_message(item) for item in history), HumanMessage(content=message)]
        return self.graph.invoke(
            {
                "messages": messages,
                "conversation_id": conversation_id,
                "customer_id": customer_id,
                "step_count": 0,
                "tool_events": [],
                "handoff_required": False,
                "rewrite_count": 0,
                "rewrite_required": False,
                "evidence_review_required": False,
                "retrieval_attempts": [],
            },
            {"recursion_limit": self.max_steps * 3 + 5},
        )
