from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import BookingChannel, DepartmentCode, ExpenseStatus, PaymentMethod, PaymentStatus, ReservationStatus

SUPPORTED_CURRENCIES = {"SLE", "USD", "EUR"}


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)
    department: DepartmentCode
    expense_approver: bool = False


class UserRead(BaseModel):
    id: UUID
    email: str
    full_name: str
    department: DepartmentCode | None
    is_admin: bool
    is_active: bool
    expense_approver: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RoomCreate(BaseModel):
    room_number: str = Field(min_length=1, max_length=30)
    room_type: str = Field(min_length=1, max_length=80)


class RoomRead(BaseModel):
    id: UUID
    room_number: str
    room_type: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ActivityCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    details: str = Field(min_length=2, max_length=5000)


class ActivityRead(BaseModel):
    id: UUID
    department: DepartmentCode
    title: str
    details: str
    recorded_by: UUID
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GuestInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=3, max_length=40)
    email: str | None = Field(default=None, max_length=320)
    model_config = ConfigDict(from_attributes=True)


class RoomSummary(BaseModel):
    id: UUID
    room_number: str
    room_type: str
    model_config = ConfigDict(from_attributes=True)


class ReservationCreate(BaseModel):
    guest: GuestInput
    room_id: UUID
    check_in_at: datetime
    check_out_at: datetime
    booking_channel: BookingChannel
    room_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def supported_currency(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in SUPPORTED_CURRENCIES:
            raise ValueError("currency must be SLE, USD, or EUR")
        return normalized

    @model_validator(mode="after")
    def valid_dates(self):
        if self.check_out_at <= self.check_in_at:
            raise ValueError("check_out_at must be after check_in_at")
        if self.check_in_at.utcoffset() is None or self.check_out_at.utcoffset() is None:
            raise ValueError("check-in and check-out must include a timezone offset")
        return self


class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus


class ReservationRead(BaseModel):
    id: UUID
    guest_id: UUID
    guest: GuestInput
    room_id: UUID
    room: RoomSummary
    check_in_at: datetime
    check_out_at: datetime
    booking_channel: BookingChannel
    status: ReservationStatus
    room_rate: Decimal
    currency: str
    notes: str | None
    created_by: UUID
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str
    method: PaymentMethod
    bank_name: str | None = Field(default=None, max_length=160)
    cheque_number: str | None = Field(default=None, max_length=100)
    transaction_reference: str | None = Field(default=None, max_length=180)
    provider: str | None = Field(default=None, max_length=120)
    paid_at: datetime

    @field_validator("currency")
    @classmethod
    def supported_currency(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in SUPPORTED_CURRENCIES:
            raise ValueError("currency must be SLE, USD, or EUR")
        return normalized

    @model_validator(mode="after")
    def validate_method_details(self):
        if self.method == PaymentMethod.cheque and (not self.cheque_number or not self.bank_name):
            raise ValueError("cheque payments require cheque_number and bank_name")
        if self.method == PaymentMethod.bank_transfer and (not self.bank_name or not self.transaction_reference):
            raise ValueError("bank transfers require bank_name and transaction_reference")
        if self.method == PaymentMethod.online and (not self.transaction_reference or not self.provider):
            raise ValueError("online payments require transaction_reference and provider")
        if self.paid_at.utcoffset() is None:
            raise ValueError("paid_at must include a timezone offset")
        return self


class PaymentRead(BaseModel):
    id: UUID
    reservation_id: UUID
    amount: Decimal
    currency: str
    method: PaymentMethod
    status: PaymentStatus
    bank_name: str | None
    cheque_number: str | None
    transaction_reference: str | None
    provider: str | None
    paid_at: datetime
    recorded_by: UUID
    model_config = ConfigDict(from_attributes=True)


class ExpenseCreate(BaseModel):
    department: DepartmentCode | None = None
    description: str = Field(min_length=3, max_length=3000)
    payee: str | None = Field(default=None, max_length=180)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str

    @field_validator("currency")
    @classmethod
    def supported_currency(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in SUPPORTED_CURRENCIES:
            raise ValueError("currency must be SLE, USD, or EUR")
        return normalized


class ExpenseDecisionInput(BaseModel):
    decision: ExpenseStatus
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("decision")
    @classmethod
    def only_final_decisions(cls, value: ExpenseStatus) -> ExpenseStatus:
        if value == ExpenseStatus.pending:
            raise ValueError("decision must be approved or rejected")
        return value


class ExpenseRead(BaseModel):
    id: UUID
    department: DepartmentCode
    description: str
    payee: str | None
    amount: Decimal
    currency: str
    status: ExpenseStatus
    submitted_by: UUID
    submitted_at: datetime
    model_config = ConfigDict(from_attributes=True)

