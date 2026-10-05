# 🧠 مدل‌های هوش مصنوعی: Claude، GPT، Gemini، DeepSeek و بقیه

LifeAgent همیشه روی **Claude Agent SDK** اجرا می‌شود (skillها، MCPها، subagentها، دکمه تأیید و حافظه همه از همین‌جاست).
آنچه عوض می‌شود فقط **مدلی است که فکر می‌کند**. هر مدلی که کلیدش را در `.env` بگذاری، در تلگرام با `/model` قابل انتخاب است.

## چطور کار می‌کند
```
تلگرام → LifeAgent → Claude Agent SDK (Claude CLI)
                         │  ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN (برای هر گفتگو جدا)
                         ├─► api.anthropic.com            ← Claude (مستقیم)
                         ├─► openrouter.ai/api            ← Claude / GPT / Gemini / Grok با یک کلید
                         ├─► api.deepseek.com/anthropic   ← DeepSeek
                         ├─► api.moonshot.ai/anthropic    ← Kimi
                         ├─► api.z.ai/api/anthropic       ← GLM
                         └─► litellm:4000 (کانتینر اختیاری) ← OpenAI / Gemini با کلید خودت، Ollama
```
این سرویس‌ها همه «API سازگار با Anthropic» دارند؛ برای OpenAI و Gemini یک کانتینر کوچک **LiteLLM** ترجمه را انجام می‌دهد.

> ⚠️ **صادقانه:** Anthropic رسماً اجرای Claude Code با مدل‌های غیر Claude را پشتیبانی نمی‌کند. این مسیر کار می‌کند
> (OpenRouter، DeepSeek، Z.ai و LiteLLM خودشان مستندش کرده‌اند)، ولی کیفیت استفاده از ابزارها و پیروی از skillها
> در مدل‌های دیگر متفاوت است. به همین دلیل آن‌ها در `/model` با برچسب «آزمایشی» آمده‌اند. برای کار اصلی Claude را نگه دار
> و مدل‌های دیگر را برای صرفه‌جویی یا به‌عنوان پشتیبان (fallback) استفاده کن.

## کدام را انتخاب کنم؟
| هدف | پیشنهاد |
|---|---|
| بهترین تعادل کیفیت/هزینه (پیش‌فرض) | `sonnet` — Claude Sonnet 5.5 (۲$/۱۰$ در هر میلیون توکن) |
| کار سخت، تحقیق طولانی، معماری | `opus` (۴$/۲۰$) یا `fable` (قوی‌ترین، ۱۰$/۵۰$) |
| ارزان برای کارهای ساده | `haiku` (۱$/۵$) — یا `deepseek` (۰٫۳$/۱٫۲$، **عکس نمی‌بیند**) |
| یک کلید برای همه | OpenRouter: `or-sonnet`، `or-gpt`، `or-gemini`، `or-gemini-flash`، `or-grok` |
| کلید OpenAI/Gemini خودت را داری | gateway: `gpt`، `gpt-luna`، `gemini`، `gemini-flash` |
| پشتیبان وقتی Anthropic مشکل دارد | `LIFEAGENT_FALLBACK_MODEL=or-sonnet` یا `deepseek-pro` |

قیمت‌ها (مهر ۱۴۰۵) در `lifeagent/models.py` ثبت‌اند و `/cost` برای مدل‌های غیر Anthropic از روی آن‌ها هزینه را **تخمین** می‌زند.

## راه‌اندازی
ساده‌ترین راه: `python3 deploy/configure.py` → مرحله ۳ هر تعداد ارائه‌دهنده که بخواهی اضافه کن (کلیدها همان‌جا چک می‌شوند)
→ مرحله ۴ مدل پیش‌فرض و مدل پشتیبان را انتخاب کن. بعد `docker compose up -d --build`.

| ارائه‌دهنده | کلید در `.env` | از کجا |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys (+ شارژ Billing) |
| OpenRouter | `OPENROUTER_API_KEY` | openrouter.ai/keys (+ شارژ Credits) |
| DeepSeek | `DEEPSEEK_API_KEY` | platform.deepseek.com |
| Moonshot (Kimi) | `MOONSHOT_API_KEY` | platform.moonshot.ai |
| Z.ai (GLM) | `ZAI_API_KEY` | z.ai |
| OpenAI / Gemini (gateway) | `OPENAI_API_KEY` و/یا `GEMINI_API_KEY` + `LITELLM_MASTER_KEY` + `COMPOSE_PROFILES=gateway` | platform.openai.com / aistudio.google.com |

### gateway (OpenAI / Gemini / مدل محلی)
- ویزارد اگر کلید OpenAI یا Gemini بدهی، خودش `LITELLM_MASTER_KEY` تصادفی می‌سازد و `COMPOSE_PROFILES=gateway` را می‌گذارد؛
  از آن به بعد `docker compose up -d` کانتینر `lifeagent-litellm` را هم بالا می‌آورد.
- تنظیمات مدل‌ها: `deploy/litellm/config.yaml`. نام هر مدل (`model_name`) باید با `model_id` همان مدل در کاتالوگ یکی باشد.
- حافظه: یک کانتینر LiteLLM حدود چند صد مگابایت RAM می‌خواهد. روی سرور ۱ گیگی، OpenRouter را به gateway ترجیح بده.
- سلامت: `docker compose logs litellm` و `python -m lifeagent.doctor` (خط «LiteLLM gateway reachable»).

## استفاده در تلگرام
- `/model` → فهرست مدل‌های در دسترس با توضیح و قیمت، با دکمه برای انتخاب.
- `/model opus` → انتخاب مستقیم با نام کوتاه (alias).
- انتخاب برای **همان گفتگو** ذخیره می‌شود (بعد از ری‌استارت هم می‌ماند).
- عوض کردن مدل **در همان ارائه‌دهنده** (مثلاً sonnet → opus) گفتگو را ادامه می‌دهد؛ رفتن به **ارائه‌دهنده دیگر**
  گفتگوی کوتاه‌مدت را از نو شروع می‌کند (حافظه بلندمدت، یادداشت‌ها و داده‌ها دست نمی‌خورند).
- `/cost` هزینه امروز و ماه را به تفکیک مدل نشان می‌دهد.

## پشتیبان خودکار (failover)
اگر `LIFEAGENT_FALLBACK_MODEL` تنظیم شده باشد و مدل اصلی خطای «کلید نامعتبر / اعتبار تمام شده / سقف درخواست / قطعی سرور»
بدهد، ربات یک پیام کوتاه می‌دهد و **همان پیام** را با مدل پشتیبان جواب می‌دهد؛ تا ۳۰ دقیقه با پشتیبان ادامه می‌دهد و بعد
دوباره مدل اصلی را امتحان می‌کند. اگر در آن نوبت ابزاری اجرا شده بود (مثلاً تراکنشی ثبت شده بود)، برای جلوگیری از کار
تکراری دوباره اجرا **نمی‌شود** و فقط خطا گزارش می‌شود.

## تفاوت مدل‌های غیر Claude
- **جستجوی وب:** WebSearch مخصوص Anthropic است؛ برای مدل‌های دیگر خودکار یک MCP جستجو اضافه می‌شود:
  Tavily اگر `TAVILY_API_KEY` داری (رایگان ۱٬۰۰۰ در ماه)، وگرنه لایه رایگان Exa بدون کلید.
- **تفکر (thinking) و effort:** فقط برای Claude فرستاده می‌شود.
- **عکس:** DeepSeek عکس نمی‌بیند؛ ربات این را به کاربر می‌گوید و پیشنهاد عوض کردن مدل می‌دهد.
- **subagentها و کارهای پس‌زمینه** (مثل خلاصه کردن صفحه وب) هم روی همان ارائه‌دهنده اجرا می‌شوند (مدل کوچک‌تر همان‌جا).

## مدل دلخواه (data/models.toml)
برای اضافه کردن مدلی که در کاتالوگ نیست (یا تغییر قیمت/برچسب)، فایل `data/models.toml` بساز (در git نیست):
```toml
[[model]]
alias = "qwen-coder"
provider = "openrouter"
model_id = "qwen/qwen3-coder"
label = "Qwen3 Coder (آزمایشی)"
note = "کدنویسی ارزان"
price_in = 0.2
price_out = 0.8

# یک endpoint سازگار با Anthropic دیگر:
[provider.myhost]
label = "My endpoint"
key_env = "MYHOST_API_KEY"
base_url = "https://example.com/anthropic"
```
یا بدون فایل: `/model openrouter:qwen/qwen3-coder` (شکل `ارائه‌دهنده:شناسه_مدل`).
بعد از تغییر فایل، ربات را ری‌استارت کن: `docker compose restart lifeagent`.

## ویس (تبدیل گفتار به متن)
- `GROQ_API_KEY` (console.groq.com، لایه رایگان دارد) → Whisper large-v3-turbo روی Groq. پیشنهاد اول.
- یا `OPENAI_API_KEY` → whisper-1. با `TRANSCRIBE_PROVIDER=auto` اول Groq امتحان می‌شود.

## آزمایش
```bash
docker compose run --rm lifeagent python -m lifeagent.doctor --live                # مدل پیش‌فرض
docker compose run --rm lifeagent python -m lifeagent.doctor --live --model or-gpt  # یک مدل خاص
docker compose run --rm lifeagent python -m lifeagent.doctor --live --model all     # همه (چند سنت)
```
