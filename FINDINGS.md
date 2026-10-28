# Findings and fixes

## Evidence from the logs and data

| Evidence | Source |
|---|---|
| `POST /declaration` failed for 13,759 of 34,332 attempts (40%): 6,886 x HTTP 500, 6,873 x 504; median 13 s, worst on 28-31 of each month | nginx log |
| Every 500 is `FATAL: sorry, too many clients already` while "generating acknowledgment pdf" | app log |
| Nightly deemed-approval job failed 108 times with `No such file` for `config/settings.ini` (file consolidated into `app.ini` in March) | cron.log |
| 4,874 applications are PENDING; 4,100 are older than the 15-day SLA (oldest 2026-02-28) | seed data |
| 300 applications have names cut to about 6 Assamese characters | seed data |
| `GET /application/N` median 3.2 s; `/contact`, `/rti`, `/grievance` and two PDFs return 404 about 4,800 times each | nginx log |
| 75,815 `POST /upload` against 34,332 declarations reached | nginx log |
| 3,387 applications were submitted with an applicant aged 58-59 | seed data |

## Fixes, in order of citizen impact

1. **Applications failing at the last step (40%).** The acknowledgment PDF was rendered inside the submission request with about 4,000 drawing calls while holding a database connection, and connections leaked on errors. Now: pooled connections that are always returned, the PDF is made on demand with a one-call border, and the submission request only writes the record.
2. **Uploads rejected.** The limit was 100 KB while the page promised 5 MB, JPG was refused, and the only message was `ERR_VAL_47`. Now: PDF/JPG up to 5 MB with messages that say what is wrong. All other form errors (previously "Something went wrong") are specific and shown at the step where they happen, not after step 6.
3. **Deemed approvals stopped in March.** Script fixed, and replaced cron with `scheduler.py`, which has the environment and logs to the container output. It runs once at start-up, so the 4,100 overdue applications become DEEMED_APPROVED with an SMS. Use `python scripts/deemed_approval.py --dry-run` to see the count first.
4. **Names and dates stored wrongly.** Names were cut to 20 bytes (about 6 Assamese letters); they are now stored whole. Dates were read month-first when ambiguous (05/03/1960 became 3 May); now day-first only. Widows are no longer required to give their husband's employer.
5. **Security.** Any logged-in citizen could approve or reject any application (`logged_in` was checked instead of `admin`). Citizens could read anyone's application and acknowledgment by changing the number in the URL. `reset_password` had SQL injection. The session key and admin password were in the repository, which also allowed forging an admin session. The deadline was judged in UTC (closing 5.5 hours early). Now fixed, with secrets in the environment, login throttling, an OTP attempt cap and one-use OTPs.

Smaller: session 5 -> 30 minutes, duplicate-mobile detected at OTP time and by a unique index, indexes on the hot queries, unique application numbers, SMS failures reported, dead footer links removed, `Werkzeug` pinned (Flask 2.2.5 does not start with Werkzeug 3).

## Not changed, deliberately

- Existing citizen records (truncated names, the 58-59 year-old applicants) are left as they are: the correct values are not in the data.
- Passwords remain DOB-based, unsalted SHA-256, so existing citizens can still log in. This should move to OTP login.
- The SMS console at `/__gateway/` is public by design of this exercise; it exposes every OTP.
- Not verified here (no Docker, Postgres or network): `docker compose up`, the PDF with Assamese text, and the font package. Check the PDF with an Assamese name after deploying.
- `dc-briefing.mp3` was not listened to.
