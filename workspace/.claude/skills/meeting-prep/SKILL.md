---
name: meeting-prep
description: Prepare for an upcoming meeting (آمادگی جلسه) — attendees, context from email/notes/GitHub, agenda and questions; and capture meeting notes and action items afterward. Use when the user mentions an upcoming meeting or shares meeting notes.
---

# آمادگی و پیگیری جلسه

## قبل از جلسه
1. رویداد را از تقویم پیدا کن: زمان، شرکت‌کنندگان، توضیحات، لینک‌ها.
2. زمینه جمع کن: آخرین ایمیل‌ها با شرکت‌کنندگان، `notes/people/<name>.md`، یادداشت‌های پروژه در `notes/work/`، و اگر فنی است، issue/PRهای مرتبط در GitHub.
3. خروجی: هدف جلسه، ۳ تا ۵ نکته زمینه‌ای، دستور جلسه پیشنهادی، سؤال‌هایی که کاربر باید بپرسد، تصمیم‌هایی که باید گرفته شود.

## بعد از جلسه (وقتی کاربر یادداشت یا ویس می‌فرستد)
1. خلاصه، تصمیم‌ها و action itemها (مسئول + مهلت) را استخراج کن.
2. در `notes/work/YYYY-MM-DD-meeting-<topic>.md` ذخیره کن و `notes/people/` را به‌روز کن.
3. action itemهای کاربر را با `task_add` ثبت کن. پیشنهاد بده ایمیل follow-up برای شرکت‌کنندگان پیش‌نویس شود (ارسال با تأیید).
