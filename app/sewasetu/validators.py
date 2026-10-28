# -*- coding: utf-8 -*-
"""Input validation. Every error message tells the citizen what to fix."""
import re
import unicodedata
from datetime import date, datetime

BLOCKS = ["Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"]
GENDERS = ("Male", "Female", "Other")
MARITAL = ("Married", "Unmarried", "Widowed")
ALLOWED_UPLOADS = (".pdf", ".jpg", ".jpeg")
NAME_MAX = 100


class ValidationError(ValueError):
    pass


def _has_control_chars(text):
    return any(unicodedata.category(c) == "Cc" for c in text)


def normalize_mobile(raw):
    digits = re.sub(r"[\s\-]", "", raw or "")
    if digits.startswith("+91"):
        digits = digits[3:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not digits.isdigit() or len(digits) != 10:
        raise ValidationError("Please enter a 10-digit mobile number "
                              "(digits only, for example 9876543210).")
    if digits[0] not in "6789":
        raise ValidationError("A mobile number must start with 6, 7, 8 or 9. "
                              "Please check the number.")
    return digits


def clean_name(raw, label="Name", required=True):
    # Trimmed only: names are stored exactly as typed, in any script.
    value = (raw or "").strip()
    if not value:
        if required:
            raise ValidationError("Please enter the %s." % label)
        return ""
    if len(value) > NAME_MAX:
        raise ValidationError("%s is too long (maximum %d characters)."
                              % (label, NAME_MAX))
    if _has_control_chars(value):
        raise ValidationError("%s contains characters that are not allowed." % label)
    return value


def parse_dob(raw):
    """Day-first only. The old '%m/%d/%Y' first guess silently swapped day and month."""
    text = (raw or "").strip()
    example = "Please enter the date of birth as DD/MM/YYYY, for example 25/03/1958."
    if not text:
        raise ValidationError(example)
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", text)
    if m:
        day, month, year = (int(g) for g in m.groups())
    else:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
        if not m:
            raise ValidationError(example)
        year, month, day = (int(g) for g in m.groups())
    try:
        dob = date(year, month, day)
    except ValueError:
        raise ValidationError("That date does not exist (%s). " % text + example)
    if dob.year < 1900 or dob > date.today():
        raise ValidationError("The date of birth looks wrong. " + example)
    return dob


def age_on(dob, today):
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def check_age(dob, today, min_age):
    if age_on(dob, today) < min_age:
        raise ValidationError(
            "Only residents who have completed %d years of age are eligible. "
            "The date of birth entered makes the applicant younger than that." % min_age)


def choice(raw, options, label, required=False):
    value = (raw or "").strip()
    if not value:
        if required:
            raise ValidationError("Please select %s." % label)
        return ""
    if value not in options:
        raise ValidationError("Please select %s from the list." % label)
    return value


def validate_bank(account, ifsc):
    account = re.sub(r"\s", "", account or "")
    ifsc = (ifsc or "").strip().upper()
    if not account:
        raise ValidationError("Please enter the bank account number.")
    if not account.isdigit() or not 9 <= len(account) <= 18:
        raise ValidationError("The bank account number should be 9 to 18 digits "
                              "(numbers only, no spaces).")
    if not ifsc:
        raise ValidationError("Please enter the IFSC code of the bank branch.")
    if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
        raise ValidationError("The IFSC code should be 11 characters: 4 letters, "
                              "the digit 0, then 6 letters or digits "
                              "(for example SBIN0001234).")
    return account, ifsc


def validate_upload(filename, size, max_bytes):
    name = (filename or "").strip()
    if not name:
        raise ValidationError("Please choose a file to upload.")
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_UPLOADS:
        raise ValidationError("Only PDF or JPG files can be uploaded. The file "
                              "you chose is not one of these.")
    if size == 0:
        raise ValidationError("The file you chose is empty. Please choose the "
                              "scanned document again.")
    if size > max_bytes:
        raise ValidationError("The file is %.1f MB. The maximum allowed size is "
                              "%d MB. Please upload a smaller file."
                              % (size / 1048576.0, max_bytes // 1048576))
    return ext


STEP_FIELDS = {
    1: ("applicant_name", "dob", "gender", "marital_status",
        "husband_name", "husband_employer"),
    2: ("village", "block"),
    3: ("bank_account", "ifsc"),
}


def validate_step(step, data, today, min_age):
    """Validate one form step. Returns (cleaned, errors)."""
    cleaned, errors = {}, []

    def run(fn, key, *args, **kwargs):
        try:
            cleaned[key] = fn(*args, **kwargs)
        except ValidationError as exc:
            errors.append(str(exc))

    if step == 1:
        run(clean_name, "applicant_name", data.get("applicant_name"), "applicant's name")
        try:
            dob = parse_dob(data.get("dob"))
            check_age(dob, today, min_age)
            cleaned["dob"] = dob
        except ValidationError as exc:
            errors.append(str(exc))
        run(choice, "gender", data.get("gender"), GENDERS, "a gender")
        run(choice, "marital_status", data.get("marital_status"), MARITAL,
            "a marital status")
        run(clean_name, "husband_name", data.get("husband_name"), "husband's name",
            required=False)
        run(clean_name, "husband_employer", data.get("husband_employer"),
            "husband's employer", required=False)
    elif step == 2:
        run(clean_name, "village", data.get("village"), "village or town")
        run(choice, "block", data.get("block"), BLOCKS, "a block", required=True)
    elif step == 3:
        try:
            cleaned["bank_account"], cleaned["ifsc"] = validate_bank(
                data.get("bank_account"), data.get("ifsc"))
        except ValidationError as exc:
            errors.append(str(exc))
    return cleaned, errors
