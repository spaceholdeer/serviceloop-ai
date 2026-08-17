from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.customer import get_runtime_knowledge_service
from app.api.customer import router as customer_router
from app.api.operations import router as operations_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_runtime_knowledge_service()
    yield


app = FastAPI(title="ServiceLoop AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(customer_router)
app.include_router(agent_router)
app.include_router(operations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "serviceloop-api"}
