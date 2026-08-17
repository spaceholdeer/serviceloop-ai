"""订单、物流和客服工单业务模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class CustomerOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "customer_orders"

    order_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Shipment(IdMixin, TimestampMixin, Base):
    __tablename__ = "shipments"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("customer_orders.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    carrier: Mapped[str] = mapped_column(String(64), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    latest_event: Mapped[str] = mapped_column(Text, nullable=False)
    latest_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportTicket(IdMixin, TimestampMixin, Base):
    __tablename__ = "support_tickets"
    __table_args__ = (Index("ix_support_tickets_customer_status", "customer_id", "status"),)

    ticket_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

