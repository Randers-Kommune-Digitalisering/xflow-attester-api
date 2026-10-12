"""SQLAlchemy models for attestation requests, orders and received records."""

import enum
import uuid

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Enum,
                        ForeignKey, Integer, String, UniqueConstraint, func)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _new_uuid() -> str:
    return str(uuid.uuid4())


class OrderStatus(str, enum.Enum):
    """Workflow state of a single attestation order."""

    PENDING_ORDER = "pending_order"
    ORDERED = "ordered"
    RECEIVED = "received"
    JOURNALIZED = "journalized"
    NOTIFIED = "notified"
    REJECTED = "rejected"


# native_enum=False gives a portable VARCHAR + CHECK on MSSQL, MySQL and PostgreSQL.
OrderStatusType = Enum(
    OrderStatus,
    name="order_status",
    native_enum=False,
    create_constraint=True,
    length=32,
    values_callable=lambda members: [member.value for member in members],
)


class SagsbehandlerRoles(str, enum.Enum):
    """Roles that are allowed to request attestations."""

    LEDER = "leder"
    STEDFORTRAEDER = "stedfortraeder for leder"


SagsbehandlerRoleType = Enum(
    SagsbehandlerRoles,
    name="sagsbehandler_role",
    native_enum=False,
    create_constraint=True,
    length=32,
    values_callable=lambda members: [member.value for member in members],
)


class AuthorizedSagsbehandler(Base):
    """Caseworker allowed to request attestations, loaded from the admin CSV."""

    __tablename__ = "authorized_sagsbehandler"
    dq_number = Column(String(16), primary_key=True)
    role = Column(SagsbehandlerRoleType, nullable=False)


class AttestationRequest(Base):
    """Submitted form: who requested attestations, for whom, and approval."""

    __tablename__ = "attestation_request"
    request_id = Column(String(36), primary_key=True, default=_new_uuid)
    requester_dq = Column(String(16), nullable=False)
    requester_name = Column(String(255), nullable=False)
    subject_cpr = Column(String(10), nullable=False)
    is_approved = Column(Boolean, nullable=False)
    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    orders = relationship("AttestationOrder", back_populates="request", cascade="all, delete-orphan")


class AttestationOrder(Base):
    """Order for one attestation type within a request."""

    __tablename__ = "attestation_order"
    __table_args__ = (
        UniqueConstraint("request_id", "attest_type",
                         name="uq_attestation_order_request_type"),
    )
    order_id = Column(String(36), primary_key=True, default=_new_uuid)
    request_id = Column(String(36),
                        ForeignKey("attestation_request.request_id", ondelete="CASCADE"), nullable=False, index=True)
    attest_type = Column(Integer, nullable=False)
    attest_subtype = Column(Integer)
    status = Column(OrderStatusType, nullable=False, index=True)
    external_order_ref = Column(String(255), unique=True)
    ordered_at = Column(DateTime(timezone=True))
    request = relationship("AttestationRequest", back_populates="orders")
    received_record = relationship("ReceivedRecord", back_populates="order", uselist=False)
    events = relationship("OrderEvent", back_populates="order", cascade="all, delete-orphan", order_by="OrderEvent.occurred_at")


class ReceivedRecord(Base):
    """Received criminal record and its journalization in SBSYS."""

    __tablename__ = "received_record"
    record_id = Column(String(36), primary_key=True, default=_new_uuid)
    # Nullable so unmatched records can be stored and matched manually.
    order_id = Column(String(36), ForeignKey("attestation_order.order_id"), unique=True)
    external_ref = Column(String(255))
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sbsys_sags_nr = Column(String(50))
    sbsys_sags_id = Column(Integer)
    sbsys_document_id = Column(String(50))
    journalized_at = Column(DateTime(timezone=True))
    notified_at = Column(DateTime(timezone=True))
    order = relationship("AttestationOrder", back_populates="received_record")


class OrderEvent(Base):
    """Append-only audit entry for an order status change."""

    __tablename__ = "order_event"
    event_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    order_id = Column(String(36), ForeignKey("attestation_order.order_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(OrderStatusType, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor = Column(String(50), nullable=False)
    order = relationship("AttestationOrder", back_populates="events")
