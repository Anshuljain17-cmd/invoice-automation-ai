"""Step 3: check every extracted invoice against business rules (plain code, no AI).

Approved invoices go to clean_invoices.csv.
Anything suspicious goes to exceptions.csv with the reasons, for a human to review.
"""
import re
from datetime import date, datetime

import pandas as pd

REQUIRED = ["supplier", "trn", "invoice_number", "invoice_date",
            "subtotal", "vat", "total", "currency"]
VAT_RATE = 0.05       # UAE VAT is 5 percent
TOLERANCE = 0.011     # allow rounding differences of about one fils
EXPECTED_CURRENCY = "AED"


def check_invoice(row, seen):
    """Return a list of problems. An empty list means the invoice looks fine."""
    reasons = []

    # Rule 0: could we even read it?
    if row["error"]:
        return [f"could not be read ({row['error']})"]

    # Rule 1: every required field must be present
    missing = [f for f in REQUIRED if pd.isna(row[f])]
    if missing:
        reasons.append("missing: " + ", ".join(missing))

    # Rule 2: the tax registration number must be exactly 15 digits
    if not pd.isna(row["trn"]) and not re.fullmatch(r"\d{15}", str(row["trn"])):
        reasons.append(f"TRN is not 15 digits ({row['trn']})")

    # Rule 3: the date must be a real date and not in the future
    if not pd.isna(row["invoice_date"]):
        try:
            d = datetime.strptime(str(row["invoice_date"]), "%Y-%m-%d").date()
            if d > date.today():
                reasons.append(f"invoice date is in the future ({d})")
        except ValueError:
            reasons.append(f"invalid date ({row['invoice_date']})")

    # Rule 4: the maths must add up (only if the numbers exist)
    sub, vat, total = row["subtotal"], row["vat"], row["total"]
    if not pd.isna(sub) and not pd.isna(vat):
        expected_vat = round(sub * VAT_RATE, 2)
        if abs(vat - expected_vat) > TOLERANCE:
            reasons.append(f"VAT {vat:,.2f} is not 5% of subtotal (expected {expected_vat:,.2f})")
    if not pd.isna(sub) and not pd.isna(vat) and not pd.isna(total):
        expected_total = round(sub + vat, 2)
        if abs(total - expected_total) > TOLERANCE:
            reasons.append(f"total {total:,.2f} does not equal subtotal + VAT (expected {expected_total:,.2f})")

    # Rule 5: the currency should be AED
    if not pd.isna(row["currency"]) and str(row["currency"]).upper() != EXPECTED_CURRENCY:
        reasons.append(f"currency is {row['currency']}, not {EXPECTED_CURRENCY}")

    # Rule 6: the same supplier must not send the same invoice number twice
    if not pd.isna(row["supplier"]) and not pd.isna(row["invoice_number"]):
        key = (str(row["supplier"]).strip().lower(), str(row["invoice_number"]).strip().lower())
        if key in seen:
            reasons.append(f"duplicate of {seen[key]}")
        else:
            seen[key] = row["file"]

    return reasons


if __name__ == "__main__":
    df = pd.read_csv("extracted.csv", dtype={"trn": str, "invoice_number": str})
    df["error"] = df["error"].fillna("")

    seen = {}
    statuses, all_reasons = [], []
    for _, row in df.iterrows():
        reasons = check_invoice(row, seen)
        statuses.append("REVIEW" if reasons else "APPROVED")
        all_reasons.append("; ".join(reasons))
    df["status"] = statuses
    df["reasons"] = all_reasons

    df.to_csv("validated.csv", index=False)
    df[df["status"] == "APPROVED"].drop(columns=["error", "reasons"]).to_csv("clean_invoices.csv", index=False)
    exceptions = df[df["status"] == "REVIEW"][["file", "supplier", "invoice_number", "total", "reasons"]]
    exceptions.to_csv("exceptions.csv", index=False)

    print(f"Approved: {(df['status'] == 'APPROVED').sum()}   Sent to review: {len(exceptions)}\n")
    for _, r in exceptions.iterrows():
        print(f"REVIEW  {r['file']}: {r['reasons']}")
    print("\nSaved: validated.csv, clean_invoices.csv, exceptions.csv")
