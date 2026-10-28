# -*- coding: utf-8 -*-
"""SQL for every query the application runs. All values are bound parameters."""
from . import db

APP_COLUMNS = ("application_no, applicant_name, mobile, dob, village, block, "
               "bank_account, ifsc, status, submitted_at, decided_at")


def latest_otp(mobile):
    with db.cursor() as cur:
        cur.execute("SELECT id, code, created_at, attempts FROM otps "
                    "WHERE mobile = %s ORDER BY id DESC LIMIT 1", (mobile,))
        return cur.fetchone()


def recent_otp_count(mobile, since):
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM otps WHERE mobile = %s AND created_at > %s",
                    (mobile, since))
        return cur.fetchone()[0]


def insert_otp(mobile, code, created_at):
    with db.cursor() as cur:
        cur.execute("INSERT INTO otps (mobile, code, created_at) VALUES (%s, %s, %s)",
                    (mobile, code, created_at))


def bump_otp_attempts(otp_id):
    with db.cursor() as cur:
        cur.execute("UPDATE otps SET attempts = attempts + 1 WHERE id = %s", (otp_id,))


def clear_otps(mobile):
    with db.cursor() as cur:
        cur.execute("DELETE FROM otps WHERE mobile = %s", (mobile,))


def application_exists(mobile):
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM applications WHERE mobile = %s LIMIT 1", (mobile,))
        return cur.fetchone() is not None


def insert_application(values, portal_hash):
    """Insert the application and its status-portal account in one transaction."""
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO applications
               (application_no, applicant_name, mobile, dob, gender, marital_status,
                husband_name, husband_employer, village, block, bank_account, ifsc,
                doc_path, status, submitted_at)
               VALUES (%(application_no)s, %(applicant_name)s, %(mobile)s, %(dob)s,
                       %(gender)s, %(marital_status)s, %(husband_name)s,
                       %(husband_employer)s, %(village)s, %(block)s,
                       %(bank_account)s, %(ifsc)s, %(doc_path)s, 'PENDING',
                       %(submitted_at)s)
               RETURNING id""", values)
        new_id = cur.fetchone()[0]
        cur.execute("INSERT INTO portal_users (mobile, password_hash) VALUES (%s, %s) "
                    "ON CONFLICT (mobile) DO NOTHING", (values["mobile"], portal_hash))
        return new_id


def portal_password_hash(mobile):
    with db.cursor() as cur:
        cur.execute("SELECT password_hash FROM portal_users WHERE mobile = %s", (mobile,))
        row = cur.fetchone()
        return row[0] if row else None


def application_id_for_mobile(mobile):
    with db.cursor() as cur:
        cur.execute("SELECT id FROM applications WHERE mobile = %s "
                    "ORDER BY submitted_at DESC LIMIT 1", (mobile,))
        row = cur.fetchone()
        return row[0] if row else None


def application_for_citizen(app_id, mobile):
    """Only returns the row when it belongs to this mobile number."""
    with db.cursor() as cur:
        cur.execute("SELECT " + APP_COLUMNS + " FROM applications "
                    "WHERE id = %s AND mobile = %s", (app_id, mobile))
        return cur.fetchone()


def application_for_ack(app_id):
    with db.cursor() as cur:
        cur.execute("SELECT mobile, application_no, applicant_name, dob, village, "
                    "block, bank_account, ifsc, submitted_at, status "
                    "FROM applications WHERE id = %s", (app_id,))
        return cur.fetchone()


def dob_for_reset(mobile):
    with db.cursor() as cur:
        cur.execute("SELECT dob FROM applications WHERE mobile = %s LIMIT 1", (mobile,))
        row = cur.fetchone()
        return row[0] if row else None


def reset_portal_password(mobile, password_hash):
    with db.cursor() as cur:
        cur.execute("UPDATE portal_users SET password_hash = %s WHERE mobile = %s",
                    (password_hash, mobile))
        return cur.rowcount


def portal_user_exists(mobile):
    return portal_password_hash(mobile) is not None


# ---- admin -----------------------------------------------------------------

def counts_by_status():
    with db.cursor() as cur:
        cur.execute("SELECT status, count(*) FROM applications GROUP BY status")
        return cur.fetchall()


def overdue_pending(cutoff):
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM applications WHERE status = 'PENDING' "
                    "AND submitted_at < %s", (cutoff,))
        return cur.fetchone()[0]


def pending_by_block():
    with db.cursor() as cur:
        cur.execute("SELECT block, count(*) FROM applications WHERE status = 'PENDING' "
                    "GROUP BY block ORDER BY count(*) DESC")
        return cur.fetchall()


def admin_list(status, offset, limit=50):
    with db.cursor() as cur:
        cur.execute("SELECT id, application_no, applicant_name, mobile, block, status, "
                    "submitted_at FROM applications WHERE status = %s "
                    "ORDER BY submitted_at ASC LIMIT %s OFFSET %s",
                    (status, limit, offset))
        return cur.fetchall()


def admin_application(app_id):
    with db.cursor() as cur:
        cur.execute("SELECT application_no, applicant_name, mobile, dob, gender, "
                    "marital_status, village, block, bank_account, ifsc, doc_path, "
                    "status, submitted_at, decided_at, decided_by "
                    "FROM applications WHERE id = %s", (app_id,))
        return cur.fetchone()


def decide(app_id, new_status, decided_at, decided_by):
    """Only a PENDING application can be decided. Returns rows changed."""
    with db.cursor() as cur:
        cur.execute("UPDATE applications SET status = %s, decided_at = %s, "
                    "decided_by = %s WHERE id = %s AND status = 'PENDING'",
                    (new_status, decided_at, decided_by, app_id))
        return cur.rowcount
