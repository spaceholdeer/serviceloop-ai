"""运营端最小数据接口。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.agents.customer_service import CustomerServiceDependencies
from app.api.customer import get_customer_service_dependencies

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/knowledge-gaps")
def list_knowledge_gap_candidates(
    dependencies: Annotated[
        CustomerServiceDependencies, Depends(get_customer_service_dependencies)
    ],
    status: str = "pending",
) -> list[dict[str, Any]]:
    return dependencies.data.list_knowledge_gap_candidates(status=status)
