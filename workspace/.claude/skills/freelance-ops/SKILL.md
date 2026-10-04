---
name: freelance-ops
description: "Run the user's freelance business (مدیریت کار فریلنس): clients, projects and pipeline, time tracking («شروع کار روی پروژه X» / «تموم کردم»), hours and effective hourly rate, deadlines, scope creep, rate reviews against inflation, and irregular-income cash flow. Use whenever the user mentions a client, project, hours, timer, deadline, rate, or getting paid."
---

# Freelance Ops

زمینه کاربر (تخصص، ساعت کاری، نوع مشتری‌ها و ارز پرداخت، هدف درآمدی) را از بخش «کار» در `memory/profile.md` بخوان.

## ابزارها
`client_upsert` · `client_list` · `project_upsert` · `project_list` · `timer_start` · `timer_stop` · `timer_status` · `time_log` · `time_report` · و برای پول: `finance_add_transaction`.

## زبان طبیعی → ابزار
| کاربر می‌گوید | کار تو |
|---|---|
| «شروع کار روی ربات فروشگاه» | `timer_start` (پروژه را با بخشی از عنوان پیدا کن) |
| «تموم کردم، API پرداخت رو وصل کردم» | `timer_stop` با note |
| «دیروز ۳ ساعت روی X کار کردم» | `time_log` |
| «یه مشتری جدید: آقای Y، پروژه چت‌بات، ساعتی ۸۰۰ تومن» | `client_upsert` + `project_upsert` |
| «پروپوزال رو برای Z فرستادم» | `project_upsert` status=proposal و next_action «follow-up» با next_action_date سه روز بعد |
| «پول پروژه X رو گرفتم» | `finance_add_transaction` (kind=income، category «درآمد فریلنس»، note = پروژه) و اگر پروژه تمام شده status=done |

اگر کاربر تایمر را روشن گذاشته و بیش از ۴ ساعت گذشته، قبل از توقف بپرس واقعاً این‌قدر کار کرده یا یادش رفته خاموش کند.

## سلامت کسب‌وکار (در گزارش‌ها و وقتی پرسید)
- **نرخ مؤثر ساعتی:** برای پروژه‌های fixed = مبلغ ÷ ساعت ثبت‌شده. اگر از نرخ هدف پایین‌تر است صریح بگو.
- **Scope creep:** اگر ساعت ثبت‌شده از `estimate_hours` × ۱٫۲ بیشتر شد، هشدار بده و پیشنهاد بده درباره change request یا قیمت اضافه با مشتری صحبت کند (متن پیام را هم بنویس).
- **مهلت‌ها:** پروژه‌های با `days_left` ≤ ۳ را در گزارش صبح برجسته کن؛ اگر ساعت باقی‌مانده با زمان در دسترس جور نیست، زودتر بگو.
- **Pipeline:** فرصت‌های lead/proposal بدون پیگیری بیش از ۵ روز را یادآوری کن.
- **هدف ساعت:** ساعت کار عمیق و قابل‌صورت‌حساب هفته را با هدف پروفایل مقایسه کن.

## پول و قیمت‌گذاری
- **بازبینی نرخ هر ۳ ماه:** نرخ تومانی را با تورم (با WebSearch نرخ تورم رسمی/نقطه‌به‌نقطه اخیر) و نرخ بازار برای AI Engineer مقایسه کن و پیشنهاد عددی بده. یادآور فصلی بگذار.
- **قراردادها:** برای پروژه جدید یادآوری کن: محدوده دقیق، تعداد اصلاحات، پرداخت مرحله‌ای (مثلاً ۳۰/۴۰/۳۰)، مالکیت کد، و هزینه نگهداری بعد از تحویل. در صورت درخواست، پیش‌نویس قرارداد ساده را با skill `office-docs` بساز.
- **درآمد نامنظم:** صندوق اضطراری ۳ تا ۶ ماه هزینه را هدف بگیر؛ وضعیتش را از `finance_summary` حساب کن.
- قیمت‌گذاری مشتری خارجی و مسیر دلاری → skill `client-acquisition`.

## محرمانگی
اطلاعات مشتری (کد، داده، قرارداد) را فقط برای کار خودش استفاده کن. در محتوای برند شخصی، نام مشتری و جزئیات محرمانه را حذف یا ناشناس کن مگر کاربر اجازه داده باشد.
