# Invoicing reference

## 1. Ledger file: `notes/work/invoices.md`
Create it on first use with exactly this shape (a Markdown table is fine in a file; never in Telegram):

```markdown
# دفتر فاکتورها — شماره‌گذاری و وضعیت صورت‌حساب‌ها و پیش‌فاکتورهای صادرشده

## تنظیمات صادرکننده
- نام روی فاکتور (فارسی / English):
- تماس روی فاکتور (ایمیل، تلفن، وب‌سایت/LinkedIn):
- اطلاعات پرداخت: فقط برچسب (مثل «کارت ملت ****1234») — شماره کامل کارت/شبا اینجا ذخیره نمی‌شود
- شرایط پرداخت پیش‌فرض: تومانی «۷ روز پس از صدور» · ارزی «Net 14»
- مالیات بر ارزش افزوده: ندارد (فقط اگر کاربر گفت ثبت‌نام‌شده است)
- شماره شروع (اگر قبلاً فاکتور با شماره دیگری صادر کرده): —

## فهرست
| شماره | نوع | صدور | مشتری | پروژه | دوره/مرحله | جمع | ارز | سررسید | وضعیت | پرداخت | یادآور | فایل |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INV-1405-001 | invoice | 1405/07/13 | شرکت نمونه | #12 ربات پشتیبانی | 1405/07/01–1405/07/12 | 11,000,000 | IRT | 1405/07/20 | sent 1405/07/13 | — | #45 | outbox/INV-1405-001-nemooneh.pdf |
```

- **وضعیت‌ها:** `draft` → `sent <تاریخ>` → `paid <تاریخ>` یا `partial <مانده>` · `overdue` · `void (→ شماره جایگزین)`.
  پیش‌فاکتور: `sent` → `accepted (→ INV-…)` / `expired` / `declined`.
- **پرداخت:** تاریخ + شناسه تراکنش، مثل `1405/07/18 · tx#231` (برای پرداخت چندمرحله‌ای همه را با `+` بنویس).
- **یادآور:** شناسه `reminder_add` پیگیری، تا وقت پرداخت `reminder_cancel` شود.
- جمع و مانده را از خروجی اسکریپت بنویس (اعداد لاتین بدون واحد، برای Grep).

## 2. Spec JSON for `scripts/invoice_pdf.py`
(کامنت‌های `//` فقط توضیح‌اند؛ فایل واقعی JSON معتبر و بدون کامنت باشد. فیلدهای اختیاری خالی را حذف کن.)
```jsonc
{
  "lang": "fa",                       // fa = فارسی RTL، تاریخ شمسی · en = English، تاریخ میلادی
  "type": "invoice",                  // invoice | quote
  "number": "INV-1405-001",
  "issue_date": "1405/07/13",         // en: "Oct 5, 2026" (از date_convert)
  "due_date": "1405/07/20",           // برای quote = اعتبار تا
  "currency": "IRT",                  // IRT (بدون اعشار) | USD | EUR | ...
  "seller": {"name": "...", "lines": ["email", "phone", "LinkedIn"]},
  "client": {"name": "...", "lines": ["contact person", "city/country"]},
  "project": "عنوان پروژه",           // اختیاری
  "period": "1405/07/01 تا 1405/07/12", // اختیاری؛ برای ساعتی
  "items": [
    {"description": "توسعه agent و API", "detail": "اختیاری، خط دوم کوچک", "qty": 12.5, "unit": "ساعت", "unit_price": 800000}
  ],
  "discount": 0,                      // مبلغ، نه درصد
  "tax_percent": 0,                   // فقط اگر کاربر مشمول است
  "paid": 0,                          // پیش‌پرداخت/علی‌الحساب قبلی که از همین فاکتور کم می‌شود
  "equivalent": "اختیاری: معادل تومانی با نرخ، منبع و زمان",
  "payment_terms": "پرداخت تا ۷ روز پس از صدور",
  "payment_details": ["از کاربر در همین گفتگو؛ اگر نداد حذف شود"],
  "notes": ["با تشکر از همکاری شما"]
}
```
اجرا (از پوشه workspace؛ Bash تأیید می‌خواهد):
`python .claude/skills/invoicing/scripts/invoice_pdf.py outbox/INV-1405-001.json outbox/INV-1405-001-<client-slug>.pdf`
خروجی stdout: `{"subtotal", "discount", "tax", "total", "paid", "balance_due", ...}` — همین اعداد مرجع‌اند.
اگر spec شماره کامل کارت/شبا دارد، بعد از ساخت PDF فایل JSON را پاک کن.

## 3. Follow-up message drafts
لحن: مؤدب، کوتاه، بدون تهدید؛ همیشه شماره فاکتور، مبلغ و فایل پیوست. ارسال با خود کاربر است.

**فارسی — روز ۱ بعد از سررسید**
> سلام {نام}، وقت بخیر. خواستم یادآوری کنم فاکتور {شماره} به مبلغ {مبلغ} بابت {پروژه} تاریخ {سررسید} سررسید شده. اگر پرداخت انجام شده، ممنون می‌شوم رسیدش را بفرستید. فایل فاکتور پیوست است. ممنون 🙏

**فارسی — روز ۷+**
> سلام {نام}، پیرو پیام قبلی درباره فاکتور {شماره} ({مبلغ})، ممنون می‌شوم تاریخ تقریبی پرداخت را بفرمایید تا برنامه‌ریزی کنم. اگر سؤالی درباره فاکتور هست، در خدمتم.

**English — day 1**
> Hi {name}, a friendly reminder that invoice {number} for {amount} ({project}) was due on {date}. If it's already on its way, please ignore this — and thanks! The invoice is attached for convenience.

**English — day 7+**
> Hi {name}, following up on invoice {number} ({amount}), now {n} days past due. Could you let me know the expected payment date? Happy to answer any questions about it.

**روز ۱۴+:** پیشنهاد تماس تلفنی/جلسه کوتاه؛ اگر قرارداد اجازه می‌دهد، کاربر می‌تواند کار مرحله بعد را تا تسویه متوقف کند —
تصمیمش با خود کاربر است؛ برای مبالغ بزرگ یا اختلاف جدی، مشورت حقوقی پیشنهاد بده.
