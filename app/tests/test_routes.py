# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timedelta
from unittest import mock

from sewasetu import timeutil
from sewasetu.security import hash_password
from tests.support import make_client, stop, APP_ROW


class AuthorisationTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.fake = make_client()

    def tearDown(self):
        stop(self.client)

    def test_citizen_session_cannot_approve_or_reject(self):
        with self.client.session_transaction() as s:
            s["portal_mobile"] = "9861908220"  # a logged-in citizen
        self.assertEqual(self.client.post("/admin/approve/1").status_code, 403)
        self.assertEqual(self.client.post("/admin/reject/1").status_code, 403)
        self.assertEqual(self.fake.statements("UPDATE applications"), [])

    def test_anonymous_cannot_approve(self):
        self.assertEqual(self.client.post("/admin/approve/1").status_code, 403)

    def test_admin_pages_redirect_citizens_to_login(self):
        with self.client.session_transaction() as s:
            s["portal_mobile"] = "9861908220"
        r = self.client.get("/admin/dashboard")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin", r.headers["Location"])

    def test_admin_can_approve_a_pending_application(self):
        with self.client.session_transaction() as s:
            s["admin"] = True
        self.assertEqual(self.client.post("/admin/approve/1").status_code, 302)
        sql, params = self.fake.statements("UPDATE applications")[0]
        self.assertIn("status = 'PENDING'", sql)  # cannot re-decide a decided case
        self.assertEqual(params[0], "APPROVED")

    def test_admin_login_uses_configured_credentials_not_the_old_default(self):
        r = self.client.post("/admin", data={"username": "admin",
                                             "password": "sewasetu@123"})
        self.assertIn(b"Invalid credentials", r.data)
        cfg = self.app.config["SETTINGS"]
        r = self.client.post("/admin", data={"username": cfg.admin_username,
                                             "password": cfg.admin_password})
        self.assertEqual(r.status_code, 302)


class CitizenDataIsolationTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.fake = make_client(
            {"FROM applications WHERE id = %s AND mobile": APP_ROW,
             "FROM applications WHERE id = %s": ("9861908220",) + APP_ROW[:1] + (
                 "Runu Dutta", APP_ROW[3], "Milanpur", "Borgaon", "3921227103603",
                 "CNRB0004417", APP_ROW[9], "PENDING")})

    def tearDown(self):
        stop(self.client)

    def test_application_page_is_scoped_to_the_logged_in_mobile(self):
        with self.client.session_transaction() as s:
            s["portal_mobile"] = "9861908220"
        self.assertEqual(self.client.get("/application/1").status_code, 200)
        sql, params = self.fake.statements("FROM applications")[0]
        self.assertIn("mobile = %s", sql)
        self.assertEqual(params, (1, "9861908220"))

    def test_application_page_needs_login(self):
        self.assertEqual(self.client.get("/application/1").status_code, 302)

    def test_someone_elses_acknowledgment_is_not_served(self):
        with self.client.session_transaction() as s:
            s["portal_mobile"] = "9000000001"
        self.assertEqual(self.client.get("/ack/1.pdf").status_code, 404)

    def test_acknowledgment_needs_login(self):
        self.assertEqual(self.client.get("/ack/1.pdf").status_code, 404)


class SqlInjectionTests(unittest.TestCase):
    def test_reset_password_binds_the_mobile_as_a_parameter(self):
        app, client, fake = make_client()
        try:
            payload = "9861908220' OR '1'='1"
            client.post("/status/reset", data={"mobile": payload})
            for sql, params in fake.log:
                self.assertNotIn(payload, sql)
                self.assertNotIn("'%s'", sql)
        finally:
            stop(client)

    def test_no_query_builds_sql_by_string_formatting(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "sewasetu"
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("'%s'\" %", text, path.name)
            self.assertNotIn("WHERE mobile = '", text, path.name)


class SessionAndTimeTests(unittest.TestCase):
    def test_form_session_lasts_long_enough_for_slow_typists(self):
        app, client, _ = make_client()
        try:
            self.assertGreaterEqual(app.config["PERMANENT_SESSION_LIFETIME"].total_seconds(), 1800)
        finally:
            stop(client)

    def test_deadline_is_judged_in_ist_not_container_utc(self):
        app, client, _ = make_client()
        try:
            cfg = app.config["SETTINGS"]
            # 21:00 UTC on 31 Oct is 02:30 IST on 1 Nov: window closed in IST.
            late = datetime(2026, 10, 31, 21, 0, tzinfo=timeutil.ZoneInfo("UTC"))
            fake_now = late.astimezone(timeutil.IST).replace(tzinfo=None)
            with mock.patch("sewasetu.routes.public.now_ist", return_value=fake_now):
                self.assertIn(b"has closed", client.get("/").data)
            # 20:00 UTC on 31 Oct is 01:30 IST on 1 Nov as well; 17:00 UTC is 22:30 IST: open.
            early = datetime(2026, 10, 31, 17, 0, tzinfo=timeutil.ZoneInfo("UTC"))
            fake_now = early.astimezone(timeutil.IST).replace(tzinfo=None)
            with mock.patch("sewasetu.routes.public.now_ist", return_value=fake_now):
                self.assertNotIn(b"has closed", client.get("/").data)
        finally:
            stop(client)


class SubmissionTests(unittest.TestCase):
    def _fill(self, client):
        with client.session_transaction() as s:
            s["verified_mobile"] = "9876543210"
            s["form_data"] = {
                "applicant_name": "প্ৰণৱ কুমাৰ দত্ত", "dob": "05/03/1960",
                "gender": "Male", "marital_status": "Married",
                "village": "Milanpur", "block": "Borgaon",
                "bank_account": "3921227103603", "ifsc": "CNRB0004417"}

    def test_full_assamese_name_and_correct_dob_are_stored(self):
        app, client, fake = make_client({"RETURNING id": (42,)})
        try:
            self._fill(client)
            with mock.patch("sewasetu.routes.apply_flow.send_sms_async"):
                r = client.post("/declaration")
            self.assertEqual(r.status_code, 200)
            self.assertIn("SSP".encode(), r.data)
            _, params = fake.statements("INSERT INTO applications")[0]
            self.assertEqual(params["applicant_name"], "প্ৰণৱ কুমাৰ দত্ত")
            self.assertEqual(str(params["dob"]), "1960-03-05")
        finally:
            stop(client)

    def test_submission_does_not_render_a_pdf_in_the_request(self):
        app, client, fake = make_client({"RETURNING id": (42,)})
        try:
            self._fill(client)
            with mock.patch("sewasetu.routes.apply_flow.send_sms_async"), \
                    mock.patch("sewasetu.ack_pdf.build_acknowledgment") as pdf:
                client.post("/declaration")
            pdf.assert_not_called()
        finally:
            stop(client)

    def test_invalid_step_shows_the_reason_on_the_same_page(self):
        app, client, _ = make_client()
        try:
            with client.session_transaction() as s:
                s["verified_mobile"] = "9876543210"
            r = client.post("/form/3", data={"bank_account": "12", "ifsc": "X"})
            self.assertEqual(r.status_code, 200)
            self.assertIn(b"9 to 18 digits", r.data)
            self.assertNotIn(b"Something went wrong", r.data)
        finally:
            stop(client)

    def test_upload_error_names_the_problem(self):
        import io
        app, client, _ = make_client()
        try:
            with client.session_transaction() as s:
                s["verified_mobile"] = "9876543210"
            r = client.post("/upload", data={"document": (io.BytesIO(b"x" * 10), "a.docx")},
                            content_type="multipart/form-data")
            self.assertIn(b"PDF or JPG", r.data)
            self.assertNotIn(b"ERR_VAL_47", r.data)
        finally:
            stop(client)


class OtpTests(unittest.TestCase):
    def test_wrong_otp_attempts_are_counted_and_capped(self):
        now = timeutil.now_ist()
        app, client, fake = make_client({"FROM otps WHERE mobile": (7, "123456", now, 5)})
        try:
            with client.session_transaction() as s:
                s["apply_mobile"] = "9876543210"
            r = client.post("/verify", data={"otp": "000000"}, follow_redirects=False)
            self.assertEqual(r.status_code, 302)  # sent back to request a new OTP
            self.assertEqual(client.get("/form/1").status_code, 302)
        finally:
            stop(client)

    def test_otp_is_deleted_after_use(self):
        now = timeutil.now_ist()
        app, client, fake = make_client({"FROM otps WHERE mobile": (7, "123456", now, 0)})
        try:
            with client.session_transaction() as s:
                s["apply_mobile"] = "9876543210"
            client.post("/verify", data={"otp": "123456"})
            self.assertTrue(fake.statements("DELETE FROM otps"))
        finally:
            stop(client)


if __name__ == "__main__":
    unittest.main()
