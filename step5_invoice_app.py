import io
import time

import pandas as pd
import streamlit as st
from openai import OpenAI

# Reuse the code we already built and tested in Steps 2 and 3
from step2_extract import API_KEY, BASE_URL, extract_fields, read_pdf_text
from step3_validate import check_invoice

FIELDS = ["file", "supplier", "trn", "invoice_number", "invoice_date",
          "subtotal", "vat", "total", "currency"]


def process_files(files, llm, progress=None):
    """Read -> extract (AI) -> validate (rules). Returns one table with a status for every invoice."""
    rows = []
    for i, f in enumerate(files):
        row = {"file": f.name, "error": ""}
        try:
            text = read_pdf_text(f)
            if not text.strip():
                raise ValueError("No text found (a scanned image would need OCR)")
            try:
                row.update(extract_fields(llm, text))
            except Exception:
                time.sleep(10)  # free API may say "too many requests": wait and retry once
                row.update(extract_fields(llm, text))
        except Exception as e:
            row["error"] = str(e)[:120]
        rows.append(row)
        if progress:
            progress((i + 1) / len(files))
        time.sleep(1.5)

    df = pd.DataFrame(rows).reindex(columns=FIELDS + ["error"])
    df["error"] = df["error"].fillna("")

    seen = {}  # remembers (supplier, invoice number) pairs to catch duplicates
    statuses, reasons = [], []
    for _, row in df.iterrows():
        problems = check_invoice(row, seen)
        statuses.append("REVIEW" if problems else "APPROVED")
        reasons.append("; ".join(problems))
    df["status"] = statuses
    df["reasons"] = reasons
    return df


def split_results(df):
    approved = df[df["status"] == "APPROVED"][FIELDS]
    exceptions = df[df["status"] == "REVIEW"][["file", "supplier", "invoice_number", "total", "reasons"]]
    return approved, exceptions


def to_excel(approved, exceptions):
    """Build an Excel file in memory with two sheets: Approved and Exceptions."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        approved.to_excel(writer, sheet_name="Approved", index=False)
        exceptions.to_excel(writer, sheet_name="Exceptions", index=False)
    return buffer.getvalue()


def main():
    st.set_page_config(page_title="Invoice Automation Demo", page_icon="🧾", layout="wide")
    st.title("🧾 Invoice Automation Demo")
    st.caption("Upload invoice PDFs. An AI reads them, plain-code rules check them, and anything "
               "suspicious goes to a review queue. Use fictional demo data only (free API key).")

    if not API_KEY:
        st.error("Missing LLM_API_KEY. Set it in your terminal, then restart the app.")
        st.stop()

    files = st.file_uploader("Upload invoice PDFs", type="pdf", accept_multiple_files=True)

    if st.button("Process invoices", disabled=not files):
        llm = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        bar = st.progress(0.0, text="Reading invoices...")
        st.session_state["result"] = process_files(
            files, llm, lambda p: bar.progress(p, text="Reading invoices..."))
        bar.empty()

    df = st.session_state.get("result")
    if df is None:
        st.info("Upload one or more invoice PDFs, then click 'Process invoices'.")
        return

    approved, exceptions = split_results(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Invoices processed", len(df))
    c2.metric("Approved automatically", len(approved))
    c3.metric("Sent to human review", len(exceptions))

    st.subheader("✅ Approved")
    st.dataframe(approved, hide_index=True)

    st.subheader("⚠️ Review queue (needs a person)")
    if exceptions.empty:
        st.success("No exceptions. Every invoice passed all checks.")
    else:
        st.dataframe(exceptions, hide_index=True)

    st.download_button(
        "Download Excel (Approved + Exceptions)",
        data=to_excel(approved, exceptions),
        file_name="processed_invoices.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
