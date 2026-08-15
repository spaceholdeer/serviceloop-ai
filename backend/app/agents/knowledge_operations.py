"""知识运营 Agent：聚合知识缺口并生成可编辑草稿。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Protocol, TypedDict

from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from openai import OpenAIError

from app.agents.customer_service import create_deepseek_chat_model
from app.services.knowledge_operations import KnowledgeOperationsService

SYSTEM_PROMPT = """你是 ServiceLoop 的知识运营 Agent。

你只根据给出的客户问题、检索证据和人工处理结论起草知识，不得补充不存在的政策事实。
输出一个 JSON 对象：
{"title":"简洁知识标题","content":"可直接编辑发布的知识正文","notes":"生成说明"}

当证据不足时，正文必须明确写出【待运营确认】以及需要确认的内容，不能猜测。
"""


class DraftModel(Protocol):
    def invoke(self, messages: list[Any]) -> Any: ...


class KnowledgeOperationsState(TypedDict, total=False):
    requested_gap_ids: list[str]
    operator_id: str
    gaps: list[dict[str, Any]]
    clusters: list[list[dict[str, Any]]]
    proposals: list[dict[str, Any]]
    drafts: list[dict[str, Any]]
    message: str


def _terms(text: str) -> set[str]:
    normalized = re.sub(r"\s+", "", text.casefold())
    chinese_bigrams = {
        normalized[index : index + 2]
        for index in range(max(len(normalized) - 1, 0))
        if not normalized[index : index + 2].isascii()
    }
    words = set(re.findall(r"[a-z0-9_-]{2,}", normalized))
    return chinese_bigrams | words


def _similarity(left: str, right: str) -> float:
    left_terms = _terms(left)
    right_terms = _terms(right)
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def _decode_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("knowledge draft is not a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError("knowledge draft must be an object")
    return payload


class KnowledgeOperationsAgent:
    def __init__(
        self,
        *,
        service: KnowledgeOperationsService,
        model: DraftModel | None = None,
        use_model: bool = True,
        cluster_threshold: float = 0.2,
    ):
        self.service = service
        self._model = model
        self.use_model = use_model
        self.cluster_threshold = cluster_threshold
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(KnowledgeOperationsState)
        builder.add_node("load_gaps", self._load_gaps)
        builder.add_node("cluster_gaps", self._cluster_gaps)
        builder.add_node("generate_proposals", self._generate_proposals)
        builder.add_node("persist_drafts", self._persist_drafts)
        builder.add_edge(START, "load_gaps")
        builder.add_conditional_edges(
            "load_gaps",
            self._route_after_load,
            {"continue": "cluster_gaps", "empty": END},
        )
        builder.add_edge("cluster_gaps", "generate_proposals")
        builder.add_edge("generate_proposals", "persist_drafts")
        builder.add_edge("persist_drafts", END)
        return builder.compile()

    def run(
        self,
        *,
        gap_ids: list[str] | None = None,
        operator_id: str = "operations-demo-001",
    ) -> dict[str, Any]:
        result = self.graph.invoke(
            {"requested_gap_ids": gap_ids or [], "operator_id": operator_id}
        )
        return {
            "processed_gap_count": len(result.get("gaps", [])),
            "drafts": result.get("drafts", []),
            "message": result.get("message") or "知识草稿已生成。",
        }

    def _load_gaps(self, state: KnowledgeOperationsState) -> dict[str, Any]:
        requested = state.get("requested_gap_ids") or None
        gaps = self.service.list_gaps(status="pending", ids=requested)
        return {
            "gaps": gaps,
            "message": "没有待处理的知识缺口。" if not gaps else "",
        }

    @staticmethod
    def _route_after_load(state: KnowledgeOperationsState) -> Literal["continue", "empty"]:
        return "continue" if state.get("gaps") else "empty"

    def _cluster_gaps(self, state: KnowledgeOperationsState) -> dict[str, Any]:
        clusters: list[list[dict[str, Any]]] = []
        for gap in state.get("gaps", []):
            for cluster in clusters:
                if max(
                    _similarity(str(gap["question"]), str(item["question"]))
                    for item in cluster
                ) >= self.cluster_threshold:
                    cluster.append(gap)
                    break
            else:
                clusters.append([gap])
        return {"clusters": clusters}

    def _generate_proposals(self, state: KnowledgeOperationsState) -> dict[str, Any]:
        proposals = [self._generate_cluster(cluster) for cluster in state.get("clusters", [])]
        return {"proposals": proposals}

    def _generate_cluster(self, cluster: list[dict[str, Any]]) -> dict[str, Any]:
        if self.use_model:
            try:
                model = self._model or create_deepseek_chat_model()
                response = model.invoke(
                    [
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(
                            content=json.dumps(
                                {
                                    "knowledge_gaps": [
                                        {
                                            "question": gap["question"],
                                            "reason": gap["reason"],
                                            "evidence": gap["evidence"],
                                            "human_resolution": gap["human_resolution"],
                                        }
                                        for gap in cluster
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        ),
                    ]
                )
                content = response.content
                text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                proposal = _decode_json(text)
                title = str(proposal.get("title") or "").strip()
                body = str(proposal.get("content") or "").strip()
                if title and body:
                    return {
                        "title": title,
                        "content": body,
                        "notes": str(proposal.get("notes") or "Agent 基于缺口证据生成。"),
                        "gap_ids": [str(gap["id"]) for gap in cluster],
                    }
            except (OpenAIError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
                pass
        return self._fallback_proposal(cluster)

    @staticmethod
    def _fallback_proposal(cluster: list[dict[str, Any]]) -> dict[str, Any]:
        first_question = str(cluster[0]["question"]).strip()
        title = f"{first_question[:36]}说明"
        questions = "\n".join(f"- {gap['question']}" for gap in cluster)
        resolutions = list(
            dict.fromkeys(
                str(gap["human_resolution"]["reply_to_customer"]).strip()
                for gap in cluster
                if gap.get("human_resolution")
                and gap["human_resolution"].get("reply_to_customer")
            )
        )
        if resolutions:
            resolution_text = "\n".join(f"- {item}" for item in resolutions)
        else:
            resolution_text = "【待运营确认】请补充适用条件、处理规则和例外情况。"
        return {
            "title": title,
            "content": (
                f"适用问题\n{questions}\n\n处理规则\n{resolution_text}\n\n"
                "发布前检查\n- 核对商品型号与适用时间。\n- 核对例外条件和需要转人工的边界。"
            ),
            "notes": f"Workflow fallback 汇总 {len(cluster)} 条知识缺口，未补充外部事实。",
            "gap_ids": [str(gap["id"]) for gap in cluster],
        }

    def _persist_drafts(self, state: KnowledgeOperationsState) -> dict[str, Any]:
        drafts = [
            self.service.create_draft(
                title=str(proposal["title"]),
                content=str(proposal["content"]),
                gap_ids=list(proposal["gap_ids"]),
                generated_by="knowledge_operations_agent",
                generation_notes=str(proposal.get("notes") or ""),
            )
            for proposal in state.get("proposals", [])
        ]
        return {
            "drafts": drafts,
            "message": f"已生成 {len(drafts)} 份可编辑知识草稿。",
        }
