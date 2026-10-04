---
name: office-docs
description: "Create or edit Word (.docx), Excel (.xlsx), PowerPoint (.pptx) and PDF files — including correct Persian/RTL text — and charts (ساخت فایل ورد، اکسل، پاورپوینت، PDF و نمودار). Use whenever the user wants a document, report, invoice, CV, spreadsheet, slide deck or chart as a file, or sends such a file to modify."
---

# Office Docs — ساخت فایل با پشتیبانی فارسی

فایل‌ها را با Python در `outbox/` بساز و با `send_file` بفرست. فایل‌های ورودی کاربر در `inbox/` هستند.
اجرای Python از طریق Bash است و تأیید کاربر را لازم دارد؛ در پیام تأیید روشن باشد چه فایلی ساخته می‌شود.
کتابخانه‌های نصب‌شده: `python-docx`, `openpyxl`, `python-pptx`, `weasyprint`, `matplotlib`, `arabic-reshaper`, `python-bidi`, `pypdf`. فونت فارسی: **Vazirmatn**.

## قواعد کلی
- قبل از ساخت، ساختار (بخش‌ها/ستون‌ها/اسلایدها) را در یک خط به کاربر بگو، مگر اینکه درخواست کاملاً روشن باشد.
- نام فایل معنادار: `outbox/2026-10-04-gozaresh-mali.xlsx`.
- اعداد مالی با جداکننده هزارگان؛ تاریخ‌ها شمسی (از ابزار `date_convert`).
- بعد از ساخت، فایل را دوباره باز کن و بررسی کن (تعداد صفحات/شیت‌ها، نبودِ خطا) و بعد بفرست.

## Word (.docx) — python-docx
فارسی نیاز به RTL در سطح پاراگراف و run دارد:
```python
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt

def rtl(paragraph, font="Vazirmatn", size=12):
    pPr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi"); bidi.set(qn("w:val"), "1"); pPr.append(bidi)
    paragraph.alignment = 2  # right
    for run in paragraph.runs:
        run.font.name = font; run.font.size = Pt(size)
        rPr = run._r.get_or_add_rPr()
        rtl_el = OxmlElement("w:rtl"); rtl_el.set(qn("w:val"), "1"); rPr.append(rtl_el)
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:  # lxml elements are falsy when childless, so no `or` here
            rFonts = OxmlElement("w:rFonts"); rPr.append(rFonts)
        rFonts.set(qn("w:cs"), font); rFonts.set(qn("w:ascii"), font); rFonts.set(qn("w:hAnsi"), font)
        cs = OxmlElement("w:szCs"); cs.set(qn("w:val"), str(size * 2)); rPr.append(cs)

doc = Document()
p = doc.add_paragraph("گزارش ماهانه"); rtl(p, size=16)
doc.save("outbox/report.docx")
```
برای جدول‌های فارسی، `tblPr` را هم با `w:bidiVisual` راست‌چین کن. برای ویرایش فایل موجود، متن را run به run عوض کن تا قالب حفظ شود.

## Excel (.xlsx) — openpyxl
- `ws.sheet_view.rightToLeft = True` برای شیت‌های فارسی.
- فرمول‌ها را واقعی بنویس (`=SUM(B2:B30)`) نه عدد محاسبه‌شده، تا کاربر بتواند ویرایش کند.
- قالب عدد: `'#,##0'`؛ عرض ستون‌ها را تنظیم کن؛ سطر عنوان bold و freeze (`ws.freeze_panes = "A2"`).
- برای خروجی داده‌های مالی از `finance_list_transactions` بگیر.

## PowerPoint (.pptx) — python-pptx
- هر اسلاید یک پیام اصلی؛ حداکثر ۵ bullet کوتاه؛ عنوان‌ها به‌صورت جمله نتیجه.
- برای متن فارسی: `paragraph.alignment = PP_ALIGN.RIGHT` و فونت Vazirmatn؛ در XML پاراگراف `rtl="1"` را روی `a:pPr` ست کن.
- نمودارها را با matplotlib به PNG بساز و درج کن.

## PDF — weasyprint (HTML → PDF)
بهترین راه برای PDF فارسی تمیز: HTML بنویس و تبدیل کن.
```python
from weasyprint import HTML
html = """<html dir="rtl" lang="fa"><head><meta charset="utf-8"><style>
@page { size: A4; margin: 2cm; }
body { font-family: Vazirmatn, sans-serif; font-size: 11pt; line-height: 1.8; }
table { width: 100%; border-collapse: collapse; } td, th { border: 1px solid #ccc; padding: 6px; }
code, .ltr { direction: ltr; unicode-bidi: embed; font-family: monospace; }
</style></head><body><h1>عنوان</h1><p>متن…</p></body></html>"""
HTML(string=html).write_pdf("outbox/report.pdf")
```
برای خواندن/ادغام/جداکردن PDF از `pypdf` استفاده کن؛ برای خواندن محتوا ابزار Read کافی است.

## نمودار — matplotlib با فارسی
```python
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import arabic_reshaper
from bidi.algorithm import get_display
fa = lambda s: get_display(arabic_reshaper.reshape(s))
plt.rcParams["font.family"] = "Vazirmatn"
fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
ax.barh([fa(c) for c in cats], values)
ax.set_title(fa("هزینه‌ها به تفکیک دسته"))
fig.tight_layout(); fig.savefig("outbox/chart.png")
```
نمودار ساده و خوانا: یک پیام، رنگ محدود، برچسب مستقیم روی داده به‌جای legend شلوغ، بدون سه‌بعدی.
