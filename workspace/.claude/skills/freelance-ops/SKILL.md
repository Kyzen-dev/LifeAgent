---
name: freelance-ops
description: "Run the user's freelance business day to day (مدیریت کار فریلنس): clients, projects and pipeline, time tracking («شروع کار روی پروژه X»، «تموم کردم»، «دیروز ۳ ساعت روی X کار کردم»), hours and effective hourly rate, deadlines and follow-ups, scope creep, receivables, rate reviews against inflation, and irregular-income cash flow. Use whenever the user mentions a client, a project, hours, a timer, a deadline, their rate, or getting paid for a project. Invoices and quotes → invoicing; winning new clients → client-acquisition or upwork-growth."
---

# Freelance Ops

زمینه کاربر (تخصص، نرخ فعلی و هدف، ساعت کاری، نوع مشتری‌ها و ارزشان، هدف درآمدی) را از بخش «کار» در
`memory/profile.md` بخوان؛ اگر نرخ هدف نیست، یک بار بپرس و ثبت کن.

## زبان طبیعی → ابزار
| کاربر می‌گوید | کار تو |
|---|---|
| «شروع کار روی ربات فروشگاه» | `timer_start` (project = بخشی از عنوان). پیدا نشد → ابزار پروژه‌های باز را برمی‌گرداند؛ با options بپرس |
| «تموم کردم، API پرداخت رو وصل کردم» | `timer_stop` با note |
| «دیروز ۳ ساعت روی X کار کردم» | `time_log` (minutes=180، date) |
| «الان روی چی‌ام؟» / «امروز چقدر کار کردم؟» | `timer_status` |
| «این هفته/ماه چقدر کار کردم؟» | `time_report` (start/end؛ پیش‌فرض از شنبه) |
| «مشتری جدید: Y، پروژه چت‌بات، ساعتی ۸۰۰ تومن» | `client_upsert` (currency، default_rate، source) + `project_upsert` (client، billing، rate، currency، estimate_hours، deadline) |
| «پروپوزال رو برای Z فرستادم» | `project_upsert` status=proposal، next_action «follow-up»، next_action_date سه روز بعد |
| «قبول کرد، شروع می‌کنیم» | `project_upsert` status=active؛ پیش‌پرداخت طبق توافق → skill `invoicing` |
| «براش فاکتور بزن» / «پیش‌فاکتور بده» | skill `invoicing` |
| «پول پروژه X رو گرفتم» | پایین: «دریافت پول» |

- مبلغ محاوره‌ای: «ساعتی ۸۰۰ تومن» یعنی ۸۰۰٬۰۰۰ تومان؛ اگر بزرگی عدد مبهم است، بپرس.
- **تایمر جامانده:** اگر تایمر بیش از ۴ ساعت روشن است، **قبل از** `timer_stop` بپرس واقعاً این‌قدر کار کرده؟
  ابزاری برای ویرایش زمان ثبت‌شده نیست؛ اگر جا مانده بود، در note زمان واقعی را بنویس («تایمر جا ماند؛ واقعی ~۲ ساعت»)
  و در فاکتور و گزارش همان عدد واقعی را حساب کن.

## دریافت پول
1. اگر برای این پروژه فاکتور باز در `notes/work/invoices.md` هست → طبق skill `invoicing` (بخش ثبت پرداخت) پیش برو.
2. وگرنه اول تکراری نبودن را چک کن (`finance_list_transactions` kind=income، چند روز اخیر، query = نام مشتری) —
   شاید از پیامک بانکی ثبت شده باشد؛ اگر بود فقط `finance_update_transaction` (category، merchant، note).
3. ثبت: `finance_add_transaction` kind=income، category=«پروژه»، merchant = نام مشتری، amount = مبلغ واقعاً رسیده،
   currency = ارز دریافتی (ریال → IRR)، note = عنوان پروژه، source=manual (یا bank_sms/receipt اگر از آن آمده).
4. پروژه تمام و تسویه شد → `project_upsert` status=done؛ اگر مشتری پروژه باز دیگری ندارد، `client_upsert` status=past.

## سلامت کسب‌وکار (در گزارش‌ها و وقتی پرسید)
- **نرخ مؤثر ساعتی:** fixed = مبلغ ÷ `hours_logged` (`project_list`)؛ hourly = `rate`. تومانی و دلاری را جدا با
  نرخ هدف پروفایل مقایسه کن و اگر پایین‌تر است صریح بگو.
- **Scope creep:** `hours_logged` > `estimate_hours` × ۱٫۲ → هشدار + پیش‌نویس پیام change request یا قیمت اضافه.
- **مهلت‌ها:** `days_left` ≤ ۳ را برجسته کن؛ اگر ساعت باقی‌مانده با وقت آزاد (تقویم) نمی‌خواند، زودتر بگو.
- **پیگیری‌ها:** `project_list` → `follow_up_due: true`؛ lead/proposal بدون پیگیری بیش از ۵ روز.
- **طلب‌ها:** فاکتورهای `sent`/`overdue` در `notes/work/invoices.md`؛ سررسیدگذشته → پیگیری با skill `invoicing`.
- **ساعت قابل‌صورت‌حساب:** `time_report` هفته در برابر هدف پروفایل.

## قالب گزارش وضعیت («کارها چطوره؟» یا در بازبینی هفتگی)
```
**💼 وضعیت فریلنس** — {تاریخ}
- این هفته: ۱۸ ساعت (هدف ۲۵) · ⏱ تایمر روشن: X (۱:۲۰)
**مهلت‌ها:** ⚠️ X — ۲ روز مانده، ~۶ ساعت کار باقی
**پیگیری:** Z — پروپوزال ۶ روز بی‌جواب → پیام پیگیری بنویسم؟
**پول:** طلب … تومان (۱ سررسیدگذشته) · نرخ مؤثر Y: … (هدف …)
```
بخش‌های خالی را حذف کن؛ جدول نه.

## پول و قیمت‌گذاری
- **بازبینی نرخ هر ۳ ماه:** نرخ تومانی را با تورم اخیر (جستجوی وب؛ منبع و تاریخ را بگو) و نرخ بازار AI engineer
  مقایسه کن و پیشنهاد عددی بده. `reminder_add` تکرار فصلی ندارد → یادآور یک‌باره ۹۰ روز بعد و هر بار دوباره تنظیم.
- **پروژه تومانی طولانی:** تورم را در قیمت ببین؛ گزینه‌ها: پرداخت مرحله‌ای کوتاه‌تر، بند تعدیل، یا قیمت ارزی با منبع
  نرخ توافقی — تصمیم با کاربر.
- **قرارداد:** محدوده دقیق، تعداد اصلاحات، پرداخت مرحله‌ای (مثلاً ۳۰/۴۰/۳۰)، مالکیت کد، هزینه نگهداری. پیش‌نویس
  با skill `office-docs`؛ برای قرارداد بزرگ بررسی حقوقی را پیشنهاد بده.
- **درآمد نامنظم:** میانگین هزینه ماهانه = میانگین سه `finance_summary` اخیر (تومانی)؛ هدف صندوق اضطراری = ۳ تا ۶ برابر.
  تراکنش‌ها موجودی نشان نمی‌دهند؛ موجودی پس‌انداز را از پروفایل یا با سؤال بگیر. پیشنهاد: «حقوق ثابت ماهانه به خودت»
  و مازاد ماه‌های پردرآمد به صندوق اضطراری.
- مشتری خارجی و قیمت‌گذاری دلاری → `client-acquisition`؛ Upwork → `upwork-growth`.

## محرمانگی
اطلاعات مشتری (کد، داده، قرارداد) را فقط برای کار خودش استفاده کن. در محتوای برند شخصی، نام مشتری و جزئیات
محرمانه را حذف یا ناشناس کن، مگر کاربر اجازه داده باشد.
