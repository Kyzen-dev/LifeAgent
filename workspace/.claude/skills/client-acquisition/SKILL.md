---
name: client-acquisition
description: "Win better-paying freelance clients, especially international USD clients outside freelance platforms (پیدا کردن مشتری خارجی مستقیم، پروپوزال، قیمت‌گذاری دلاری): positioning, LinkedIn/X outreach, discovery calls, proposals and estimates, pricing, case studies. Use when the user wants more/better direct clients, writes a non-Upwork proposal, or prices a project; for Upwork itself use upwork-growth."
---

# Client Acquisition — مشتری بهتر و درآمد دلاری

## دو کانال
- **Upwork:** مسیر کامل رشد حساب از صفر تا Top Rated در skill `upwork-growth` است (اگر در پروفایل آمده که کاربر حساب Upwork فعال دارد). دسترسی به حساب و مسائل هویتی/مالی آن با خود کاربر است؛ درباره دور زدن احراز هویت یا تشخیص موقعیت راهنمایی نکن.
- **مشتری مستقیم خارجی** (پایین): مکمل Upwork و بدون کارمزد پلتفرم؛ برند شخصی در LinkedIn/X به هر دو کمک می‌کند.

## مشتری مستقیم خارجی
1. **جایگاه‌یابی (niche):** به‌جای «AI developer» عمومی، یک پیشنهاد مشخص: مثلاً «AI agents آماده production با LangGraph برای اتوماسیون پشتیبانی/پردازش اسناد/ابزارهای داخلی شرکت‌های کوچک». با کاربر ۲-۳ گزینه را بسنج (skill `decision-helper` حالت A).
2. **اثبات (portfolio):** ۲-۳ case study کوتاه از پروژه‌های واقعی (ناشناس‌شده): مسئله → معماری → نتیجه عددی. یک repo نمایشی تمیز در GitHub با README خوب و دموی کوتاه.
3. **کانال‌ها:** LinkedIn و X (با skill `personal-brand`)، جامعه‌های تخصصی (Discord/Slack فریم‌ورک‌ها، GitHub issues/PR در پروژه‌های LangChain اکوسیستم)، و معرفی از مشتری‌های راضی.
4. **پیام سرد (outreach):** شخصی، کوتاه، ارزش‌محور: یک مشاهده مشخص از کسب‌وکار طرف + یک ایده/نمونه کوچک + یک سؤال ساده. بدون اسپم انبوه. پیش‌نویس را بنویس؛ ارسال با خود کاربر است. هر outreach را با `project_upsert` (status=lead، next_action) ثبت کن.
5. **پرداخت:** راه‌های قانونی و عملی دریافت پول برای ساکنان ایران دائماً تغییر می‌کند؛ با WebSearch به‌روز بررسی کن و ریسک‌ها (قانونی، نوسان، کارمزد، امنیت) را شفاف بگو. توصیه قطعی حقوقی نده.

## جلسه کشف نیاز (discovery call)
سؤال‌ها: مسئله فعلی و هزینه‌اش، راه‌حل‌های امتحان‌شده، داده/سیستم‌های موجود، معیار موفقیت، بودجه و زمان، تصمیم‌گیرنده. اسکریپت و سؤال‌های انگلیسی را آماده کن؛ قبلش با skill `english-coach` تمرین role-play پیشنهاد بده.

## پروپوزال و تخمین
ساختار: بازگویی مسئله با زبان مشتری → راه‌حل پیشنهادی (معماری سطح بالا؛ برای جزئیات فنی skill `agent-architect`) → مراحل (milestone) با خروجی قابل‌تحویل → زمان‌بندی → قیمت (۲-۳ گزینه: پایه/استاندارد/کامل) → ریسک‌ها و فرض‌ها → چرا من (case study مرتبط) → قدم بعدی.
- تخمین: کار را به task تقسیم کن، برای هر کدام بازه بده، ۲۰-۳۰٪ ریسک برای ابهام‌های LLM (کیفیت داده، eval، تکرار prompt) اضافه کن.
- برای مشتری خارجی انگلیسی روان و بی‌اغراق بنویس؛ فایل PDF با `office-docs`.
- ثبت: `project_upsert` status=proposal + follow-up سه روز بعد.

## قیمت‌گذاری دلاری
- داده بازار را با WebSearch (نرخ‌های AI/LLM engineer فریلنس، با تاریخ و منبع) بیاور و بازه بده.
- پروژه‌های agent را ترجیحاً **fixed با milestone** یا retainer ماهانه قیمت بده، نه ساعتی ارزان. برای اولین مشتری‌های خارجی، تخفیف «case study» محدود و صریح (نه نرخ دائمی پایین).
- هزینه‌های جاری مشتری (API مدل، hosting، نگهداری) را جدا و شفاف بنویس.

## پیگیری
در بازبینی هفتگی: تعداد outreach، پاسخ‌ها، پروپوزال‌ها، نرخ تبدیل، و یک قدم بهبود برای هفته بعد.
