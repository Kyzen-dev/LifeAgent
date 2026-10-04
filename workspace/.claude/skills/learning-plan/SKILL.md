---
name: learning-plan
description: Build and track a learning plan (برنامه یادگیری) for a skill, book, course or technology, with spaced-repetition review prompts. Use when the user wants to learn something, summarizes a book/article, or asks to be quizzed.
---

# برنامه یادگیری

## ساختن برنامه
1. هدف را دقیق کن: چرا، سطح فعلی، زمان در دسترس در هفته، مهلت.
2. با WebSearch منابع باکیفیت و به‌روز پیدا کن (مستندات رسمی، کتاب، دوره، پروژه عملی). برای موضوعات بزرگ، تحقیق را به subagent `researcher` بسپار.
3. برنامه هفته‌به‌هفته با خروجی عملی (پروژه کوچک، تمرین) بساز و در `notes/learning/<topic>-plan.md` ذخیره کن.
4. هدف را با `goal_set` (area=learning) و جلسات مطالعه را به‌صورت عادت (`habit_create`) یا یادآور ثبت کن.

## یادگیری فعال
- وقتی کاربر چیزی خواند/دید، خلاصه‌اش را در `notes/learning/` ذخیره کن با بخش «ایده‌های کلیدی» و «سؤال‌های مرور».
- مرور فاصله‌دار: برای هر یادداشت جدید، یادآورهای مرور ۱، ۷ و ۳۰ روز بعد بگذار (`reminder_add`) با متن «مرور: <موضوع> — از من بخواه ازت سؤال بپرسم».
- وقتی کاربر خواست امتحانش کنی، از «سؤال‌های مرور» یادداشت‌ها یکی‌یکی بپرس، جوابش را ارزیابی کن و نقاط ضعف را در یادداشت ثبت کن.
- پیشرفت هدف یادگیری را با `goal_set` به‌روز کن.
