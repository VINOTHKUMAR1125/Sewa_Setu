# Sewa Setu - Old Age Pension Portal

Handover copy. Vendor maintenance contract ended 31/01/2026.

## Running

```
cp .env.example .env        # then set DB_PASSWORD, SECRET_KEY, ADMIN_PASSWORD
docker compose up --build
```

- Portal: http://localhost:8000
- SMS gateway console (simulated telecom): http://localhost:8000/__gateway/ - "sent" OTPs appear here once delivered.
- Database: Postgres, loaded from `seed/seed.sql` on first boot. Wait for the `db` container to report healthy (the seed is large); the app starts after that.
- Admin panel: http://localhost:8000/admin (username and password from `.env`).
- Health check: `/healthz`.

Secrets are no longer stored in the repository. The app refuses to start without `DB_PASSWORD`, `SECRET_KEY` and `ADMIN_PASSWORD`.

## Tests

```
cd app && python -m unittest discover -s tests -t .
```

The suite runs without a database (it uses a fake cursor) and without the PDF library.

## Layout

- `app/app.py` - entry point (`gunicorn app:app`)
- `app/sewasetu/` - application package: `config`, `db` (connection pool), `validators`, `repo` (all SQL), `security`, `sms`, `ack_pdf`, `timeutil`, `throttle`, `routes/{public,apply_flow,status,admin}`
- `app/migrations/` - idempotent SQL applied at start-up (indexes, unique constraints, OTP attempt counter)
- `app/scripts/` - `deemed_approval.py` (job) and `scheduler.py` (runs it at start-up and daily 02:00 IST)
- `app/tests/` - unit and route tests
- `FINDINGS.md` - what the evidence showed and what was changed

Production logs (Jan-Jun 2026) are in `logs/`. `dc-briefing.mp3` is the DC's briefing.
