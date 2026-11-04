# DORWAILA INN'S & SUIT HOTEL Management System

## 1. Purpose

This document defines the initial requirements and API design for a web-based hotel records system. The system centralizes hotel operations, department activity, guest reservations, payments, expenses, inventory, and administrative reporting.

### Users

- Admin
- General Manager
- Human Resource Management
- Front Desk / Reception
- Kitchen Management
- Housekeeping Management
- Bar Attendant Management
- Security Management
- Storekeeping / Warehouse Management

### Initial assumptions

- The first release serves one hotel location.
- The supported currencies are SLE, USD, and EUR. Use ISO-style three-letter currency codes in data and APIs.
- SLE is the default reporting currency. Preserve every transaction's original currency and amount.
- There is no public staff registration. The first Admin account is securely provisioned during installation; Admin creates all subsequent staff accounts.
- Only Admin can access or generate reports that cover all departments.
- Admin and HR users assigned the `expense_approver` permission can approve or reject expense submissions. This permission does not grant report access.

## 2. Functional requirements

### 2.1 Authentication and accounts

- Staff sign in using an account created by Admin.
- Admin can create accounts, assign one or more department roles, change permissions, disable accounts, and restore disabled accounts.
- Disabled accounts cannot sign in. Their historical records remain available for audit and reporting.
- Record account creation, disabling, restoration, role changes, sign-ins, and failed sign-in attempts.

### 2.2 Department operations

- Staff can create and update records for their assigned department according to role permissions.
- Department activity records include the department, date/time, description, creator, and relevant status.
- Admin can access all department records.
- General Manager has operational access as assigned but does not receive cross-department report access by default.

### 2.3 Reservations and front desk

Each reservation records:

- Guest name, phone number, and email address
- Room or rooms reserved
- Check-in and check-out dates and times
- Booking channel: `online`, `walk_in`, `phone`, `travel_agent`, or `other`
- Automatic creation timestamp (`recorded_at`) and creating staff member
- Status: `pending`, `confirmed`, `checked_in`, `checked_out`, or `cancelled`
- Agreed room price and currency
- Notes where needed

The system checks room availability before confirming the reservation and prevents overlapping confirmed stays for the same room. A reservation may have multiple payment records, allowing deposits, installments, refunds, or payments using different methods.

Payment methods: `cash`, `cheque`, `bank_transfer`, and `online`.

- Cheque: record cheque number and bank.
- Bank transfer: record bank and transaction reference.
- Online: record provider and transaction reference.
- Cash: record amount received and date/time.
- For every method, record amount, currency, status, payment timestamp, and staff member recording it.
- Never store full payment card numbers, security codes, or online banking credentials.

### 2.4 Expenses

- Department staff submit an expense with department, description, amount, currency, date, payee where applicable, and optional receipt attachment.
- New expenses start as `pending`.
- Admin or an HR account with `expense_approver` permission may approve or reject a pending expense and add a decision note.
- Store the approver and decision timestamp. Do not allow the submitter to approve their own expense unless they separately hold an authorized approval role; log any such decision.
- Approved expenses are included in financial reports. Pending and rejected items remain visible with their status.
- Approved transactions are corrected through traceable adjustments or reversal entries, not silent deletion.

### 2.5 Inventory

- Storekeeping manages item records, suppliers, receipts, issues to departments, adjustments, and reorder thresholds.
- Each stock transaction records item, quantity, transaction type, destination/source department, timestamp, and user.
- Stock balances are calculated from transactions and are auditable.

### 2.6 Reports

- Only Admin can view or generate cross-department reports, finance summaries, and report exports.
- Reports support a date range and relevant department/status filters.
- Department users may view their operational records as allowed by role but do not receive a reporting permission by default.
- HR expense approval does not grant access to reports.
- Every generated report is logged with the Admin account, report type, filters, and generation timestamp.
- Financial reports show original-currency totals separately. Consolidated SLE totals use a stored exchange-rate record containing rate, effective date, source, and entered-by user. Historical rates are not overwritten.

## 3. Roles and permission outline

| Permission | Admin | Department staff | HR expense approver |
|---|---:|---:|---:|
| Create/disable staff accounts | Yes | No | No, unless also Admin |
| Manage all departments | Yes | No | No |
| Record assigned department activity | Yes | Assigned department | HR records as assigned |
| Submit department expenses | Yes | Assigned department | HR records as assigned |
| Approve/reject expenses | Yes | No by default | Yes |
| View/generate all-department reports | Yes | No | No |
| View audit log | Yes | No | No |

Authorization must be checked by the API for every request. Hiding a button in the web interface is not an access control.

## 4. Recommended architecture

Use a modular monolith for the first release: one web application and one API organized into modules, backed by a relational database. This keeps deployment and maintenance manageable for one hotel while preserving clear module boundaries.

- Web client: React with TypeScript, responsive for desktop and mobile browsers.
- API: Python with FastAPI, REST/JSON, and OpenAPI documentation.
- Database: PostgreSQL with migrations and foreign-key constraints.
- File storage: private object storage or a protected server volume for receipts and attachments.
- Deployment: HTTPS, managed server or cloud host, automated database and attachment backups, and documented restore procedures.

## 5. API conventions

- Prefix: `/api/v1`
- JSON request and response bodies; timestamps use ISO 8601 with timezone offsets and are stored consistently in UTC.
- Use UUIDs for public resource IDs.
- Use pagination for list endpoints (`limit`, `cursor`) and stable sorting.
- Return standard HTTP status codes and a consistent error shape, for example `{ "error": { "code": "forbidden", "message": "You do not have permission to perform this action." } }`.
- Validate all input on the server, including enum values, currency codes, positive amounts, email format, date ordering, room availability, and payment-method-specific fields.
- Use idempotency keys for payment recording where duplicate submissions are possible.

## 6. Main endpoint groups

| Method and path | Purpose | Access |
|---|---|---|
| `POST /api/v1/auth/login` | Sign in | All users |
| `POST /api/v1/auth/logout` | Sign out | Signed-in user |
| `GET /api/v1/auth/me` | Get current account and permissions | Signed-in user |
| `GET /api/v1/admin/users` | List staff accounts | Admin |
| `POST /api/v1/admin/users` | Create account and assign role | Admin |
| `PATCH /api/v1/admin/users/{user_id}` | Change role or account status | Admin |
| `GET /api/v1/rooms` | List rooms and availability | Front Desk; Admin |
| `POST /api/v1/reservations` | Create reservation | Front Desk; Admin |
| `GET /api/v1/reservations/{reservation_id}` | View reservation | Front Desk; Admin |
| `PATCH /api/v1/reservations/{reservation_id}` | Update permitted reservation fields/status | Front Desk; Admin |
| `POST /api/v1/reservations/{reservation_id}/payments` | Record payment or refund | Front Desk; Admin |
| `POST /api/v1/departments/{department_id}/activities` | Record department activity | Assigned department; Admin |
| `POST /api/v1/expenses` | Submit expense | Assigned department; Admin |
| `GET /api/v1/expenses` | List expenses within permitted scope | Department scope; Admin |
| `POST /api/v1/expenses/{expense_id}/decision` | Approve or reject expense | Admin; HR with `expense_approver` |
| `POST /api/v1/inventory/transactions` | Receive, issue, or adjust stock | Storekeeping; Admin |
| `GET /api/v1/admin/reports/summary` | Cross-department dashboard data | Admin only |
| `GET /api/v1/admin/reports/finance` | Income and expense report | Admin only |
| `GET /api/v1/admin/reports/departments/{department_id}` | Department activity report | Admin only |
| `GET /api/v1/admin/audit-logs` | Review security and record history | Admin only |

## 7. Example reservation request

```json
{
  "guest": {
    "name": "Aminata Kamara",
    "phone": "+232XXXXXXXX",
    "email": "aminata@example.com"
  },
  "room_ids": ["room-uuid"],
  "check_in_at": "2026-12-10T14:00:00+00:00",
  "check_out_at": "2026-12-12T11:00:00+00:00",
  "booking_channel": "online",
  "room_rate": {
    "amount": "125.00",
    "currency": "USD"
  },
  "notes": "Late arrival"
}
```

The server sets `recorded_at`, `created_by`, and the initial status. Monetary amounts are decimal strings in JSON to avoid floating-point rounding errors.

### Example payment request

```json
{
  "amount": "50.00",
  "currency": "USD",
  "method": "cheque",
  "cheque_number": "CHQ-1042",
  "bank_name": "Example Bank",
  "paid_at": "2026-12-01T10:30:00+00:00"
}
```

Fields such as `cheque_number` are required for cheque payments, while online payments require a transaction reference. Do not accept or store card security codes.

## 8. Core data model

- `users`: account identity, password hash, status, timestamps.
- `roles` and `permissions`: named roles and permission assignments.
- `user_roles`: user-to-role assignments, scoped to department where applicable.
- `departments`: the eight hotel departments.
- `guests`: name, phone, email, timestamps.
- `rooms`: room number, type, capacity, and operational status.
- `reservations`: guest, booking channel, stay timestamps, status, creator, recorded timestamp.
- `reservation_rooms`: reservation-to-room links and agreed room rates.
- `payments`: reservation, amount, currency, method, reference details, status, recorded-by, paid-at.
- `department_activities`: department-specific activity and creator.
- `expenses`: department, amount, currency, payee, description, attachment, status, submitter.
- `expense_decisions`: expense, decision, approver, note, timestamp.
- `exchange_rates`: base/quote currencies, rate, effective date, source, creator.
- `inventory_items`, `suppliers`, and `inventory_transactions`.
- `audit_logs`: actor, action, target record, timestamp, and limited before/after change data.

Use database constraints to prevent invalid amounts, invalid status values, overlapping room bookings, duplicate account names, and orphaned records. Use explicit deletion policies so account deactivation never deletes business history.

## 9. Security and operational requirements

- Hash passwords with a modern password hashing algorithm; never store plaintext passwords.
- Require HTTPS and secure, HttpOnly session cookies or an equivalent secure authentication mechanism.
- Consider multi-factor authentication for Admin accounts.
- Apply rate limits to sign-in and sensitive endpoints.
- Restrict HR records and uploaded receipts to authorized roles; avoid exposing attachments through public URLs.
- Log account changes, expense decisions, financial corrections, report generation, and permission denials.
- Back up the database and attached documents on a schedule; test restoration as part of operations.
- Use database migrations, environment-based secrets, and separate development/production configuration.

## 10. Implementation stages

1. Confirm approval thresholds, reservation cancellation/refund policy, room types, and whether offline operation is required.
2. Implement authentication, Admin account management, roles, departments, and audit logging.
3. Implement rooms, guests, reservations, and multi-currency payments.
4. Implement department activity, expenses, HR/Admin approval, and inventory.
5. Implement Admin-only reporting and exports, including stored exchange-rate conversions.
6. Deploy with HTTPS, backups, restore instructions, and staff training.

## 11. Acceptance criteria for the first release

- Admin can create and disable accounts for all eight departments; disabled accounts cannot sign in and historical records remain intact.
- A department user cannot access another department's restricted records by changing a URL or API request.
- Only Admin can access cross-department and financial report endpoints.
- HR with `expense_approver` can approve/reject expenses but cannot access report endpoints.
- Reservations store the required guest details, booking channel, room, check-in/out timestamps, and automatic record timestamp.
- The system rejects a confirmed room reservation that overlaps another confirmed booking.
- Payments and expenses preserve SLE, USD, or EUR amounts and capture the required method references.
- Reports show original currency totals and use recorded exchange rates for any SLE consolidation.
- Account, expense, payment correction, and report actions are traceable in the audit log.
