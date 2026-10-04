---
name: finance-report
description: Monthly personal finance report (گزارش مالی ماهانه) on Jalali months — income, expenses by category, budgets, trends vs last month, savings rate, and a chart. Use on the 1st of each Jalali month or when the user asks about their spending/money.
---

# گزارش مالی ماهانه

1. `finance_summary` برای ماه هدف (پیش‌فرض: ماه شمسی گذشته) و ماه قبل از آن برای مقایسه.
2. محاسبه کن: درآمد، هزینه، خالص، نرخ پس‌انداز (خالص ÷ درآمد)، تغییر هر دسته نسبت به ماه قبل.
3. دسته‌هایی که از بودجه گذشته‌اند یا بیش از ۲۵٪ رشد داشته‌اند را برجسته کن و با `finance_list_transactions` بزرگ‌ترین تراکنش‌هایشان را ببین.
4. اشتراک‌ها و هزینه‌های تکراری را تشخیص بده (همان مبلغ/دسته در چند ماه).
5. **نمودار (اختیاری):** اگر داده کافی است، با Python/matplotlib یک نمودار میله‌ای دسته‌ها در `outbox/finance-YYYY-MM.png` بساز و با `send_file` بفرست. (اجرای Bash تأیید کاربر را لازم دارد؛ اگر رد شد، بدون نمودار ادامه بده.)

## خروجی
**💰 گزارش مالی {ماه سال}**
- درآمد / هزینه / خالص / نرخ پس‌انداز
- ۵ دسته بزرگ هزینه با درصد و مقایسه با ماه قبل
- وضعیت بودجه‌ها (✅ / ⚠️ / 🔴)
- ۲ تا ۳ پیشنهاد مشخص و عددی (مثلاً «اشتراک X که سه ماه استفاده نشده: ۱۲۰ هزار تومان در ماه»)

یادداشت گزارش را در `notes/reviews/YYYY-MM-finance.md` ذخیره کن.
