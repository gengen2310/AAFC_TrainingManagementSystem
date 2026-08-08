# Backend Rules — AAFC TMS

## Stack

- FastAPI 0.110+, SQLAlchemy 2.0, Python 3.13, Alembic, Pydantic v2
- SQLite for local demo; PostgreSQL for production
- JWT HS256 via python-jose, passlib pbkdf2_sha256 for access-code hashing (`app/security.py`)

## Permission model

- All role/scope checks go through `permissions.py` — Principal dataclass + require_* helpers
- Use `require_system_admin(p)` for system-only endpoints
- Use `require_role(p, *roles)` for mixed-role endpoints
- Use `require_can_view_squadron / require_can_write_squadron` for tenancy
- Never write ad hoc role checks inline in routers

## Migrations

- New migration: run `alembic heads` first and set `down_revision` to the actual current head — never
  hardcode a specific revision id in this file, it goes stale the moment another migration lands (this
  line itself previously hardcoded `e7a9c2f4b8d1`, which drifted 3 migrations behind the real head)
- Use batch_alter_table for SQLite-compatible ALTER TABLE
- Never drop columns or rename primary keys without confirming SQLite compatibility
- Run `alembic upgrade head` after adding a migration

## Models

- All models inherit from `Base` in `database.py`
- Use `UUIDMixin` for UUID primary keys
- Use `TimestampMixin` for created_at/updated_at
- New models must be imported in `models/__init__.py`

## Audit logging

- Call `services.audit(db, p, object_type=..., object_id=..., action=...)` for all privileged state changes
- system_admin endpoint writes always include old/new values where meaningful
- Do not audit reads (only writes, auth, and configuration changes)

## Tests

- Every new endpoint needs at least: happy-path test, forbidden test, unauthenticated test
- Use `tests/conftest.py` fixtures (`client`, `login`)
- Run `python -m pytest tests/ -q` from backend/ — must pass before packaging

## Error handling

- Raise `HTTPException(403, ...)` for permission denials
- Raise `HTTPException(401, ...)` only from `get_principal` (already done)
- Raise `HTTPException(400, ...)` for validation/business logic failures
- Never return stack traces in production (main.py 500 handler suppresses)
