---
name: office-docs
description: "Create, read or edit Word (.docx), Excel (.xlsx), PowerPoint (.pptx) and PDF files and charts with correct Persian/RTL text (ساخت فایل ورد، اکسل، پاورپوینت، PDF و نمودار فارسی): reports, CVs, timesheets, spreadsheets of transactions, slide decks, charts. Use whenever the user wants something «به‌صورت فایل», «خروجی PDF/اکسل بده», «رزومه», «نمودار بکش», or sends such a file in inbox/ to read, fix or convert. For client invoices/quotes use the invoicing skill (it calls this one for the file)."
---

# Office Docs — ساخت فایل با پشتیبانی فارسی

هدف: فایل درست، خوانا و راست‌چین در `outbox/` که با `send_file` (با `caption` کوتاه) فرستاده می‌شود. فایل‌های کاربر در `inbox/` فقط‌خواندنی‌اند.
کتابخانه‌های نصب‌شده: `python-docx`, `openpyxl`, `python-pptx`, `weasyprint`, `matplotlib`, `arabic-reshaper`, `python-bidi`, `pypdf`.
فونت فارسی سیستم: **Vazirmatn**. (reportlab و LibreOffice نصب نیستند؛ PDF فقط با weasyprint.)

## روند کار
1. **ساختار:** بخش‌ها/ستون‌ها/اسلایدها را در یک خط بگو، مگر اینکه درخواست کاملاً روشن باشد. فرمت را کاربر نگفته؟
   برای خواندن/چاپ/ارسال → PDF؛ برای ویرایش اعداد → xlsx؛ برای ویرایش متن → docx.
2. **داده:** از منبع واقعی بگیر — تراکنش‌ها `finance_list_transactions` (فیلتر start/end/category/currency/query) یا `finance_summary`؛
   ساعت کار `time_report`؛ مشتری/پروژه `client_list`/`project_list`؛ تاریخ شمسی با `date_convert`. عدد ساختگی نگذار.
3. **اسکریپت:** کد را با Write در `outbox/_scripts/<name>.py` بنویس و با یک فرمان کوتاه `python3 outbox/_scripts/<name>.py` اجرا کن
   (Bash تأیید کاربر می‌خواهد؛ فرمان کوتاه پیام تأیید را خوانا می‌کند). ساخت **و** بررسی را در همان اسکریپت بگذار تا یک تأیید کافی باشد.
4. **نام فایل:** معنادار و لاتین: `outbox/2026-10-05-gozaresh-mali.xlsx`. هرگز فایل inbox را بازنویسی نکن؛ نسخه ویرایش‌شده را در outbox بساز.
5. **بررسی** (بخش «چک‌لیست») و بعد `send_file`.

## Word (.docx) — python-docx
فارسی نیاز به RTL در سطح پاراگراف و run دارد (عناصر به ترتیب schema درج می‌شوند تا Word خطا ندهد):
```python
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt

def rtl(paragraph, font="Vazirmatn", size=12):
    """راست‌چین کردن پاراگراف فارسی — بعد از افزودن همه runها صدا بزن."""
    pPr = paragraph._p.get_or_add_pPr()
    if pPr.find(qn("w:bidi")) is None:
        bidi = OxmlElement("w:bidi"); bidi.set(qn("w:val"), "1"); pPr.append(bidi)
    paragraph.alignment = 2  # right
    for run in paragraph.runs:
        run.font.name = font; run.font.size = Pt(size)
        run.font.rtl = True  # w:rtl
        rPr = run._r.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:  # lxml elements are falsy when childless, so no `or` here
            rFonts = OxmlElement("w:rFonts"); rPr.insert(0, rFonts)
        rFonts.set(qn("w:cs"), font); rFonts.set(qn("w:ascii"), font); rFonts.set(qn("w:hAnsi"), font)
        if rPr.find(qn("w:szCs")) is None:  # complex-script size, right after w:sz
            cs = OxmlElement("w:szCs"); cs.set(qn("w:val"), str(size * 2)); rPr.find(qn("w:sz")).addnext(cs)

def rtl_table(table):
    """ستون اول جدول در سمت راست؛ بعد rtl() را روی پاراگراف‌های هر خانه هم بزن."""
    tblPr = table._tbl.tblPr
    el = OxmlElement("w:bidiVisual"); el.set(qn("w:val"), "1")
    style = tblPr.find(qn("w:tblStyle"))
    style.addnext(el) if style is not None else tblPr.insert(0, el)

doc = Document()
p = doc.add_paragraph("گزارش ماهانه"); rtl(p, size=16)
t = doc.add_table(rows=2, cols=2); t.style = "Table Grid"; rtl_table(t)
for cell in t._cells:
    cell.text = "خانه"
    for cp in cell.paragraphs: rtl(cp, size=11)
doc.save("outbox/report.docx")
```
- ویرایش فایل موجود: متن را run به run عوض کن تا قالب حفظ شود؛ خواندن متن: `[p.text for p in Document(path).paragraphs]` + جدول‌ها.
- فایل برای کس دیگری است و شاید Vazirmatn نداشته باشد → `font="Tahoma"` (روی ویندوز هست) یا PDF بفرست.

## Excel (.xlsx) — openpyxl
```python
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
wb = Workbook(); ws = wb.active; ws.title = "هزینه‌ها"
ws.sheet_view.rightToLeft = True
ws.append(["دسته", "مبلغ (تومان)"])
# ... ws.append([category, amount]) برای هر سطر — عدد را عدد بگذار، نه رشته
ws["A10"], ws["B10"] = "جمع", "=SUM(B2:B9)"           # فرمول واقعی، نه عدد محاسبه‌شده
for c in ws[1]: c.font = Font(name="Vazirmatn", bold=True)
for row in ws.iter_rows(min_row=2):
    row[0].alignment = Alignment(horizontal="right", readingOrder=2); row[1].number_format = "#,##0"
ws.freeze_panes = "A2"; ws.column_dimensions["A"].width = 18; ws.column_dimensions["B"].width = 16
wb.save("outbox/expenses.xlsx")
```
- چند ارز → ستون ارز جدا و جمع جدا برای هر ارز؛ تومان و دلار را بدون نرخ صریح جمع نزن.
- خواندن فایل کاربر: `load_workbook(path, data_only=True)` برای مقدار نهایی فرمول‌ها.

## PowerPoint (.pptx) — python-pptx
- هر اسلاید یک پیام؛ عنوان = جمله نتیجه («درآمد ۲۰٪ بیشتر شد»)؛ حداکثر ۵ bullet کوتاه؛ نمودار به‌صورت PNG از matplotlib.
```python
from pptx.util import Pt
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

def rtl_frame(text_frame, font="Vazirmatn", size=20):
    for p in text_frame.paragraphs:
        p.alignment = PP_ALIGN.RIGHT
        p._p.get_or_add_pPr().set("rtl", "1")
        for r in p.runs:
            r.font.name = font; r.font.size = Pt(size)
            rPr = r._r.get_or_add_rPr()
            if rPr.find(qn("a:cs")) is None:  # complex-script typeface for Persian glyphs
                cs = rPr.makeelement(qn("a:cs"), {"typeface": font}); rPr.find(qn("a:latin")).addnext(cs)
```
بعد از گذاشتن متن هر shape، `rtl_frame(shape.text_frame)` را صدا بزن.

## PDF — weasyprint (HTML → PDF)
بهترین راه برای PDF فارسی تمیز (فاکتور، گزارش، رزومه): HTML بنویس و تبدیل کن. Pango شکل‌دهی فارسی را خودش انجام می‌دهد.
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
- سند انگلیسی (فاکتور مشتری خارجی، CV انگلیسی) → `dir="ltr" lang="en"`؛ کلمه انگلیسی وسط متن فارسی → `<span dir="ltr">`.
- خواندن/ادغام/جداکردن PDF با `pypdf`؛ برای فهم محتوا ابزار Read کافی است.

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
- هشدار `findfont: Font family 'Vazirmatn' not found` دیدی → قبل از رسم:
  `[font_manager.fontManager.addfont(f) for f in font_manager.findSystemFonts() if "Vazirmatn" in f]`
- نمودار ساده: یک پیام، رنگ محدود، برچسب مستقیم روی داده به‌جای legend شلوغ، بدون سه‌بعدی؛ محور مبلغ با جداکننده هزارگان.

## چک‌لیست قبل از ارسال
- [ ] `arabic_reshaper` + `get_display` **فقط** برای matplotlib (و تصویر)؛ در docx/xlsx/pptx/HTML متن خام فارسی بده — شکل‌دهی دوباره متن را برعکس می‌کند.
- [ ] فایل را دوباره باز کردی: docx/pptx با همان کتابخانه (تعداد پاراگراف/جدول/اسلاید)، xlsx با `load_workbook` (شیت‌ها و فرمول‌ها)، PDF با `pypdf` (تعداد صفحه).
- [ ] PDF و PNG را با Read دیدی: حروف فارسی متصل، ترتیب راست‌به‌چپ، اعداد و جدول سالم.
- [ ] اعداد از داده واقعی، با جداکننده هزارگان، ارز مشخص؛ تاریخ‌ها شمسی؛ هیچ اطلاعات حساس اضافه (شماره کارت کامل) در فایل نیست.
- [ ] `send_file` با caption یک‌خطی؛ در پیام فقط خلاصه و نکته مهم، نه تکرار محتوای فایل.
