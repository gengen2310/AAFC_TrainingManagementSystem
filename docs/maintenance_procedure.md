# Maintenance Procedure

## Routine Maintenance Tasks

### Weekly

- Verify backend health: `curl http://localhost:8000/api/health`
- Check access log for unexpected 4xx/5xx patterns
- Backup the database (see `backup_and_restore.md`)

### Monthly

- Review audit log for unusual access patterns
- Verify facilitator records are current
- Check for expired access codes (access codes have no built-in expiry — review with unit CO)

### Start of Training Year

1. Create new planning year via Annual Program
2. Generate parade dates (verify weekday and holiday exclusions)
3. Add/update holiday periods for the new year
4. Add anchor events from the CEA calendar
5. Assign curriculum missions using the Training Planner
6. Confirm timing template is correct for the unit

### End of Training Year

1. Export closeout reports for the year
2. Run year rollover to create the next planning year
3. Archive the completed year (`active_status = False` on PlanningYear)
4. Remove facilitators who have left the unit

---

## DB Reset (Development Only)

```bash
rm -f backend/aafc_tms.db
bash RUN_TMS_BACKEND_MAC.sh
```

This rebuilds all tables and re-seeds demo data. **Do not run in a live deployment.**

---

## Alembic Migrations

To apply new migrations (e.g. after pulling an update):

```bash
cd backend
alembic upgrade head
```

To check current revision:

```bash
alembic current
```

Current migration head: `d1e3f5a7c9b0` (V14 Training Planner)

---

## Log Location

The backend writes to stdout/stderr. To capture to file:

```bash
bash RUN_TMS_BACKEND_MAC.sh >> logs/backend.log 2>&1 &
```

Log format (access log):
```
{"method":"GET","path":"/api/health","status":200,"dur_ms":1.2,"client":"127.0.0.1"}
```

---

## Access Code Management

Access codes are one-time-use from a user perspective but do not expire automatically. To rotate:

1. Log in as `system_admin` or `national_admin`
2. Navigate to **Accounts**
3. Use the "Reset Access Code" action for the relevant user

Previous codes become invalid immediately. Codes are stored as bcrypt hashes — they cannot be retrieved in plaintext.

---

## Dependency Updates

```bash
cd backend
pip install --upgrade -r requirements.txt
```

Check for CVEs in key dependencies:
- FastAPI
- SQLAlchemy
- python-jose (JWT)
- passlib / bcrypt
