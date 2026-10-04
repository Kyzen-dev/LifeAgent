---
name: evening-checkin
description: Evening check-in (چک‌این شبانه) — ask briefly how the day went, log habits/mood/journal from the answer, and preview tomorrow. Use for the scheduled evening routine.
---

# چک‌این شبانه

1. `habit_status` را بگیر و عادت‌هایی که امروز ثبت نشده‌اند را پیدا کن.
2. یک پیام **کوتاه و گرم** بفرست (حداکثر ۶ خط):
   - «امروز چطور گذشت؟ حال و انرژی از ۱ تا ۱۰؟»
   - فهرست عادت‌های ثبت‌نشده امروز تا با یک جواب کوتاه ثبتشان کند.
   - اولین رویداد فردا از تقویم (اگر دسترسی هست).
3. وقتی کاربر جواب داد: حال/انرژی و هر نکته معنادار را با `journal_add` ثبت کن، عادت‌های انجام‌شده را با `habit_log`، و اگر کاری برای فردا گفت با `task_add`.
4. اگر چند روز پشت‌سرهم حال یا انرژی پایین بوده (`journal_recent`)، با ملایمت اشاره کن و یک پیشنهاد کوچک و عملی بده.
