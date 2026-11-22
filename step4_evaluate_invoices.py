"""Step 4: measure how accurate the system is.

Part A: compare extracted.csv with ground_truth.csv, field by field.
Part B: check that the validator sent exactly the problem invoices to review.
"""
import pandas as pd

FIELDS = ["supplier", "trn", "invoice_number", "invoice_date",
          "subtotal", "vat", "total", "currency"]
NUMERIC = ["subtotal", "vat", "total"]

STR_TYPES = {"trn": str, "invoice_number": str}
truth = pd.read_csv("ground_truth.csv", dtype=STR_TYPES)
found = pd.read_csv("extracted.csv", dtype=STR_TYPES)
validated = pd.read_csv("validated.csv", dtype=STR_TYPES)

df = truth.merge(found, on="file", suffixes=("_true", "_found"))


def same(field, true_value, found_value):
    """Is the extracted value equal to the true one? Both empty counts as correct."""
    true_empty, found_empty = pd.isna(true_value), pd.isna(found_value)
    if true_empty or found_empty:
        return true_empty and found_empty
    if field in NUMERIC:
        return abs(float(true_value) - float(found_value)) < 0.005
    return str(true_value).strip().lower() == str(found_value).strip().lower()


# ---------- Part A: field-by-field accuracy ----------
mistakes = []
per_field = []
for field in FIELDS:
    correct = 0
    for _, row in df.iterrows():
        if same(field, row[f"{field}_true"], row[f"{field}_found"]):
            correct += 1
        else:
            mistakes.append({"file": row["file"], "field": field,
                             "expected": row[f"{field}_true"], "got": row[f"{field}_found"]})
    per_field.append({"field": field, "correct": correct, "total": len(df),
                      "accuracy_%": round(correct / len(df) * 100, 1)})

report = pd.DataFrame(per_field)
total_cells = len(df) * len(FIELDS)
wrong_cells = len(mistakes)
bad_invoices = len({m["file"] for m in mistakes})

print("PART A: extraction accuracy (per field)\n")
print(report.to_string(index=False))
print(f"\nCells correct: {total_cells - wrong_cells}/{total_cells} "
      f"= {(total_cells - wrong_cells) / total_cells * 100:.1f}%")
print(f"Invoices with every field correct: {len(df) - bad_invoices}/{len(df)}")
if mistakes:
    print("\nMistakes:")
    for m in mistakes:
        print(f"  {m['file']}  {m['field']}: expected {m['expected']!r}, got {m['got']!r}")

# ---------- Part B: did the validator catch the planted problems? ----------
check = truth[["file", "problem"]].merge(validated[["file", "status", "reasons"]], on="file")
check["should_review"] = check["problem"].notna()
check["was_reviewed"] = check["status"] == "REVIEW"

caught = check[check["should_review"] & check["was_reviewed"]]
missed = check[check["should_review"] & ~check["was_reviewed"]]
false_alarms = check[~check["should_review"] & check["was_reviewed"]]

print("\nPART B: validation check\n")
print(f"Planted problems caught: {len(caught)}/{int(check['should_review'].sum())}")
print(f"Problems missed: {len(missed)}")
print(f"False alarms (good invoices sent to review): {len(false_alarms)}")
for _, r in missed.iterrows():
    print(f"  MISSED  {r['file']} ({r['problem']})")
for _, r in false_alarms.iterrows():
    print(f"  FALSE ALARM  {r['file']}: {r['reasons']}")

report.to_csv("accuracy_report.csv", index=False)
pd.DataFrame(mistakes).to_csv("mistakes.csv", index=False)
print("\nSaved: accuracy_report.csv, mistakes.csv")
