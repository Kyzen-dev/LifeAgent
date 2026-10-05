---
name: learning-plan
description: "Build and track a learning plan (برنامه یادگیری) for a skill, technology, book or course, tied to the user's career and income goals: clarify the goal, choose current verified resources, a week-by-week plan with hands-on outputs, goal/habit tracking, spaced-repetition review reminders, and quizzes with quick-reply buttons. Use when the user says «می‌خوام X یاد بگیرم», «برنامه یادگیری», «امتحانم کن», «ازم سؤال بپرس», shares a summary of something they learned, or asks about learning progress. For deep analysis of one document use deepread; for English practice use english-coach."
---

# برنامه یادگیری

**هدف:** یادگیری که به خروجی واقعی برسد (پروژه، مهارت قابل‌فروش، نرخ بالاتر)، با زمانی که کاربر واقعاً دارد.

## ۱. ساختن برنامه
1. **Intake** (حداکثر ۳ سؤال؛ بقیه از `memory/profile.md` و `goal_list`): چرا (کدام هدف)، سطح فعلی، ساعت در هفته، مهلت.
   سطح را با دکمه بپرس: `[[options: تازه‌کار | آشنا | کار کرده‌ام]]`.
   ظرفیت واقعی را با `time_report` و پروژه‌های فعال (`project_list`) بسنج؛ برنامه بزرگ‌تر از ظرفیت را صریح کوچک کن.
2. **اولویت:** بین موضوع‌های رقیب، آن که به درآمد یا پروژه نزدیک‌تر است اول (شکاف‌های `career-coach`، نیاز آگهی‌های Upwork، «امتحان کن» در `ai-digest`).
3. **منابع:** با جستجوی وب (WebSearch یا ابزار جستجوی موجود) ۳-۵ منبع به‌روز: مستند رسمی (برای کتابخانه‌ها context7 اگر هست)، یک کتاب یا دوره، یک پروژه عملی. تاریخ و نسخه منبع را چک کن؛ لینک ساختگی نده. موضوع بزرگ → subagent `researcher` یا `learning-coach`.
4. **برنامه هفته‌به‌هفته:** هر هفته: هدف، منبع (بخش مشخص)، ساعت، **خروجی عملی** (کد، پروژه کوچک، یادداشت). هفته آخر: پروژه قابل نمایش (GitHub/portfolio؛ پست با `personal-brand`).
5. **ذخیره و ثبت (با تأیید کاربر):** `notes/learning/<topic>-plan.md` (خط خلاصه، هدف، منابع، هفته‌ها با چک‌باکس، لاگ پیشرفت)؛ `goal_set` (area=learning، why، target_date)؛ جلسات مطالعه با `habit_create` (یا عادت یادگیری موجود در `habit_status`) یا `reminder_add` weekly.

## ۲. یادگیری فعال
- کاربر چیزی خواند یا دید (متن، لینک، ویدیو با `youtube_transcript`، فایل در inbox): خلاصه در `notes/learning/YYYY-MM-DD-<slug>.md` با «ایده‌های کلیدی»، «کاربرد در کار من» و «سؤال‌های مرور» (۳-۵ سؤال: یادآوری + کاربرد). خوانش عمیق یک سند → skill `deepread`.
- **مرور فاصله‌دار:** برای هر یادداشت جدید پیشنهاد بده و با تأیید، `reminder_add` در ۱، ۷ و ۳۰ روز بعد: «مرور: <موضوع> — بنویس «امتحانم کن <موضوع>»».

## ۳. امتحان (quiz)
1. سؤال‌ها از «سؤال‌های مرور» و «نقاط ضعف» یادداشت‌ها (Grep در `notes/learning/`)؛ نقاط ضعف قبلی اول؛ ترکیب یادآوری و کاربرد؛ **یکی‌یکی**.
2. چندگزینه‌ای: گزینه‌ها در متن با A/B/C و دکمه کوتاه `[[options: A | B | C | 🛑 بسه]]`؛ سؤال باز بدون دکمه.
3. جواب را صادقانه ارزیابی کن، شکاف را با توضیح کوتاه پر کن، و در بخش «نقاط ضعف» همان یادداشت ثبت کن.
4. پایان: امتیاز، یک پیشنهاد مشخص، و `habit_log` اگر عادت یادگیری تعریف شده.

## ۴. پیگیری
- «پیشرفتم چطوره؟» یا در `weekly-review`: چک‌باکس‌های فایل برنامه + `habit_status` → درصد پیشرفت با `goal_set` (id، progress).
- دو هفته عقب‌ماندگی → برنامه را بازچینی کن (کوچک‌تر، نه فشرده‌تر) و دلیل را در لاگ بنویس.
- اتمام: `goal_set` status=done و پیشنهاد پیش‌نویس پست «what I learned» با `personal-brand`.

## قالب برنامه در تلگرام (بدون جدول)
**📚 برنامه یادگیری: {موضوع}** — هدف · مهلت · ساعت در هفته
**هفته ۱:** … → خروجی: …
**هفته ۲:** … → خروجی: …
(حداکثر ۶-۸ خط؛ نسخه کامل در فایل)
**منابع:** ۳-۵ لینک، هر کدام با یک خط «چرا»
`[[options: ✅ ثبت هدف و یادآورها | ✏️ تغییر بده | ❌ فعلاً نه]]`
