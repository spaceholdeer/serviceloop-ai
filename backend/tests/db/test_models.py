from sqlalchemy import inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.db.base import Base
from app.db.models import (
    Conversation,
    Handoff,
    HumanResolution,
    KnowledgeDocument,
    KnowledgeVersion,
    Message,
    ToolCall,
)


def test_customer_service_core_tables_are_registered():
    assert {
        "conversations",
        "messages",
        "tool_calls",
        "handoffs",
        "human_resolutions",
        "knowledge_documents",
        "knowledge_versions",
        "knowledge_gaps",
        "knowledge_drafts",
        "customer_orders",
        "shipments",
        "support_tickets",
        "customer_feedback",
        "bad_cases",
        "improvement_tasks",
        "data_operations_runs",
    }.issubset(Base.metadata.tables)


def test_model_relationships_can_be_configured():
    configure_mappers()

    assert inspect(Conversation).relationships.messages.mapper.class_ is Message
    assert inspect(Conversation).relationships.tool_calls.mapper.class_ is ToolCall
    assert inspect(Conversation).relationships.handoffs.mapper.class_ is Handoff
    assert inspect(Handoff).relationships.resolution.mapper.class_ is HumanResolution
    assert inspect(KnowledgeDocument).relationships.versions.mapper.class_ is KnowledgeVersion


def test_all_core_tables_compile_for_mysql_8():
    dialect = mysql.dialect()

    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in sql
