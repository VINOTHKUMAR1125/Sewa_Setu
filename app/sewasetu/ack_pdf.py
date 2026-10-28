# -*- coding: utf-8 -*-
"""Acknowledgment PDF. Generated on demand so the status is always current."""
import os
import logging

from fpdf import FPDF

log = logging.getLogger("sewasetu.pdf")

FONT_DIR = "/usr/share/fonts/truetype/noto"
# Base Latin font first, then scripts used by citizens (Assamese uses the Bengali script).
FONT_FILES = [("NotoSans", "NotoSans-Regular.ttf"),
              ("NotoSansBengali", "NotoSansBengali-Regular.ttf"),
              ("NotoSansDevanagari", "NotoSansDevanagari-Regular.ttf")]

LABELS = ["Application No", "Applicant Name", "Mobile", "Date of Birth",
          "Village", "Block", "Bank Account", "IFSC", "Submitted At", "Status"]


def _load_unicode_fonts(pdf):
    loaded = []
    for family, filename in FONT_FILES:
        path = os.path.join(FONT_DIR, filename)
        if os.path.exists(path):
            try:
                pdf.add_font(family, "", path, uni=True)
                loaded.append(family)
            except Exception as exc:
                log.warning("could not load font %s: %s", path, exc)
    if len(loaded) > 1:
        try:
            pdf.set_fallback_fonts(loaded[1:])
        except Exception as exc:
            log.warning("font fallback unavailable: %s", exc)
    return loaded[0] if loaded else None


def _latin1_safe(text):
    return text.encode("latin-1", "replace").decode("latin-1")


def build_acknowledgment(values):
    """values: application_no, name, mobile, dob, village, block, account, ifsc,
    submitted_at, status (in LABELS order)."""
    pdf = FPDF()
    pdf.add_page()
    family = _load_unicode_fonts(pdf)
    unicode_ok = family is not None
    body_font = family or "Helvetica"

    def text(value):
        value = str(value)
        return value if unicode_ok else _latin1_safe(value)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "GOVERNMENT OF PURVANCHAL", ln=1, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Department of Social Welfare", ln=1, align="C")
    pdf.cell(0, 8, "Old Age Pension Scheme - Acknowledgment", ln=1, align="C")
    pdf.ln(4)
    pdf.rect(10, 10, 190, 277)  # letterhead border: one call, not thousands of lines
    pdf.set_font(body_font, "", 10)
    for label, value in zip(LABELS, values):
        pdf.cell(60, 8, label, border=1)
        try:
            pdf.cell(0, 8, text(value), border=1, ln=1)
        except Exception as exc:
            log.warning("cell for %s not renderable: %s", label, exc)
            pdf.cell(0, 8, _latin1_safe(str(value)), border=1, ln=1)
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, "This is a computer generated acknowledgment. Processing SLA "
                         "as per the Purvanchal Right to Public Services Act applies.")
    return bytes(pdf.output())
