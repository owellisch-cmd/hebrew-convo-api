"""Best-effort parsers that turn an uploaded expense export (CSV or PDF) into
a list of categorized line items. These are heuristics over free-form data,
not a certified claims parser — always show the user what was extracted so
they can correct it.
"""

from __future__ import annotations

import csv
import io
import re

from pypdf import PdfReader

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "prescription": ["rx", "pharmacy", "prescription", "drug", "refill"],
    "er": ["emergency", " er ", "er visit", "urgent care"],
    "specialist": [
        "specialist",
        "dermatology",
        "cardiology",
        "orthopedic",
        "psychiatry",
        "therapy",
        "referral",
    ],
    "hospital": ["hospital", "inpatient", "surgery", "admission", "operating room"],
    "primary_care": [
        "primary care",
        "office visit",
        "physician",
        "pcp",
        "checkup",
        "wellness",
        "annual exam",
    ],
}

AMOUNT_COLUMN_CANDIDATES = ["amount", "cost", "charge", "total", "paid", "patient responsibility"]
DESCRIPTION_COLUMN_CANDIDATES = ["description", "category", "service", "provider", "type", "claim type"]

CURRENCY_RE = re.compile(r"\$?\s?(-?\d[\d,]*\.\d{2})")


def categorize(text: str) -> str:
    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return category
    return "other"


def _parse_amount(raw: str) -> float | None:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return abs(float(cleaned))
    except (TypeError, ValueError):
        return None


def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []

    fieldnames_lower = {f.lower().strip(): f for f in reader.fieldnames}

    amount_col = next(
        (fieldnames_lower[c] for c in AMOUNT_COLUMN_CANDIDATES if c in fieldnames_lower),
        None,
    )
    description_col = next(
        (fieldnames_lower[c] for c in DESCRIPTION_COLUMN_CANDIDATES if c in fieldnames_lower),
        None,
    )

    items: list[dict] = []
    for row in reader:
        amount = None
        if amount_col:
            amount = _parse_amount(row.get(amount_col, ""))
        if amount is None:
            # Fall back: scan every cell for something that looks like a dollar amount
            for value in row.values():
                amount = _parse_amount(value or "")
                if amount is not None:
                    break
        if amount is None or amount == 0:
            continue

        description = row.get(description_col, "") if description_col else ""
        if not description:
            description = " ".join(str(v) for v in row.values() if v)

        items.append(
            {
                "amount": amount,
                "description": description[:200],
                "category": categorize(description),
                "incurred_on": row.get("date") or row.get("Date"),
            }
        )
    return items


def parse_pdf(content: bytes) -> list[dict]:
    reader = PdfReader(io.BytesIO(content))
    items: list[dict] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            match = CURRENCY_RE.search(line)
            if not match:
                continue
            amount = _parse_amount(match.group(1))
            if amount is None or amount == 0:
                continue
            items.append(
                {
                    "amount": amount,
                    "description": line.strip()[:200],
                    "category": categorize(line),
                    "incurred_on": None,
                }
            )
    return items


def parse_expense_file(filename: str, content: bytes) -> list[dict]:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return parse_csv(content)
    if lower.endswith(".pdf"):
        return parse_pdf(content)
    raise ValueError("Unsupported file type — please upload a .csv or .pdf")
