---
name: client-acquisition
description: "Win better-paying freelance clients, especially international USD clients outside freelance platforms (پیدا کردن مشتری خارجی مستقیم، پیام سرد، جلسه کشف نیاز، پروپوزال و قیمت‌گذاری دلاری؛ «find clients», «cold outreach», «how much should I charge»): positioning, LinkedIn/X outreach, discovery calls, proposals and estimates, USD pricing, case studies, and a weekly outreach funnel. Use when the user wants more or better direct clients, writes a non-Upwork proposal, or prices a project. For Upwork itself use upwork-growth; for a numbered quote/invoice document use invoicing; for running active projects use freelance-ops."
---

# Client Acquisition — مشتری بهتر و درآمد دلاری

تخصص، niche انتخاب‌شده، نرخ فعلی و هدف، و کانال‌های فعال را از بخش «کار» در `memory/profile.md` بخوان؛
case studyها را از `notes/work/` (ناشناس‌شده) بردار.

## دو کانال
- **Upwork:** مسیر کامل رشد حساب در skill `upwork-growth`. دسترسی به حساب و مسائل هویتی/مالی آن با خود کاربر است؛
  درباره دور زدن احراز هویت، تحریم یا تشخیص موقعیت راهنمایی نکن.
- **مشتری مستقیم خارجی** (پایین): مکمل Upwork و بدون کارمزد پلتفرم؛ برند شخصی در LinkedIn/X به هر دو کمک می‌کند.

## مشتری مستقیم خارجی
1. **جایگاه‌یابی (niche):** به‌جای «AI developer» عمومی، یک پیشنهاد مشخص بر اساس تخصص پروفایل (مثلاً «AI agents آماده
   production برای اتوماسیون پشتیبانی/پردازش اسناد/ابزارهای داخلی شرکت‌های کوچک»). ۲-۳ گزینه را با skill
   `decision-helper` (حالت A) بسنج و نتیجه را در پروفایل ثبت کن.
2. **اثبات:** ۲-۳ case study کوتاه از پروژه‌های واقعی (ناشناس‌شده): مسئله → معماری → نتیجه عددی. یک repo نمایشی
   تمیز در GitHub با README خوب و دموی کوتاه (طراحی با `agent-architect`).
3. **کانال‌ها:** LinkedIn و X (skill `personal-brand`)، جامعه‌های تخصصی (Discord/Slack فریم‌ورک‌ها، issue/PR مفید در
   اکوسیستم LangChain)، و معرفی از مشتری‌های راضی.
4. **پیام سرد (outreach):** شخصی، کوتاه (حداکثر ~۹۰ کلمه انگلیسی)، ارزش‌محور: یک مشاهده مشخص از کسب‌وکار طرف +
   یک ایده/نمونه کوچک + یک سؤال ساده. بدون ارسال انبوه. پیش‌نویس با تو، ارسال با کاربر. هر outreach →
   `project_upsert` (client، title، status=lead، source=linkedin/x/referral/direct، next_action «follow-up»،
   next_action_date ۵ روز بعد).
5. **پرداخت:** راه‌های قانونی و عملی دریافت پول برای ساکنان ایران دائماً تغییر می‌کند؛ با جستجوی وب (WebSearch یا ابزار
   جستجوی موجود) به‌روز بررسی کن، تاریخ و منبع را بگو، و ریسک‌ها (قانونی، نوسان، کارمزد، امنیت) را شفاف بگو.
   توصیه قطعی حقوقی نده و راه دور زدن تحریم یا KYC پیشنهاد نکن.

قالب پیش‌نویس پیام در تلگرام:
```
✉️ **پیش‌نویس برای {نام/شرکت}** ({کانال})
{متن انگلیسی در بلوک کد تا راحت کپی شود}
چرا این زاویه: {یک خط فارسی}
[[options: ✅ خوبه | ✏️ کوتاه‌ترش کن | 🔄 زاویه دیگه]]
```

## جلسه کشف نیاز (discovery call)
سؤال‌ها: مسئله فعلی و هزینه‌اش، راه‌حل‌های امتحان‌شده، داده/سیستم‌های موجود، معیار موفقیت، بودجه و زمان،
تصمیم‌گیرنده. اسکریپت و سؤال‌های انگلیسی را آماده کن و تمرین role-play با skill `english-coach` پیشنهاد بده.
بعد از جلسه: یادداشت در `notes/work/YYYY-MM-DD-meeting-<client>.md` و `project_upsert` status=interview.

## پروپوزال و تخمین
ساختار: بازگویی مسئله با زبان مشتری → راه‌حل (معماری سطح بالا؛ جزئیات با `agent-architect`) → مراحل (milestone)
با خروجی قابل‌تحویل → زمان‌بندی → قیمت (۲-۳ گزینه: پایه/استاندارد/کامل) → ریسک‌ها و فرض‌ها → چرا من (case study
مرتبط) → قدم بعدی.
- تخمین: کار را به task تقسیم کن، برای هر کدام بازه بده و ۲۰-۳۰٪ ذخیره برای ابهام‌های LLM (کیفیت داده، eval،
  تکرار prompt) اضافه کن.
- انگلیسی روان و بی‌اغراق؛ فایل PDF با `office-docs`. اگر مشتری پیش‌فاکتور/quote رسمی شماره‌دار خواست → skill `invoicing`.
- ذخیره در `notes/work/YYYY-MM-DD-proposal-<client>.md`؛ `project_upsert` status=proposal، billing، rate، currency،
  estimate_hours، و follow-up سه روز بعد.

## قیمت‌گذاری دلاری
- داده بازار را با جستجوی وب (نرخ‌های فریلنس AI/LLM engineer، با تاریخ و منبع) بیاور و بازه بده؛ عدد از حافظه نگو.
- پروژه‌های agent را ترجیحاً **fixed با milestone** یا retainer ماهانه قیمت بده، نه ساعتی ارزان. برای اولین مشتری‌های
  خارجی، تخفیف «case study» محدود و صریح (نه نرخ دائمی پایین).
- برای مقایسه با کار ایرانی، معادل تومانی نرخ را با `iran_market_prices` (یا جستجوی وب) با منبع و زمان نشان بده.
- هزینه‌های جاری مشتری (API مدل، hosting، نگهداری) را جدا و شفاف بنویس.
- مشتری جدید خارجی: پیش‌پرداخت قبل از شروع (برای مرحله اول) و پرداخت مرحله‌ای را پیشنهاد بده؛ فاکتور با `invoicing`.

## بعد از برد
`client_upsert` (currency=USD، default_rate، source، status=active) + `project_upsert` status=active → ادامه کار با
`freelance-ops`؛ از مشتری راضی بعد از تحویل testimonial و اجازه case study بخواه.

## پیگیری هفتگی (در بازبینی هفتگی)
`pipeline_stats` (days=7 و 30، برای هر source مثل linkedin/x/referral) + شمارش leadهای این هفته از `project_list`
(status=lead): تعداد outreach، پاسخ‌ها، پروپوزال‌ها، مصاحبه‌ها، استخدام‌ها و نرخ تبدیل؛ یک آزمایش بهبود برای هفته بعد.
