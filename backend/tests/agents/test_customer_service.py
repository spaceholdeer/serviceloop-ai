from collections import deque

from langchain.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.customer_service import CustomerServiceAgent, CustomerServiceDependencies
from app.services.data import DataService
from app.services.human import HumanService
from app.services.logistics import LogisticsService
from app.services.order import OrderService
from app.services.ticket import TicketService


class ScriptedModel:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.bound_tool_names: list[str] = []
        self.invoke_count = 0
        self.invocations = []

    def bind_tools(self, tools):
        self.bound_tool_names = [item.name for item in tools]
        return self

    def invoke(self, messages):
        self.invoke_count += 1
        self.invocations.append(messages)
        if not self.responses:
            raise RuntimeError("scripted model has no response")
        return self.responses.popleft()


class EmptyKnowledgeService:
    def search(self, _query: str, limit: int = 5) -> list[dict]:
        assert limit == 5
        return []


class ScoredKnowledgeService:
    def __init__(self, score: float):
        self.score = score

    def search(self, _query: str, limit: int = 5) -> list[dict]:
        assert limit == 5
        return [
            {
                "document_id": "refund-policy",
                "text": "售后政策证据",
                "rerank_score": self.score,
            }
        ]


class SequencedKnowledgeService:
    def __init__(self, scores: list[float]):
        self.scores = deque(scores)
        self.queries: list[str] = []

    def search(self, query: str, limit: int = 5) -> list[dict]:
        assert limit == 5
        self.queries.append(query)
        score = self.scores.popleft()
        return [
            {
                "document_id": "after-sales-policy",
                "text": "售后政策证据",
                "rerank_score": score,
            }
        ]


class BrokenOrderService:
    def get_order(self, *, customer_id: str, order_id: str) -> dict:
        raise RuntimeError(f"order backend failed: {customer_id}/{order_id}")


def dependencies(*, knowledge=None, order=None) -> CustomerServiceDependencies:
    return CustomerServiceDependencies(
        knowledge=knowledge or EmptyKnowledgeService(),
        order=order or OrderService(),
        logistics=LogisticsService(),
        ticket=TicketService(),
        human=HumanService(),
        data=DataService(),
    )


def test_agent_queries_order_and_logistics_then_answers():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_order",
                        "args": {"order_id": "ORD-202608-1001"},
                        "id": "call-order",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_logistics",
                        "args": {"order_id": "ORD-202608-1001"},
                        "id": "call-logistics",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="订单已发货，预计 8 月 16 日送达。"),
        ]
    )
    service_dependencies = dependencies()
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-001",
        customer_id="customer-demo-001",
        message="ORD-202608-1001 什么时候能到？",
    )

    assert result["final_answer"] == "订单已发货，预计 8 月 16 日送达。"
    assert result["handoff_required"] is False
    assert [event["service_name"] for event in result["tool_events"]] == [
        "get_order",
        "get_logistics",
    ]
    assert all(event["status"] == "succeeded" for event in result["tool_events"])
    assert len(service_dependencies.data.messages) == 2
    assert model.bound_tool_names == [
        "search_knowledge",
        "get_order",
        "get_logistics",
        "create_ticket",
        "request_human_handoff",
    ]


def test_agent_receives_persisted_history_before_current_question():
    model = ScriptedModel([AIMessage(content="明天上午送达。")])
    agent = CustomerServiceAgent(model=model, dependencies=dependencies())

    result = agent.invoke(
        conversation_id="conversation-with-history",
        customer_id="customer-demo-001",
        message="大约几点？",
        history=[
            {"role": "customer", "content": "订单什么时候到？"},
            {"role": "assistant", "content": "预计明天送达。"},
        ],
    )

    assert result["final_answer"] == "明天上午送达。"
    assert [type(message) for message in model.invocations[0]] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        HumanMessage,
    ]
    assert [message.content for message in model.invocations[0][1:]] == [
        "订单什么时候到？",
        "预计明天送达。",
        "大约几点？",
    ]


def test_empty_knowledge_rewrites_once_then_routes_to_human():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "超过七天的质量问题能否换货"},
                        "id": "call-knowledge",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="购买超过七天的商品质量问题是否可以换货？"),
            AIMessage(
                content=(
                    '{"intent":"policy_inquiry","action":"handoff",'
                    '"reason":"没有检索到可支持回答的条款",'
                    '"reason_code":"knowledge_insufficient"}'
                )
            ),
        ]
    )
    service_dependencies = dependencies()
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-002",
        customer_id="customer-demo-001",
        message="超过七天商品坏了还能换吗？",
    )

    assert result["handoff_required"] is True
    assert result["handoff_reason"] == "knowledge_insufficient"
    assert result["rewrite_count"] == 1
    assert len(result["retrieval_attempts"]) == 2
    assert model.invoke_count == 3
    assert result["customer_intent"] == "policy_inquiry"
    assert result["evidence_decision"]["action"] == "handoff"
    assert result["handoff"]["status"] == "queued"
    assert result["knowledge_gap_assessment"]["is_knowledge_gap"] is True
    assert result["knowledge_gap_candidate"]["status"] == "pending"
    assert len(service_dependencies.human.handoffs) == 1
    assert len(service_dependencies.data.knowledge_gap_candidates) == 1
    assert "人工客服" in result["final_answer"]


def test_unexpected_tool_failure_routes_to_human():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_order",
                        "args": {"order_id": "ORD-202608-1001"},
                        "id": "call-broken-order",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    service_dependencies = dependencies(order=BrokenOrderService())
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-003",
        customer_id="customer-demo-001",
        message="帮我查一下订单。",
    )

    assert result["handoff_required"] is True
    assert result["handoff_reason"] == "tool_failed"
    assert result["tool_events"][0]["status"] == "failed"
    assert result["knowledge_gap_assessment"]["is_knowledge_gap"] is False
    assert result["knowledge_gap_candidate"] is None
    assert len(service_dependencies.human.handoffs) == 1


def test_agent_requested_handoff_is_not_created_twice():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "request_human_handoff",
                        "args": {
                            "reason_code": "policy_unclear",
                            "agent_summary": "售后规则无法确定",
                        },
                        "id": "call-handoff",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    service_dependencies = dependencies()
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-004",
        customer_id="customer-demo-001",
        message="这个特殊情况能换货吗？",
    )

    assert result["handoff_reason"] == "policy_unclear"
    assert result["knowledge_gap_assessment"]["is_knowledge_gap"] is True
    assert result["knowledge_gap_candidate"]["status"] == "pending"
    assert len(service_dependencies.human.handoffs) == 1


def test_explicit_human_request_skips_model_and_is_not_a_knowledge_gap():
    model = ScriptedModel([])
    service_dependencies = dependencies()
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-005",
        customer_id="customer-demo-001",
        message="请帮我转人工客服。",
    )

    assert model.invoke_count == 0
    assert result["handoff_reason"] == "user_requested_human"
    assert result["knowledge_gap_assessment"]["is_knowledge_gap"] is False
    assert result["knowledge_gap_candidate"] is None


def test_refund_action_is_decided_by_agent_and_is_not_a_knowledge_gap():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "request_human_handoff",
                        "args": {
                            "reason_code": "refund_request",
                            "agent_summary": "用户明确申请退款",
                        },
                        "id": "call-refund-handoff",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    service_dependencies = dependencies()
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-006",
        customer_id="customer-demo-001",
        message="我想申请退款。",
    )

    assert model.invoke_count == 1
    assert result["handoff_reason"] == "refund_request"
    assert result["knowledge_gap_assessment"]["is_knowledge_gap"] is False
    assert result["knowledge_gap_candidate"] is None


def test_low_rerank_score_routes_to_human_and_creates_gap_candidate():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "特殊售后规则"},
                        "id": "call-low-score",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="特殊售后场景适用什么处理规则？"),
            AIMessage(
                content=(
                    '{"intent":"policy_inquiry","action":"handoff",'
                    '"reason":"证据相关性不足，无法确定特殊规则",'
                    '"reason_code":"policy_unclear"}'
                )
            ),
        ]
    )
    service_dependencies = dependencies(knowledge=ScoredKnowledgeService(0.2))
    agent = CustomerServiceAgent(
        model=model,
        dependencies=service_dependencies,
        min_rerank_score=0.35,
    )

    result = agent.invoke(
        conversation_id="conversation-007",
        customer_id="customer-demo-001",
        message="请查询特殊售后规则。",
    )

    assert result["handoff_reason"] == "policy_unclear"
    assert result["rewrite_count"] == 1
    assert len(result["retrieval_attempts"]) == 2
    assert result["knowledge_gap_candidate"]["status"] == "pending"
    assert result["evidence_decision"]["intent"] == "policy_inquiry"
    assert result["evidence_decision"]["action"] == "handoff"
    evidence = result["knowledge_gap_assessment"]["evidence"]["knowledge_searches"][0]
    assert evidence["best_rerank_score"] == 0.2
    assert evidence["minimum_rerank_score"] == 0.35


def test_high_rerank_score_returns_to_agent_for_final_answer():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "售后规则"},
                        "id": "call-high-score",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="根据售后政策，可以继续申请售后检测。"),
        ]
    )
    service_dependencies = dependencies(knowledge=ScoredKnowledgeService(0.8))
    agent = CustomerServiceAgent(
        model=model,
        dependencies=service_dependencies,
        min_rerank_score=0.35,
    )

    result = agent.invoke(
        conversation_id="conversation-008",
        customer_id="customer-demo-001",
        message="请查询售后规则。",
    )

    assert result["handoff_required"] is False
    assert result["final_answer"] == "根据售后政策，可以继续申请售后检测。"
    assert result["knowledge_gap_candidate"] is None


def test_refund_policy_question_is_not_treated_as_refund_action():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "X3 智能手表退款政策"},
                        "id": "call-refund-policy",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="根据退款政策，符合条款后可以提交申请。"),
        ]
    )
    service_dependencies = dependencies(knowledge=ScoredKnowledgeService(0.82))
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-refund-policy",
        customer_id="customer-demo-001",
        message="X3 智能手表退款政策是什么？",
    )

    assert result["handoff_required"] is False
    assert result["final_answer"] == "根据退款政策，符合条款后可以提交申请。"
    assert result["tool_events"][0]["service_name"] == "search_knowledge"


def test_return_terms_question_is_answered_from_knowledge():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "X3 智能手表退货条款"},
                        "id": "call-return-policy",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="根据退货条款，需要满足规定的时间和商品状态条件。"),
        ]
    )
    service_dependencies = dependencies(knowledge=ScoredKnowledgeService(0.84))
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-return-policy",
        customer_id="customer-demo-001",
        message="X3 智能手表退货条款是什么？",
    )

    assert result["handoff_required"] is False
    assert result["final_answer"] == "根据退货条款，需要满足规定的时间和商品状态条件。"


def test_low_rerank_decision_can_ask_for_clarification_without_handoff():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "这个条款"},
                        "id": "call-unclear-policy",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="用户想查询哪个商品的哪类售后条款？"),
            AIMessage(
                content=(
                    '{"intent":"unclear","action":"clarify",'
                    '"reason":"缺少商品型号和条款类型",'
                    '"clarifying_question":"请问你想查询哪个商品，以及退货、换货还是维修条款？"}'
                )
            ),
        ]
    )
    service_dependencies = dependencies(knowledge=ScoredKnowledgeService(0.18))
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-clarify",
        customer_id="customer-demo-001",
        message="这个条款是什么？",
    )

    assert result["handoff_required"] is False
    assert result["customer_intent"] == "unclear"
    assert result["evidence_decision"]["action"] == "clarify"
    assert result["final_answer"] == "请问你想查询哪个商品，以及退货、换货还是维修条款？"
    assert service_dependencies.human.handoffs == []


def test_low_rerank_decision_can_allow_evidence_based_answer():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "X3 退货时间"},
                        "id": "call-low-but-usable",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="X3 智能手表购买后多长时间可以退货？"),
            AIMessage(
                content=(
                    '{"intent":"policy_inquiry","action":"answer",'
                    '"reason":"检索片段直接包含 X3 的退货时间条件"}'
                )
            ),
            AIMessage(content="根据检索到的 X3 条款，可以按其中的时间条件判断。"),
        ]
    )
    service_dependencies = dependencies(knowledge=ScoredKnowledgeService(0.28))
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-low-answer",
        customer_id="customer-demo-001",
        message="X3 多久能退？",
    )

    assert result["handoff_required"] is False
    assert result["customer_intent"] == "policy_inquiry"
    assert result["evidence_decision"]["action"] == "answer"
    assert result["final_answer"] == "根据检索到的 X3 条款，可以按其中的时间条件判断。"


def test_query_rewrite_recovers_low_score_and_returns_to_agent():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "这个过了几天还能搞吗"},
                        "id": "call-original-query",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="X3 Pro 购买 9 天后出现质量问题是否可以换货？"),
            AIMessage(content="根据售后政策，可以申请质量检测后处理。"),
        ]
    )
    knowledge = SequencedKnowledgeService([0.2, 0.82])
    service_dependencies = dependencies(knowledge=knowledge)
    agent = CustomerServiceAgent(
        model=model,
        dependencies=service_dependencies,
        min_rerank_score=0.35,
    )

    result = agent.invoke(
        conversation_id="conversation-009",
        customer_id="customer-demo-001",
        message="X3 Pro 买了 9 天，这个还能搞吗？",
    )

    assert result["handoff_required"] is False
    assert result["rewrite_count"] == 1
    assert result["original_query"] == "这个过了几天还能搞吗"
    assert result["rewritten_query"] == "X3 Pro 购买 9 天后出现质量问题是否可以换货？"
    assert [item["best_rerank_score"] for item in result["retrieval_attempts"]] == [
        0.2,
        0.82,
    ]
    assert knowledge.queries == [
        "这个过了几天还能搞吗",
        "X3 Pro 购买 9 天后出现质量问题是否可以换货？",
    ]
    assert result["final_answer"] == "根据售后政策，可以申请质量检测后处理。"


def test_query_rewrite_failure_handoffs_without_retry_loop():
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "模糊问题"},
                        "id": "call-before-rewrite-failure",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    service_dependencies = dependencies(knowledge=ScoredKnowledgeService(0.1))
    agent = CustomerServiceAgent(model=model, dependencies=service_dependencies)

    result = agent.invoke(
        conversation_id="conversation-010",
        customer_id="customer-demo-001",
        message="这个怎么处理？",
    )

    assert result["handoff_reason"] == "query_rewrite_failed"
    assert result["rewrite_count"] == 1
    assert len(result["retrieval_attempts"]) == 1
    assert result["knowledge_gap_candidate"]["status"] == "pending"
