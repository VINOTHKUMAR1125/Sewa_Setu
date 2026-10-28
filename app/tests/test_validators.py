# -*- coding: utf-8 -*-
import unittest
from datetime import date

from sewasetu import validators as v


class MobileTests(unittest.TestCase):
    def test_plain_and_prefixed_numbers_normalise(self):
        for raw in ("9876543210", " 98765 43210 ", "+919876543210", "09876543210"):
            self.assertEqual(v.normalize_mobile(raw), "9876543210")

    def test_bad_numbers_get_a_specific_message(self):
        with self.assertRaises(v.ValidationError) as ctx:
            v.normalize_mobile("12345")
        self.assertIn("10-digit", str(ctx.exception))
        self.assertNotIn("Something went wrong", str(ctx.exception))


class DobTests(unittest.TestCase):
    def test_day_first_is_never_swapped_to_month_first(self):
        # 05/03/1960 is 5 March. The old parser read it as 3 May.
        self.assertEqual(v.parse_dob("05/03/1960"), date(1960, 3, 5))

    def test_other_separators_and_iso(self):
        self.assertEqual(v.parse_dob("25-03-1958"), date(1958, 3, 25))
        self.assertEqual(v.parse_dob("1958-03-25"), date(1958, 3, 25))

    def test_impossible_date_explains_itself(self):
        with self.assertRaises(v.ValidationError) as ctx:
            v.parse_dob("31/02/1958")
        self.assertIn("DD/MM/YYYY", str(ctx.exception))

    def test_age_limit(self):
        dob = v.parse_dob("01/01/2000")
        with self.assertRaises(v.ValidationError):
            v.check_age(dob, date(2026, 10, 27), 60)
        v.check_age(v.parse_dob("27/10/1966"), date(2026, 10, 27), 60)


class NameTests(unittest.TestCase):
    def test_indian_language_name_is_stored_whole(self):
        name = "প্ৰণৱ কুমাৰ দত্ত"  # far longer than 20 bytes in UTF-8
        self.assertGreater(len(name.encode("utf-8")), 20)
        self.assertEqual(v.clean_name(name), name)

    def test_empty_name_is_rejected(self):
        with self.assertRaises(v.ValidationError):
            v.clean_name("   ")


class UploadTests(unittest.TestCase):
    MAX = 5 * 1024 * 1024

    def test_photo_of_a_few_hundred_kb_is_accepted(self):
        self.assertEqual(v.validate_upload("proof.JPG", 400 * 1024, self.MAX), ".jpg")

    def test_a_pdf_just_under_5mb_is_accepted(self):
        self.assertEqual(v.validate_upload("proof.pdf", 4 * 1024 * 1024, self.MAX), ".pdf")

    def test_errors_say_what_is_wrong(self):
        with self.assertRaises(v.ValidationError) as big:
            v.validate_upload("proof.pdf", 6 * 1024 * 1024, self.MAX)
        self.assertIn("5 MB", str(big.exception))
        with self.assertRaises(v.ValidationError) as kind:
            v.validate_upload("proof.docx", 1000, self.MAX)
        self.assertIn("PDF or JPG", str(kind.exception))
        self.assertNotIn("ERR_VAL", str(kind.exception))


class BankTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(v.validate_bank("3921227103603", "cnrb0004417"),
                         ("3921227103603", "CNRB0004417"))

    def test_invalid_ifsc_message(self):
        with self.assertRaises(v.ValidationError) as ctx:
            v.validate_bank("3921227103603", "BAD")
        self.assertIn("IFSC", str(ctx.exception))


class StepTests(unittest.TestCase):
    def test_widow_does_not_need_husband_details(self):
        cleaned, errors = v.validate_step(1, {
            "applicant_name": "Malati Deka", "dob": "22/01/1943",
            "gender": "Female", "marital_status": "Widowed"}, date(2026, 10, 27), 60)
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["marital_status"], "Widowed")


if __name__ == "__main__":
    unittest.main()
