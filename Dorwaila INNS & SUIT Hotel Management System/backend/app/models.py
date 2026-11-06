import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class DepartmentCode(str, enum.Enum):
    general_manager = "general_manager"
    human_resources = "human_resources"
    front_desk = "front_desk"
    kitchen = "kitchen"
    housekeeping = "housekeeping"
    bar = "bar"
    security = "security"
    storekeeping = "storekeeping"


class BookingChannel(str, enum.Enum):
    online = "online"
    walk_in = "walk_in"
    phone = "phone"
    travel_agent = "travel_agent"
    other = "other"


class ReservationStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    checked_in = "checked_in"
    checked_out = "checked_out"
    cancelled = "cancelled"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    cheque = "cheque"
    bank_transfer = "bank_transfer"
    online = "online"


class PaymentStatus(str, enum.Enum):
    recorded = "recorded"
    refunded = "refunded"
    voided = "voided"


class ExpenseStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(512))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expense_approver: Mapped[bool] = mapped_column(Boolean, default=False)
    department: Mapped[DepartmentCode | None] = mapped_column(Enum(DepartmentCode), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Guest(Base):
    __tablename__ = "guests"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DepartmentActivity(Base):
    __tablename__ = "department_activities"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    department: Mapped[DepartmentCode] = mapped_column(Enum(DepartmentCode), index=True)
    title: Mapped[str] = mapped_column(String(180))
    details: Mapped[str] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    room_type: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    guest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guests.id"), index=True)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"), index=True)
    guest: Mapped[Guest] = relationship()
    room: Mapped[Room] = relationship()
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    check_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    booking_channel: Mapped[BookingChannel] = mapped_column(Enum(BookingChannel))
    status: Mapped[ReservationStatus] = mapped_column(Enum(ReservationStatus), default=ReservationStatus.pending)
    room_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reservation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reservations.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.recorded)
    bank_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cheque_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    department: Mapped[DepartmentCode] = mapped_column(Enum(DepartmentCode), index=True)
    description: Mapped[str] = mapped_column(Text)
    payee: Mapped[str | None] = mapped_column(String(180), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus), default=ExpenseStatus.pending, index=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ExpenseDecision(Base):
    __tablename__ = "expense_decisions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expenses.id"), index=True)
    decision: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

