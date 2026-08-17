"""数据运营 Agent：把运行信号转成 Bad Case 和可执行改进任务。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.db.models import BadCase, DataOperationsRun, ImprovementTask
from app.services.data_operations import DataOperationsService


class DataOperationsState(TypedDict, total=False):
    operator_id: str
    signals: list[dict[str, Any]]
    created_cases: list[BadCase]
    groups: dict[str, list[BadCase]]
    tasks: list[ImprovementTask]
    run: DataOperationsRun
    has_work: bool


class DataOperationsAgent:
    """LangGraph workflow；分析有条件分支，写入由应用服务统一事务提交。"""

    def __init__(self, service: DataOperationsService):
        self.service = service
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(DataOperationsState)
        workflow.add_node("load_signals", self._load_signals)
        workflow.add_node("materialize_cases", self._materialize_cases)
        workflow.add_node("group_cases", self._group_cases)
        workflow.add_node("create_tasks", self._create_tasks)
        workflow.add_node("record_run", self._record_run)
        workflow.add_edge(START, "load_signals")
        workflow.add_conditional_edges(
            "load_signals",
            self._route_after_load,
            {"analyze": "materialize_cases", "empty": "record_run"},
        )
        workflow.add_edge("materialize_cases", "group_cases")
        workflow.add_edge("group_cases", "create_tasks")
        workflow.add_edge("create_tasks", "record_run")
        workflow.add_edge("record_run", END)
        return workflow.compile()

    def run(self, *, operator_id: str = "operations-demo-001") -> dict[str, Any]:
        result = self.graph.invoke({"operator_id": operator_id})
        return {
            "run": result["run"],
            "bad_cases": result.get("created_cases", []),
            "improvement_tasks": result.get("tasks", []),
        }

    def _load_signals(self, _state: DataOperationsState) -> dict[str, Any]:
        signals = self.service.collect_signals()
        has_open_cases = bool(self.service.list_bad_cases(status="open"))
        return {"signals": signals, "has_work": bool(signals) or has_open_cases}

    @staticmethod
    def _route_after_load(state: DataOperationsState) -> Literal["analyze", "empty"]:
        return "analyze" if state.get("has_work") else "empty"

    def _materialize_cases(self, state: DataOperationsState) -> dict[str, Any]:
        return {"created_cases": self.service.materialize_bad_cases(state.get("signals", []))}

    def _group_cases(self, _state: DataOperationsState) -> dict[str, Any]:
        return {"groups": self.service.group_open_cases()}

    def _create_tasks(self, state: DataOperationsState) -> dict[str, Any]:
        return {"tasks": self.service.create_improvement_tasks(state.get("groups", {}))}

    def _record_run(self, state: DataOperationsState) -> dict[str, Any]:
        run = self.service.record_run(
            operator_id=state["operator_id"],
            signal_count=len(state.get("signals", [])),
            created_case_count=len(state.get("created_cases", [])),
            tasks=state.get("tasks", []),
        )
        return {"run": run}
