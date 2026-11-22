"""Creates 20 FICTIONAL invoice PDFs and a ground_truth.csv with the correct values.

Why: real invoices are confidential. Fake ones let us practise safely, and because
WE know the correct answers, we can measure how accurate our extraction is later.
Three different layouts and some deliberate errors make it realistic.
"""
import csv
import os
import random
from datetime import date, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

random.seed(42)  # same fake data every time you run the script
os.makedirs("invoices", exist_ok=True)

SUPPLIERS = [
    "Gulf Office Supplies LLC", "Desert Logistics FZE", "Marina IT Solutions LLC",
    "Al Noor Printing Services", "Skyline Cleaning Co. LLC", "Falcon Catering Services",
    "Oasis Furniture Trading", "Bluewave Marketing FZ-LLC",
]
ITEMS = [
    ("A4 paper boxes", 45.00), ("Printer toner cartridge", 310.00),
    ("Office chair", 520.00), ("Monthly cleaning service", 1800.00),
    ("Laptop docking station", 650.00), ("Freight charge", 400.00),
    ("Business cards (500 pcs)", 180.00), ("Catering for 20 guests", 1500.00),
    ("Website maintenance", 2200.00), ("Whiteboard markers (box)", 35.00),
]
BUYER = "Palm Crest Properties"


def make_trn():
    """UAE tax registration numbers have 15 digits. These are random and fictional."""
    return "100" + "".join(str(random.randint(0, 9)) for _ in range(12))


def build_invoice(n):
    supplier = SUPPLIERS[n % len(SUPPLIERS)]
    items = []
    for desc, price in random.sample(ITEMS, random.randint(2, 4)):
        qty = random.randint(1, 10)
        items.append((desc, qty, price, round(qty * price, 2)))
    subtotal = round(sum(i[3] for i in items), 2)
    vat = round(subtotal * 0.05, 2)  # UAE VAT is 5 percent
    return {
        "supplier": supplier,
        "trn": make_trn(),
        "invoice_number": f"INV-2026-{1000 + n * 7}",
        "date": date(2026, 9, 1) + timedelta(days=random.randint(0, 75)),
        "items": items,
        "subtotal": subtotal,
        "vat": vat,
        "total": round(subtotal + vat, 2),
        "problem": "",
    }


def money(x, style):
    return f"{x:,.2f}" if style != "B" else f"{x:.2f}"


def draw_pdf(inv, path, layout):
    c = canvas.Canvas(path, pagesize=A4)
    y = 800

    def line(text, size=11, x=50, gap=18):
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(x, y, text)
        y -= gap

    d = inv["date"]
    if layout == "A":
        labels = dict(num="Invoice No", date="Date", trn="TRN", sub="Subtotal", vat="VAT (5%)", tot="Total")
        date_text = d.strftime("%d %b %Y")
        title = "TAX INVOICE"
    elif layout == "B":
        labels = dict(num="Invoice #", date="Issued", trn="Tax Reg. No.", sub="Net amount", vat="VAT 5%", tot="Amount due")
        date_text = d.strftime("%d/%m/%Y")
        title = "Invoice"
    else:
        labels = dict(num="Invoice Number", date="Invoice Date", trn="Tax Registration Number (TRN)",
                      sub="Sub Total", vat="Value Added Tax @ 5%", tot="Grand Total (AED)")
        date_text = d.isoformat()
        title = "TAX INVOICE"

    line(title, 20, gap=28)
    line(inv["supplier"], 14, gap=22)
    if inv["trn"]:
        line(f"{labels['trn']}: {inv['trn']}")
    line(f"{labels['num']}: {inv['invoice_number']}")
    line(f"{labels['date']}: {date_text}")
    line(f"Bill To: {BUYER}", gap=30)
    line("Description                         Qty      Unit price      Amount", 10, gap=16)
    for desc, qty, price, amount in inv["items"]:
        line(f"{desc:<32}{qty:>4}      {money(price, layout):>10}      {money(amount, layout):>10}", 10)
    y -= 12
    line(f"{labels['sub']}: AED {money(inv['subtotal'], layout)}", x=330)
    line(f"{labels['vat']}: AED {money(inv['vat'], layout)}", x=330)
    line(f"{labels['tot']}: AED {money(inv['total'], layout)}", 12, x=330, gap=30)
    line("Payment terms: 30 days from invoice date. Bank transfer only.", 9)
    c.save()


invoices = [build_invoice(n) for n in range(1, 21)]

# ----- Deliberate problems, so we can test our validation rules later -----
invoices[17]["total"] = round(invoices[17]["total"] + 250.00, 2)  # printed total is wrong
invoices[17]["problem"] = "wrong_total"
invoices[18]["trn"] = ""  # missing tax registration number
invoices[18]["problem"] = "missing_trn"
dup = dict(invoices[4])  # a second copy of invoice 5 (duplicate submission)
dup["problem"] = "duplicate"
invoices[19] = dup

with open("ground_truth.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["file", "supplier", "trn", "invoice_number", "invoice_date",
                "subtotal", "vat", "total", "currency", "problem"])
    for i, inv in enumerate(invoices, 1):
        name = f"invoice_{i:02d}.pdf"
        draw_pdf(inv, os.path.join("invoices", name), "ABC"[i % 3])
        w.writerow([name, inv["supplier"], inv["trn"], inv["invoice_number"], inv["date"].isoformat(),
                    inv["subtotal"], inv["vat"], inv["total"], "AED", inv["problem"]])

print("Created 20 invoices in the 'invoices' folder and ground_truth.csv")
