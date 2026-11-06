from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import (
    AuditLog, DepartmentActivity, DepartmentCode, Expense, ExpenseDecision, ExpenseStatus,
    Guest, Payment, Reservation, ReservationStatus, Room, User, now_utc,
)
from app.config import settings
from app.schemas import (
    ActivityCreate, ActivityRead, ExpenseCreate, ExpenseDecisionInput, ExpenseRead, PaymentCreate, PaymentRead,
    ReservationCreate, ReservationRead, ReservationStatusUpdate, RoomCreate,
    RoomRead, UserCreate, UserRead,
)
from app.security import (
    _dummy_password_hash, create_access_token, current_user, hash_password,
    require_admin, verify_password,
)

app = FastAPI(title="Dorwaila Hotel Management API", version="0.1.0")
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


def write_audit(db: Session, actor_id: UUID | None, action: str, target_type: str, target_id: str, details: str = "") -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, details=details[:4000]))


def require_front_desk(user: User) -> None:
    if not user.is_admin and user.department != DepartmentCode.front_desk:
        raise HTTPException(status_code=403, detail="Front desk permission required")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/auth/token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Db):
    email = form.username.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    # Hash a dummy value on unknown accounts to reduce account-enumeration timing differences.
    if not verify_password(form.password, user.password_hash if user else _dummy_password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")
    write_audit(db, user.id, "sign_in", "user", str(user.id))
    db.commit()
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@app.get("/api/v1/auth/me", response_model=UserRead)
def me(user: CurrentUser):
    return user


@app.get("/api/v1/admin/users", response_model=list[UserRead])
def list_users(db: Db, admin: AdminUser):
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@app.post("/api/v1/admin/users", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Db, admin: AdminUser):
    email = payload.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        department=payload.department,
        expense_approver=payload.expense_approver,
        is_admin=False,
    )
    db.add(user)
    db.flush()
    write_audit(db, admin.id, "create_user", "user", str(user.id), f"department={payload.department.value}")
    db.commit()
    db.refresh(user)
    return user


@app.patch("/api/v1/admin/users/{user_id}/disable", response_model=UserRead)
def disable_user(user_id: UUID, db: Db, admin: AdminUser):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Admin cannot disable the account currently in use")
    if user.is_admin:
        active_admins = db.scalar(select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True))) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot disable the last active Admin account")
    user.is_active = False
    write_audit(db, admin.id, "disable_user", "user", str(user.id))
    db.commit()
    db.refresh(user)
    return user


@app.patch("/api/v1/admin/users/{user_id}/enable", response_model=UserRead)
def enable_user(user_id: UUID, db: Db, admin: AdminUser):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    write_audit(db, admin.id, "enable_user", "user", str(user.id))
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/v1/admin/rooms", response_model=RoomRead, status_code=201)
def create_room(payload: RoomCreate, db: Db, admin: AdminUser):
    room_number = payload.room_number.strip()
    if db.scalar(select(Room.id).where(Room.room_number == room_number)):
        raise HTTPException(status_code=409, detail="Room number already exists")
    room = Room(room_number=room_number, room_type=payload.room_type.strip())
    db.add(room)
    db.flush()
    write_audit(db, admin.id, "create_room", "room", str(room.id))
    db.commit()
    db.refresh(room)
    return room


@app.get("/api/v1/rooms", response_model=list[RoomRead])
def list_rooms(db: Db, user: CurrentUser):
    require_front_desk(user)
    return list(db.scalars(select(Room).where(Room.is_active.is_(True)).order_by(Room.room_number)))


def room_is_available(db: Session, room_id: UUID, check_in: datetime, check_out: datetime, exclude_id: UUID | None = None) -> bool:
    conflicts = select(Reservation.id).where(
        Reservation.room_id == room_id,
        Reservation.status.in_([ReservationStatus.pending, ReservationStatus.confirmed, ReservationStatus.checked_in]),
        Reservation.check_in_at < check_out,
        Reservation.check_out_at > check_in,
    )
    if exclude_id:
        conflicts = conflicts.where(Reservation.id != exclude_id)
    return db.scalar(conflicts.limit(1)) is None


@app.post("/api/v1/reservations", response_model=ReservationRead, status_code=201)
def create_reservation(payload: ReservationCreate, db: Db, user: CurrentUser):
    require_front_desk(user)
    room = db.get(Room, payload.room_id)
    if not room or not room.is_active:
        raise HTTPException(status_code=404, detail="Active room not found")
    if not room_is_available(db, room.id, payload.check_in_at, payload.check_out_at):
        raise HTTPException(status_code=409, detail="Room is already reserved for part of this time")
    guest_data = payload.guest
    guest = Guest(name=guest_data.name.strip(), phone=guest_data.phone.strip(), email=guest_data.email)
    db.add(guest)
    db.flush()
    reservation = Reservation(
        guest_id=guest.id,
        room_id=room.id,
        check_in_at=payload.check_in_at,
        check_out_at=payload.check_out_at,
        booking_channel=payload.booking_channel,
        room_rate=payload.room_rate,
        currency=payload.currency,
        notes=payload.notes,
        created_by=user.id,
        status=ReservationStatus.pending,
    )
    db.add(reservation)
    db.flush()
    write_audit(db, user.id, "create_reservation", "reservation", str(reservation.id))
    db.commit()
    db.refresh(reservation)
    return reservation


@app.get("/api/v1/reservations", response_model=list[ReservationRead])
def list_reservations(db: Db, user: CurrentUser, from_at: datetime | None = None, to_at: datetime | None = None):
    require_front_desk(user)
    query = select(Reservation).order_by(Reservation.check_in_at)
    if from_at:
        query = query.where(Reservation.check_out_at >= from_at)
    if to_at:
        query = query.where(Reservation.check_in_at <= to_at)
    return list(db.scalars(query.limit(500)))


@app.get("/api/v1/reservations/{reservation_id}", response_model=ReservationRead)
def get_reservation(reservation_id: UUID, db: Db, user: CurrentUser):
    require_front_desk(user)
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@app.patch("/api/v1/reservations/{reservation_id}/status", response_model=ReservationRead)
def update_reservation_status(reservation_id: UUID, payload: ReservationStatusUpdate, db: Db, user: CurrentUser):
    require_front_desk(user)
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    allowed_transitions = {
        ReservationStatus.pending: {ReservationStatus.confirmed, ReservationStatus.cancelled},
        ReservationStatus.confirmed: {ReservationStatus.checked_in, ReservationStatus.cancelled},
        ReservationStatus.checked_in: {ReservationStatus.checked_out},
        ReservationStatus.checked_out: set(),
        ReservationStatus.cancelled: set(),
    }
    if payload.status != reservation.status and payload.status not in allowed_transitions[reservation.status]:
        raise HTTPException(status_code=409, detail="Invalid reservation status transition")
    if payload.status == ReservationStatus.confirmed and not room_is_available(
        db, reservation.room_id, reservation.check_in_at, reservation.check_out_at, reservation.id
    ):
        raise HTTPException(status_code=409, detail="Room is already reserved for part of this time")
    reservation.status = payload.status
    write_audit(db, user.id, "update_reservation_status", "reservation", str(reservation.id), payload.status.value)
    db.commit()
    db.refresh(reservation)
    return reservation


@app.post("/api/v1/reservations/{reservation_id}/payments", response_model=PaymentRead, status_code=201)
def record_payment(reservation_id: UUID, payload: PaymentCreate, db: Db, user: CurrentUser):
    require_front_desk(user)
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    payment = Payment(reservation_id=reservation.id, recorded_by=user.id, **payload.model_dump())
    db.add(payment)
    db.flush()
    write_audit(db, user.id, "record_payment", "payment", str(payment.id), f"reservation={reservation.id};currency={payment.currency}")
    db.commit()
    db.refresh(payment)
    return payment


@app.get("/api/v1/reservations/{reservation_id}/payments", response_model=list[PaymentRead])
def list_reservation_payments(reservation_id: UUID, db: Db, user: CurrentUser):
    require_front_desk(user)
    if not db.get(Reservation, reservation_id):
        raise HTTPException(status_code=404, detail="Reservation not found")
    return list(db.scalars(select(Payment).where(Payment.reservation_id == reservation_id).order_by(Payment.paid_at)))


@app.post("/api/v1/departments/{department}/activities", response_model=ActivityRead, status_code=201)
def create_department_activity(department: DepartmentCode, payload: ActivityCreate, db: Db, user: CurrentUser):
    if not user.is_admin and user.department != department:
        raise HTTPException(status_code=403, detail="You may only record activity for your department")
    activity = DepartmentActivity(
        department=department,
        title=payload.title.strip(),
        details=payload.details.strip(),
        recorded_by=user.id,
    )
    db.add(activity)
    db.flush()
    write_audit(db, user.id, "record_department_activity", "department_activity", str(activity.id))
    db.commit()
    db.refresh(activity)
    return activity


@app.get("/api/v1/departments/{department}/activities", response_model=list[ActivityRead])
def list_department_activities(department: DepartmentCode, db: Db, user: CurrentUser, limit: int = 100):
    if not user.is_admin and user.department != department:
        raise HTTPException(status_code=403, detail="You may only access activity for your department")
    safe_limit = max(1, min(limit, 500))
    query = select(DepartmentActivity).where(DepartmentActivity.department == department)
    return list(db.scalars(query.order_by(DepartmentActivity.recorded_at.desc()).limit(safe_limit)))


@app.post("/api/v1/expenses", response_model=ExpenseRead, status_code=201)
def submit_expense(payload: ExpenseCreate, db: Db, user: CurrentUser):
    department = payload.department or user.department
    if not user.is_admin and (department is None or user.department != department):
        raise HTTPException(status_code=403, detail="Expense must belong to your assigned department")
    if department is None:
        raise HTTPException(status_code=422, detail="department is required")
    expense = Expense(
        department=department,
        description=payload.description.strip(),
        payee=payload.payee,
        amount=payload.amount,
        currency=payload.currency,
        submitted_by=user.id,
        status=ExpenseStatus.pending,
    )
    db.add(expense)
    db.flush()
    write_audit(db, user.id, "submit_expense", "expense", str(expense.id))
    db.commit()
    db.refresh(expense)
    return expense


@app.get("/api/v1/expenses", response_model=list[ExpenseRead])
def list_expenses(db: Db, user: CurrentUser, status_filter: ExpenseStatus | None = None):
    if not user.is_admin and user.department is None:
        raise HTTPException(status_code=403, detail="Department permission required")
    query = select(Expense).order_by(Expense.submitted_at.desc())
    if not user.is_admin and not user.expense_approver:
        query = query.where(Expense.department == user.department)
    if status_filter:
        query = query.where(Expense.status == status_filter)
    return list(db.scalars(query.limit(500)))


@app.post("/api/v1/expenses/{expense_id}/decision", response_model=ExpenseRead)
def decide_expense(expense_id: UUID, payload: ExpenseDecisionInput, db: Db, user: CurrentUser):
    if not user.is_admin and not user.expense_approver:
        raise HTTPException(status_code=403, detail="Expense approver permission required")
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.status != ExpenseStatus.pending:
        raise HTTPException(status_code=409, detail="Only pending expenses can be decided")
    if expense.submitted_by == user.id:
        raise HTTPException(status_code=403, detail="A user cannot approve their own expense")
    expense.status = payload.decision
    decision = ExpenseDecision(expense_id=expense.id, decision=payload.decision, note=payload.note, decided_by=user.id)
    db.add(decision)
    write_audit(db, user.id, "expense_decision", "expense", str(expense.id), payload.decision.value)
    db.commit()
    db.refresh(expense)
    return expense


@app.get("/api/v1/admin/reports/finance")
def finance_report(db: Db, admin: AdminUser, from_at: datetime | None = None, to_at: datetime | None = None):
    expense_query = select(Expense.department, Expense.currency, Expense.status, func.sum(Expense.amount).label("total"))
    if from_at:
        expense_query = expense_query.where(Expense.submitted_at >= from_at)
    if to_at:
        expense_query = expense_query.where(Expense.submitted_at <= to_at)
    expense_rows = db.execute(expense_query.group_by(Expense.department, Expense.currency, Expense.status)).all()
    payment_query = select(Payment.currency, Payment.status, func.sum(Payment.amount).label("total"))
    if from_at:
        payment_query = payment_query.where(Payment.paid_at >= from_at)
    if to_at:
        payment_query = payment_query.where(Payment.paid_at <= to_at)
    payment_rows = db.execute(payment_query.group_by(Payment.currency, Payment.status)).all()
    write_audit(db, admin.id, "generate_finance_report", "report", "finance", f"from={from_at};to={to_at}")
    db.commit()
    return {
        "period": {"from": from_at, "to": to_at},
        "reporting_currency": settings.reporting_currency,
        "expense_totals_by_department_currency_status": [
            {"department": dept.value, "currency": currency, "status": state.value, "amount": str(total)}
            for dept, currency, state, total in expense_rows
        ],
        "payment_totals_by_currency_status": [
            {"currency": currency, "status": state.value, "amount": str(total)}
            for currency, state, total in payment_rows
        ],
        "note": "Totals remain grouped by original currency. Exchange-rate conversion is not implemented yet.",
    }


@app.get("/api/v1/admin/reports/departments/{department}")
def department_report(department: DepartmentCode, db: Db, admin: AdminUser):
    expense_count = db.scalar(select(func.count(Expense.id)).where(Expense.department == department)) or 0
    expenses = db.execute(
        select(Expense.currency, Expense.status, func.sum(Expense.amount))
        .where(Expense.department == department)
        .group_by(Expense.currency, Expense.status)
    ).all()
    activity_count = db.scalar(select(func.count(DepartmentActivity.id)).where(DepartmentActivity.department == department)) or 0
    write_audit(db, admin.id, "generate_department_report", "department", department.value)
    db.commit()
    return {
        "department": department.value,
        "activity_count": activity_count,
        "expense_count": expense_count,
        "expense_totals": [
            {"currency": currency, "status": state.value, "amount": str(total)}
            for currency, state, total in expenses
        ],
    }


@app.get("/api/v1/admin/reports/summary")
def admin_summary(db: Db, admin: AdminUser):
    summary = []
    for department in DepartmentCode:
        activity_count = db.scalar(select(func.count(DepartmentActivity.id)).where(DepartmentActivity.department == department)) or 0
        expense_count = db.scalar(select(func.count(Expense.id)).where(Expense.department == department)) or 0
        pending_expense_count = db.scalar(
            select(func.count(Expense.id)).where(
                Expense.department == department,
                Expense.status == ExpenseStatus.pending,
            )
        ) or 0
        summary.append({
            "department": department.value,
            "activity_count": activity_count,
            "expense_count": expense_count,
            "pending_expense_count": pending_expense_count,
        })
    write_audit(db, admin.id, "generate_summary_report", "report", "summary")
    db.commit()
    return {"departments": summary}


@app.get("/api/v1/admin/audit-logs")
def audit_logs(db: Db, admin: AdminUser, limit: int = 100):
    safe_limit = max(1, min(limit, 500))
    entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(safe_limit)).all()
    return [
        {"id": str(entry.id), "actor_id": str(entry.actor_id) if entry.actor_id else None,
         "action": entry.action, "target_type": entry.target_type, "target_id": entry.target_id,
         "details": entry.details, "created_at": entry.created_at}
        for entry in entries
    ]

