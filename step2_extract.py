import json
import os
import re
import time

import pandas as pd
from openai import OpenAI
from pypdf import PdfReader

# ---------- SETTINGS (same idea as Project 1: provider can be swapped) ----------
API_KEY = os.environ.get("LLM_API_KEY")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")

PROMPT = """You extract data from invoice text. Return ONLY a JSON object with exactly these keys:
supplier, trn, invoice_number, invoice_date, subtotal, vat, total, currency

Rules:
- supplier: the company that ISSUED the invoice. Do not use the "Bill To" company.
- trn: the supplier's tax registration number (15 digits). If the invoice has none, use null. Never invent one.
- invoice_date: format YYYY-MM-DD. The text may show 12 Oct 2026, 12/10/2026 (day/month/year) or 2026-10-12.
- subtotal, vat, total: plain numbers without commas or currency symbols, copied EXACTLY as printed.
  Do NOT calculate, fix or double-check any number, even if it looks wrong.
- currency: 3-letter code such as AED.
- If any other field is missing, use null.
Return JSON only, with no explanation."""


def read_pdf_text(path):
    """Step 1 of the pipeline: get the text out of a PDF (works for PDFs that contain real text)."""
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_json(reply):
    """AI replies sometimes wrap JSON in extra words or ``` marks. Cut out just the JSON part."""
    reply = re.sub(r"```(?:json)?", "", reply).strip()
    start, end = reply.find("{"), reply.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found in the AI reply")
    return json.loads(reply[start:end + 1])


def to_number(value):
    """Turn '1,234.50' or 'AED 1234.5' or 1234.5 into a float. Missing or unreadable -> None."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("AED", "").strip())
    except ValueError:
        return None


def to_text(value):
    """Missing values should be None, not the words 'null' or 'None'."""
    if value is None or str(value).strip().lower() in ("", "null", "none", "n/a"):
        return None
    return str(value).strip()


def extract_fields(llm, text):
    """Step 2 of the pipeline: ask the AI for the fields, then clean the reply with plain code."""
    reply = llm.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"INVOICE TEXT:\n{text}"},
        ],
    ).choices[0].message.content
    data = parse_json(reply)
    return {
        "supplier": to_text(data.get("supplier")),
        "trn": to_text(data.get("trn")),
        "invoice_number": to_text(data.get("invoice_number")),
        "invoice_date": to_text(data.get("invoice_date")),
        "subtotal": to_number(data.get("subtotal")),
        "vat": to_number(data.get("vat")),
        "total": to_number(data.get("total")),
        "currency": to_text(data.get("currency")),
    }


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("Missing LLM_API_KEY. Set it in your terminal first.")
    llm = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    files = sorted(f for f in os.listdir("invoices") if f.lower().endswith(".pdf"))
    rows = []
    for name in files:
        row = {"file": name, "error": ""}
        try:
            text = read_pdf_text(os.path.join("invoices", name))
            if not text.strip():
                raise ValueError("No text found (a scanned image would need OCR)")
            try:
                row.update(extract_fields(llm, text))
            except Exception:
                time.sleep(15)  # free API may say "too many requests": wait and try once more
                row.update(extract_fields(llm, text))
            print(f"OK    {name}  {row['invoice_number']}  total={row['total']}")
        except Exception as e:
            row["error"] = str(e)[:120]
            print(f"FAIL  {name}  {row['error']}")
        rows.append(row)
        time.sleep(2.5)  # be gentle with free-tier limits

    df = pd.DataFrame(rows)
    df.to_csv("extracted.csv", index=False)
    failed = (df["error"] != "").sum()
    print(f"\nDone. {len(df) - failed} extracted, {failed} failed. Saved to extracted.csv")
