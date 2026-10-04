---
name: deep-research
description: "Rigorous multi-source research for high-stakes questions and decisions (تحقیق عمیق و مستند): reframe the decision, test falsifiable hypotheses, triangulate every claim across ≥3 independent sources, run an adversarial pass, and save sources for reuse. Use when a wrong answer is costly — buying something expensive, choosing a technology/stack, job/relocation decisions, health or financial choices, comparing N options. NOT for quick facts."
license: MIT (adapted from alirezarezvani/claude-skills research/deep-research)
---

# Deep Research — تحقیق منضبط

برای سؤال‌های کم‌ریسک مستقیم جواب بده یا subagent `researcher` را صدا بزن. این skill وقتی است که اشتباه گران است.

## مراحل
1. **بررسی کار قبلی:** `notes/research/` را Grep کن؛ اگر قبلاً تحقیق شده، فقط به‌روزرسانی (delta) انجام بده.
2. **بازتعریف:** تصمیمی که پشت سؤال است را بنویس، و ۲ تا ۴ **فرضیه ابطال‌پذیر** (مثلاً «لپ‌تاپ X برای Docker سنگین کافی است»).
3. **برنامه:** زیرسؤال‌ها، کانال‌های منبع (مستندات رسمی، مقاله/پژوهش، داده رسمی، نقد تخصصی، بحث کاربران مثل Reddit/HN)، جستجوهای مخالف («X problems», «X vs Y downsides»)، و معیار توقف.
4. **جستجو موازی:** برای زیرسؤال‌های مستقل، چند subagent `researcher` را **هم‌زمان** اجرا کن (نه پشت سر هم). هر منبع: عنوان، URL، تاریخ، نقل‌قول عینی کوتاه.
5. **امتیاز و مثلث‌سازی:** هر منبع از نظر اعتبار / تازگی / سوگیری. هر ادعای اصلی باید ≥۳ منبع مستقل **از انواع مختلف** داشته باشد؛ کمتر از آن را «شواهد ناکافی» علامت بزن، نه واقعیت.
6. **ترکیب + نقد مخالف:** گزارش را بساز، بعد از خودت بپرس: کدام منبع ضعیف‌ترین حلقه است؟ چه شاهدی نظرم را عوض می‌کند؟ قوی‌ترین استدلال مخالف چیست؟ چه چیزی را جستجو نکردم؟ — و برای استدلال مخالف واقعاً جستجو کن.
7. **ذخیره:** در `notes/research/<slug>/` : `report.md` (گزارش نهایی)، `sources.md` (همه منابع با نقل‌قول و امتیاز)، `refresh.md` (اعداد/قیمت‌ها/فرضیه‌هایی که بعداً باید چک شوند).

## خروجی در چت (کوتاه)
- **جمع‌بندی و توصیه** (با سطح اطمینان: کم/متوسط/زیاد)
- **وضعیت فرضیه‌ها:** تأیید / رد / نامشخص
- **ریسک‌ها و قوی‌ترین استدلال مخالف**
- **منابع کلیدی** (۳ تا ۶ لینک با تاریخ)
- مسیر فایل گزارش کامل

## ضدالگوها
- منبع یا URL ساختگی ممنوع؛ اگر fetch چیزی برنگرداند، ادعا خالی می‌ماند.
- نتیجه‌گیری روی منابع هم‌نوع (مثلاً فقط وبلاگ‌های فروشنده) = مثلث‌سازی انجام نشده.
- برای قیمت و موجودی در ایران، تاریخ و منبع را صریح بگو؛ سریع تغییر می‌کنند.
