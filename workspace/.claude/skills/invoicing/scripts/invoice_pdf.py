"""Render an invoice or quote (Persian RTL or English) from a JSON spec to PDF with weasyprint.

Usage (from the workspace dir):
    python .claude/skills/invoicing/scripts/invoice_pdf.py spec.json outbox/INV-1405-001-client.pdf

The script does the arithmetic (line totals, discount, tax, balance due) and prints the
computed totals as JSON, so the numbers recorded in notes/work/invoices.md come from here,
not from mental math. Spec fields: see references/spec.md.
"""

from __future__ import annotations

import html
import json
import re
import sys

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
PERSIAN_RE = re.compile(r"[؀-ۿ]")
LATIN_RE = re.compile(r"[A-Za-z@]")
ZERO_DECIMALS = {"IRT", "IRR"}
SYMBOL = {"USD": "$", "EUR": "€"}
CURRENCY_FA = {"IRT": "تومان", "IRR": "ریال", "USD": "دلار", "EUR": "یورو", "USDT": "تتر", "AED": "درهم"}

LABELS = {
    "fa": {
        "invoice": "صورت‌حساب", "quote": "پیش‌فاکتور", "number": "شماره", "issue_date": "تاریخ صدور",
        "due_date": "سررسید پرداخت", "valid_until": "اعتبار تا", "seller": "صادرکننده", "client": "مشتری",
        "project": "پروژه", "period": "دوره کار", "row": "ردیف", "description": "شرح", "qty": "مقدار",
        "unit_price": "مبلغ واحد", "total": "مبلغ", "subtotal": "جمع", "discount": "تخفیف",
        "tax": "مالیات", "grand_total": "جمع کل", "paid": "پرداخت‌شده قبلی", "balance": "مانده قابل پرداخت",
        "terms": "شرایط پرداخت", "payment": "اطلاعات پرداخت", "notes": "توضیحات", "currency": "ارز",
    },
    "en": {
        "invoice": "Invoice", "quote": "Quote", "number": "No.", "issue_date": "Issue date",
        "due_date": "Due date", "valid_until": "Valid until", "seller": "From", "client": "Bill to",
        "project": "Project", "period": "Service period", "row": "#", "description": "Description",
        "qty": "Qty", "unit_price": "Unit price", "total": "Amount", "subtotal": "Subtotal",
        "discount": "Discount", "tax": "Tax", "grand_total": "Total", "paid": "Paid to date",
        "balance": "Balance due", "terms": "Payment terms", "payment": "Payment details", "notes": "Notes",
        "currency": "Currency",
    },
}


def money(value: float, currency: str, lang: str) -> str:
    decimals = 0 if currency in ZERO_DECIMALS else 2
    text = f"{value:,.{decimals}f}"
    if lang == "fa":
        text = text.replace(",", "٬").replace(".", "٫").translate(FA_DIGITS)
        return f"{text} {CURRENCY_FA.get(currency, currency)}"
    symbol = SYMBOL.get(currency)
    return f"{symbol}{text}" if symbol else f"{text} {currency}"


def qty_text(value: float, lang: str) -> str:
    text = f"{value:g}"
    return text.replace(".", "٫").translate(FA_DIGITS) if lang == "fa" else text


def esc(text: object, lang: str) -> str:
    """Escape; in fa use Persian digits, but keep Latin-only text (emails, names, URLs) as an LTR run."""
    raw = str(text)
    if lang != "fa":
        return html.escape(raw)
    if LATIN_RE.search(raw) and not PERSIAN_RE.search(raw):
        return f'<span class="ltr">{html.escape(raw)}</span>'
    return html.escape(raw.translate(FA_DIGITS))


def compute(spec: dict) -> dict:
    items = spec.get("items") or []
    if not items:
        raise ValueError("items is empty")
    lines = []
    for item in items:
        qty = float(item.get("qty", 1))
        price = float(item["unit_price"])
        if qty <= 0 or price < 0:
            raise ValueError(f"bad qty/price in item: {item}")
        lines.append({**item, "qty": qty, "line_total": round(qty * price, 2)})
    subtotal = round(sum(line["line_total"] for line in lines), 2)
    discount = round(float(spec.get("discount") or 0), 2)
    tax_percent = float(spec.get("tax_percent") or 0)
    tax = round((subtotal - discount) * tax_percent / 100, 2)
    total = round(subtotal - discount + tax, 2)
    paid = round(float(spec.get("paid") or 0), 2)
    if spec.get("currency", "IRT") in ZERO_DECIMALS:
        subtotal, discount, tax, total, paid = (round(x) for x in (subtotal, discount, tax, total, paid))
    return {"lines": lines, "subtotal": subtotal, "discount": discount, "tax_percent": tax_percent,
            "tax": tax, "total": total, "paid": paid, "balance_due": round(total - paid, 2)}


def render(spec: dict, calc: dict) -> str:
    lang = spec.get("lang", "fa")
    L = LABELS[lang]
    cur = spec.get("currency", "IRT")
    kind = spec.get("type", "invoice")
    m = lambda v: money(v, cur, lang)  # noqa: E731
    e = lambda v: esc(v, lang)  # noqa: E731

    def party(key: str) -> str:
        p = spec.get(key) or {}
        rows = "".join(f"<div>{e(x)}</div>" for x in p.get("lines", []))
        return f'<div class="party"><h3>{L[key]}</h3><div class="name">{e(p.get("name", ""))}</div>{rows}</div>'

    meta = [(L["number"], f'<span class="ltr">{html.escape(spec["number"])}</span>'),
            (L["issue_date"], e(spec["issue_date"]))]
    if spec.get("due_date"):
        meta.append((L["valid_until"] if kind == "quote" else L["due_date"], e(spec["due_date"])))
    for key in ("project", "period"):
        if spec.get(key):
            meta.append((L[key], e(spec[key])))
    meta_html = "".join(f"<div><b>{k}:</b> {v}</div>" for k, v in meta)

    body_rows = "".join(
        f"<tr><td>{e(i + 1)}</td><td class='desc'>{e(line['description'])}"
        + (f"<div class='sub'>{e(line['detail'])}</div>" if line.get("detail") else "")
        + f"</td><td>{qty_text(line['qty'], lang)} {e(line.get('unit', ''))}</td>"
        f"<td class='num'>{m(float(line['unit_price']))}</td><td class='num'>{m(line['line_total'])}</td></tr>"
        for i, line in enumerate(calc["lines"])
    )
    sums = [(L["subtotal"], m(calc["subtotal"]))]
    if calc["discount"]:
        sums.append((L["discount"], "− " + m(calc["discount"])))
    if calc["tax"]:
        sums.append((f"{L['tax']} ({qty_text(calc['tax_percent'], lang)}٪)" if lang == "fa"
                     else f"{L['tax']} ({calc['tax_percent']:g}%)", m(calc["tax"])))
    sums.append((L["grand_total"], m(calc["total"])))
    if calc["paid"]:
        sums += [(L["paid"], "− " + m(calc["paid"])), (L["balance"], m(calc["balance_due"]))]
    sums_html = "".join(
        f"<tr class='{'grand' if i == len(sums) - 1 else ''}'><td>{k}</td><td class='num'>{v}</td></tr>"
        for i, (k, v) in enumerate(sums)
    )

    blocks = ""
    if spec.get("equivalent"):
        blocks += f"<p class='eq'>{e(spec['equivalent'])}</p>"
    for key, field in (("terms", "payment_terms"), ("payment", "payment_details"), ("notes", "notes")):
        value = spec.get(field)
        if value:
            items = value if isinstance(value, list) else [value]
            blocks += f"<h3>{L[key]}</h3>" + "".join(f"<div>{e(x)}</div>" for x in items)

    direction, align = ("rtl", "right") if lang == "fa" else ("ltr", "left")
    font = "Vazirmatn, 'DejaVu Sans', sans-serif" if lang == "fa" else "'DejaVu Sans', Vazirmatn, sans-serif"
    return f"""<!doctype html><html dir="{direction}" lang="{lang}"><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 1.8cm 1.6cm; }}
body {{ font-family: {font}; font-size: 10pt; line-height: 1.7; color: #222; }}
.head {{ display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 2px solid #1f4e79; padding-bottom: 8px; margin-bottom: 14px; }}
.head h1 {{ margin: 0; font-size: 20pt; color: #1f4e79; }}
.meta {{ text-align: {align}; font-size: 9.5pt; }}
.parties {{ display: flex; gap: 24px; margin-bottom: 16px; }}
.party {{ flex: 1; background: #f5f7fa; padding: 8px 12px; border-radius: 4px; }}
.party .name {{ font-weight: bold; }}
h3 {{ margin: 10px 0 4px; font-size: 10.5pt; color: #1f4e79; }}
table {{ width: 100%; border-collapse: collapse; }}
.items th {{ background: #1f4e79; color: #fff; padding: 6px; font-weight: normal; text-align: {align}; }}
.items td {{ border-bottom: 1px solid #ddd; padding: 6px; vertical-align: top; }}
.desc .sub {{ color: #666; font-size: 8.5pt; }}
.num {{ white-space: nowrap; }}
.sums {{ width: 50%; margin-top: 10px; margin-{'right' if lang == 'en' else 'left'}: 0;
  margin-{align}: auto; }}
.sums td {{ padding: 4px 6px; }}
.sums .grand td {{ font-weight: bold; border-top: 2px solid #1f4e79; font-size: 11pt; }}
.eq {{ color: #555; font-size: 9pt; }}
.ltr {{ direction: ltr; unicode-bidi: embed; }}
</style></head><body>
<div class="head"><h1>{L[kind]}</h1><div class="meta">{meta_html}</div></div>
<div class="parties">{party('seller')}{party('client')}</div>
<table class="items"><thead><tr><th>{L['row']}</th><th>{L['description']}</th><th>{L['qty']}</th>
<th>{L['unit_price']}</th><th>{L['total']}</th></tr></thead><tbody>{body_rows}</tbody></table>
<table class="sums">{sums_html}</table>
{blocks}
</body></html>"""


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: invoice_pdf.py SPEC.json OUT.pdf")
    with open(sys.argv[1], encoding="utf-8") as fh:
        spec = json.load(fh)
    for field in ("number", "issue_date", "items"):
        if not spec.get(field):
            sys.exit(f"missing field: {field}")
    if spec.get("lang", "fa") not in LABELS:
        sys.exit("lang must be fa or en")
    calc = compute(spec)
    from weasyprint import HTML

    HTML(string=render(spec, calc)).write_pdf(sys.argv[2])
    out = {k: v for k, v in calc.items() if k != "lines"}
    print(json.dumps({"file": sys.argv[2], "currency": spec.get("currency", "IRT"), **out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
