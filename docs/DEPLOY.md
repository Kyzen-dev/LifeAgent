# راهنمای کامل راه‌اندازی LifeAgent — از صفر تا استفاده روزانه

این راهنما را به ترتیب جلو برو. هر مرحله یک «✔ نتیجه درست» دارد؛ تا آن را ندیدی، سراغ مرحله بعد نرو.
اگر هر جا خطایی دیدی، به بخش **۹. رفع اشکال** برو یا متن خطا را برای Claude بفرست.

**نقشه کلی (حدود ۱٫۵ تا ۲ ساعت برای بار اول):**

| بخش | چه کاری | زمان |
|---|---|---|
| ۱ | ساخت حساب‌ها و کلیدها | ۲۰ دقیقه |
| ۲ | تست در GitHub Codespaces (بدون سرور) | ۲۰ دقیقه |
| ۳ | سرور دائمی رایگان در Oracle Cloud | ۴۰ دقیقه |
| ۴ | اولین گفتگو و آشنایی | ۱۰ دقیقه |
| ۵ | چک‌لیست تست | ۳۰ دقیقه |
| ۶ تا ۹ | اتصال‌های اختیاری، نگهداری، هزینه، رفع اشکال | هر وقت لازم شد |

> **چرا سرور خارج؟** Telegram API و Anthropic API از داخل ایران در دسترس نیستند؛ ربات باید روی سروری خارج از ایران اجرا شود. خودت از هر جایی با تلگرام با آن حرف می‌زنی.

> **ریپو عمومی است.** فایل‌های شخصی (`.env` با کلیدها و `workspace/memory/profile.md`) در `.gitignore` هستند و هیچ‌وقت نباید commit شوند.

---

## ۱. ساخت حساب‌ها و کلیدها

### ۱-۱. دو ربات تلگرام
در تلگرام به [@BotFather](https://t.me/BotFather) برو:
1. `/newbot` → نام نمایشی (مثلاً `My LifeAgent`) → username که با `bot` تمام شود (مثلاً `myname_life_bot`).
2. پیامی که BotFather می‌دهد یک **توکن** دارد، شبیه `7123456789:AAH...`. آن را جایی امن نگه دار. این **ربات اصلی** است.
3. دوباره `/newbot` → یک ربات دوم مثلاً `myname_life_test_bot` → این **ربات تستی** است.

**✔ نتیجه درست:** دو توکن داری.
> چرا دو ربات؟ هر توکن فقط در **یک** جا می‌تواند همزمان روشن باشد. تستی برای Codespaces، اصلی برای سرور.

### ۱-۲. کلید Anthropic (مغز ربات)
1. به [console.anthropic.com](https://console.anthropic.com) برو و وارد شو.
2. **Settings → Billing:** اعتبار شارژ کن (۱۰ تا ۲۰ دلار برای ماه اول کافی است؛ مدل پیش‌فرض اقتصادی است).
3. **Settings → Limits:** یک **سقف خرج ماهانه** بگذار، مثلاً ۳۰ دلار. این مهم‌ترین محافظ هزینه است.
4. **API Keys → Create Key** → نامش را `lifeagent` بگذار → کلید (`sk-ant-...`) را کپی کن. فقط یک بار نشان داده می‌شود.

**✔ نتیجه درست:** یک کلید `sk-ant-...` و اعتبار مثبت.

### ۱-۳. اختیاری
- **ویس:** کلید OpenAI از [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (هزینه تبدیل گفتار به متن بسیار کم است). بدون آن، بقیه چیزها کار می‌کند.
- **GitHub:** حساب GitHub برای Codespaces لازم است (همانی که ریپو دارد).

### ۱-۴. فایل‌های شخصی
دو فایلی که Claude برایت فرستاده را آماده نگه دار:
- `.env` — تنظیمات شخصی‌ات (ساعت روال‌ها، اذان، مدل) با کلیدهای خالی. **کلیدها را لازم نیست دستی پر کنی؛ ویزارد این کار را می‌کند.**
- `profile.md` — پروفایل شخصی‌ات.

---

## ۲. تست در GitHub Codespaces (بدون سرور)

Codespaces یک کامپیوتر ابری موقت است که GitHub رایگان می‌دهد (ماهی ۱۲۰ core-hour، یعنی حدود ۶۰ ساعت با ماشین ۲ هسته‌ای).

1. به https://github.com/Kyzen-dev/LifeAgent برو → دکمه سبز **Code** → تب **Codespaces** → **Create codespace on ...**
   چند دقیقه صبر کن تا VS Code در مرورگر باز شود و نصب‌ها (پیام‌های ترمینال پایین صفحه) تمام شوند.
2. **فایل‌های شخصی را آپلود کن:** از پنل فایل‌ها (سمت چپ):
   - `.env` را روی پوشه اصلی (ریشه) بکش و رها کن.
   - `profile.md` را داخل پوشه `workspace/memory/` بکش و رها کن.
3. **ویزارد تنظیمات** را در ترمینال اجرا کن:
   ```bash
   python deploy/configure.py
   ```
   ویزارد به انگلیسی سؤال می‌پرسد (چون ترمینال‌ها فارسی را خوب نشان نمی‌دهند):
   | سؤال | چه جوابی بدهی |
   |---|---|
   | `Bot token` | توکن **ربات تستی** را paste کن (در ترمینال مرورگر: Ctrl+Shift+V یا راست‌کلیک → Paste) |
   | `Detect it automatically?` | Enter بزن؛ بعد در تلگرام به **ربات تستی** یک پیام (مثلاً «سلام») بفرست و دوباره Enter |
   | `Use <نام تو> — id ...?` | Enter (تأیید) |
   | `API key` | کلید Anthropic |
   | `OpenAI API key` | کلید OpenAI یا فقط Enter برای رد کردن |
   | `GitHub fine-grained token` | فعلاً Enter |
   | `Prayer-time reminders (azan)?` | `y` و Enter |
   | `City` | `Tehran` (یا شهر خودت به انگلیسی) |

   هر کلید همان لحظه چک می‌شود: `OK` سبز یعنی درست، `XX` قرمز یعنی دوباره وارد کن.
   **✔ نتیجه درست:** `OK saved .../.env`
4. **چک سلامت کامل:**
   ```bash
   python -m lifeagent.doctor --live
   ```
   **✔ نتیجه درست:** خط‌های ✅ برای config، skills (۳۱)، Telegram، Anthropic، و در آخر
   `Claude Agent SDK (live) — reply='OK'` و جمله `All required checks passed.`
   (⚠️ زرد برای چیزهای اختیاری مثل GitHub/Google طبیعی است.)
5. **روشن کردن ربات:**
   ```bash
   python -m lifeagent
   ```
   **✔ نتیجه درست:** در لاگ `LifeAgent is up` دیده می‌شود. این ترمینال را باز بگذار.
6. حالا برو سراغ **بخش ۴** (اولین گفتگو) با ربات تستی، و بعد **بخش ۵** (چک‌لیست).
7. **بعد از تست حتماً خاموش کن:** https://github.com/codespaces → «…» کنار codespace → **Stop codespace**.
   (بستن تب مرورگر خاموشش نمی‌کند و سهمیه رایگان مصرف می‌شود.)

---

## ۳. سرور دائمی رایگان در Oracle Cloud

### ۳-۱. ساخت حساب
1. [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) → **Start for free**.
2. **Home Region** را با دقت انتخاب کن (بعداً عوض نمی‌شود)؛ مثلاً **Germany Central (Frankfurt)**.
3. کارت بین‌المللی برای احراز هویت لازم است؛ در طرح Always Free چیزی کم نمی‌شود.

### ۳-۲. ساخت سرور (VM)
منو (☰) → **Compute → Instances → Create instance**:

| بخش | مقدار |
|---|---|
| Name | `lifeagent` |
| Image and shape → **Edit** → Image | **Change image → Ubuntu → Canonical Ubuntu 24.04** |
| Shape | **Change shape → Ampere → VM.Standard.A1.Flex**؛ OCPU = **2**، Memory = **12 GB** |
| Networking | پیش‌فرض بماند (Assign a public IPv4 address = بله) |
| Add SSH keys | **Generate a key pair for me** → **Save private key** (فایلی مثل `ssh-key-2026-10-05.key` دانلود می‌شود؛ نامش را `oracle.key` بگذار) |

**Create** را بزن. وقتی وضعیت **RUNNING** شد، **Public IP address** را کپی کن.

- اگر خطای **Out of capacity** گرفتی: در بخش Placement یک **Availability Domain** دیگر انتخاب کن، یا چند ساعت بعد دوباره امتحان کن.
- **جلوگیری از پس‌گرفته‌شدن سرور:** Oracle ممکن است VMهای Always Free را که ۷ روز خیلی کم‌مصرف بوده‌اند پس بگیرد (ربات ما بیشتر وقت بیکار است). راه مطمئن: **Billing → Upgrade to Pay As You Go**؛ تا داخل سهمیه Always Free بمانی هزینه‌ای ندارد.

**✔ نتیجه درست:** یک سرور RUNNING با Public IP.

### ۳-۳. وصل شدن به سرور (SSH)
فایل `oracle.key` را در یک پوشه (مثلاً `Downloads`) داشته باش و ترمینال را در همان پوشه باز کن.

**ویندوز (PowerShell):**
```powershell
cd $HOME\Downloads
icacls oracle.key /inheritance:r /grant:r "$($env:USERNAME):(R)"   # فقط بار اول؛ وگرنه خطای UNPROTECTED PRIVATE KEY
ssh -i oracle.key ubuntu@PUBLIC_IP
```
**مک / لینوکس:**
```bash
cd ~/Downloads
chmod 600 oracle.key
ssh -i oracle.key ubuntu@PUBLIC_IP
```
سؤال `Are you sure you want to continue connecting` → بنویس `yes`.

**✔ نتیجه درست:** خط فرمانی مثل `ubuntu@lifeagent:~$`.

### ۳-۴. گرفتن کد (روی سرور)
```bash
git clone https://github.com/Kyzen-dev/LifeAgent.git ~/lifeagent
```

### ۳-۵. فرستادن فایل‌های شخصی (روی کامپیوتر خودت، یک ترمینال دیگر)
در همان پوشه‌ای که `oracle.key`، `.env` و `profile.md` هستند:
```bash
scp -i oracle.key .env ubuntu@PUBLIC_IP:~/lifeagent/.env
scp -i oracle.key profile.md ubuntu@PUBLIC_IP:~/lifeagent/workspace/memory/profile.md
```
(اگر ویندوز فایل `.env` را به اسم `.env.txt` ذخیره کرده بود، با همین اسم بفرست و روی سرور `mv ~/lifeagent/.env.txt ~/lifeagent/.env` بزن.)

### ۳-۶. نصب و روشن کردن (روی سرور)
```bash
cd ~/lifeagent
bash deploy/setup-server.sh
```
اسکریپت به ترتیب:
1. اگر رم کم باشد swap می‌سازد.
2. Docker را نصب می‌کند.
3. چون کلیدها در `.env` خالی‌اند، **همان ویزارد بخش ۲** را باز می‌کند — این بار توکن **ربات اصلی** را بده و به **ربات اصلی** پیام بده.
4. image را می‌سازد (بار اول ۵ تا ۱۰ دقیقه) و ربات را روشن می‌کند.
5. در آخر چک سلامت را اجرا می‌کند.

**✔ نتیجه درست:** `Done.` در آخر و ✅ برای Telegram و Anthropic در خروجی doctor.

یک چک کامل‌تر (یک درخواست واقعی خیلی کوچک):
```bash
sudo docker compose run --rm lifeagent python -m lifeagent.doctor --live
```
ربات با `restart: unless-stopped` اجرا می‌شود: اگر سرور ری‌استارت شود یا ربات crash کند، خودش دوباره بالا می‌آید.

### ۳-۷. پشتیبان‌گیری خودکار روزانه
```bash
crontab -e      # اگر پرسید کدام ویرایشگر، 1 (nano) را بزن
```
این خط را آخر فایل اضافه کن، ذخیره کن (Ctrl+O، Enter، Ctrl+X):
```
0 4 * * * cd ~/lifeagent && bash deploy/backup.sh >> ~/lifeagent-backups/backup.log 2>&1
```
هر روز ساعت ۴ صبح (به وقت سرور) یک پشتیبان سازگار در `~/lifeagent-backups/` ساخته می‌شود و پشتیبان‌های قدیمی‌تر از ۱۴ روز پاک می‌شوند. همین حالا یک بار دستی تست کن: `bash deploy/backup.sh`.
ماهی یک بار پشتیبان‌ها را روی کامپیوتر خودت بیاور:
```bash
scp -i oracle.key "ubuntu@PUBLIC_IP:~/lifeagent-backups/*.tgz" .
```

### جایگزین: Google Cloud e2-micro
اگر Oracle جواب نداد: در Google Cloud یک VM **e2-micro** در `us-west1`، `us-central1` یا `us-east1` با دیسک **30 GB standard** و Ubuntu 24.04 بساز، با دکمه SSH کنسول وارد شو و از بخش **۳-۴** به بعد را همین‌طور انجام بده. اسکریپت خودش ۲ گیگ swap اضافه می‌کند؛ build کندتر است ولی کار می‌کند.

---

## ۴. اولین گفتگو

در تلگرام به ربات (تستی در Codespaces، اصلی روی سرور):
1. `/start` → راهنمای ربات می‌آید.
2. بنویس: **«سلام، بیا با هم آشنا بشیم»**
   دستیار بخش «راه‌اندازی اولیه» پروفایلت را اجرا می‌کند: عادت‌ها (نماز، مدیتیشن، ورزش، خواب، مطالعه، انگلیسی، کار عمیق)، اهداف، وزن اولیه — و چند سؤال می‌پرسد (اسمت، نرخ فعلی و هدف، پروژه‌ها، ساعت خواب، وضعیت حساب Upwork).
3. با حوصله جواب بده؛ هر چه دقیق‌تر بگویی، دستیار شخصی‌تر می‌شود.

**✔ نتیجه درست:** «عادت‌هام رو نشون بده» عادت‌های ساخته‌شده را نشان می‌دهد.

---

## ۵. چک‌لیست تست

هر مورد را بفرست و تیک بزن. اگر چیزی درست کار نکرد، خروجی لاگ را نگه دار (بخش ۷).

**پایه**
- [ ] از یک حساب تلگرام **دیگر** به ربات پیام بده → نباید جواب بدهد (امنیت).
- [ ] `/new` و بعد «من کی هستم و هدف‌هام چیه؟» → از پروفایل جواب می‌دهد.

**فریلنس و Upwork**
- [ ] «یه مشتری جدید: X، پروژه چت‌بات RAG، ساعتی ۱ میلیون» → ثبت مشتری و پروژه.
- [ ] «شروع کار روی چت‌بات» → چند دقیقه بعد «تموم کردم، retriever رو درست کردم» → ثبت زمان.
- [ ] «این هفته چند ساعت کار کردم؟» → گزارش ساعت و درآمد تقریبی.
- [ ] «پروفایل آپورکم رو از صفر بنویس» → Title، Overview، ایده portfolio.
- [ ] متن یک آگهی Upwork را بفرست → امتیاز تناسب + دو نسخه پروپوزال. بعد «فرستادمش، ۱۲ کانکت» → ثبت.
- [ ] «آمار پروپوزال‌های آپورک؟» → قیف تبدیل.

**مالی، سلامت، عادت‌ها**
- [ ] «۲۵۰ تومن ناهار» → ثبت هزینه. «این ماه چقدر خرج کردم؟» → خلاصه.
- [ ] عکس یک رسید یا پیامک بانکی → استخراج و ثبت.
- [ ] «وزنم ۶۰.۵ شد» → ثبت. «برنامه افزایش وزنم چیه؟» → کالری، پروتئین، تمرین.
- [ ] «امروز ۲۰ دقیقه مدیتیشن کردم» → ثبت عادت.

**یادآور و روال‌ها**
- [ ] «۲ دقیقه دیگه یادم بنداز آب بخورم» → سر وقت پیام با دکمه‌های «انجام شد/تعویق».
- [ ] «اوقات شرعی امروز؟» → زمان‌ها. یادآور اذان سر وقت با دکمه «خواندم».
- [ ] `/brief` → گزارش صبحگاهی همین الان. `/review` → بازبینی هفتگی.

**فایل‌ها**
- [ ] یک PDF بفرست → خلاصه. «خلاصه‌اش رو PDF کن» → دکمه تأیید → فایل PDF با فارسی درست.
- [ ] «هزینه‌های این ماه رو اکسل کن» → فایل xlsx.
- [ ] ویس فارسی و ویس انگلیسی (اگر کلید OpenAI داری) → متن درست و جواب.

**امنیت**
- [ ] یک کار که Bash لازم دارد (مثل ساخت PDF) → دکمه‌های «تأیید / رد / تأیید موارد مشابه تا ۳۰ دقیقه».
- [ ] `/cost` → هزینه تقریبی امروز.

**رشد AI**
- [ ] «تو LangGraph چطور human-in-the-loop بذارم؟» → جواب فنی با مستندات به‌روز.
- [ ] «خلاصه اخبار AI این هفته» → خبرها با لینک + ایده پست.
- [ ] «یه پست لینکدین درباره تجربه‌ام با RAG بنویس» → دو نسخه انگلیسی.

**روال‌های زمان‌دار** — برای تست بدون صبر کردن، روی سرور در `.env` مثلاً `MIDDAY_CHECKIN_TIME` را ۵ دقیقه بعد بگذار و `sudo docker compose up -d` بزن. (اگر پیگیری ظهر چیز مفیدی برای گفتن نداشته باشد پیامی نمی‌فرستد؛ این درست است.) بعد مقدار را برگردان.

---

## ۶. اتصال‌های اختیاری

### GitHub (خلاصه PRها، issueها و CI)
1. GitHub → Settings → Developer settings → **Personal access tokens → Fine-grained tokens → Generate new token**.
2. Repository access: ریپوهای مهمت. Permissions (Repository): **Contents, Issues, Pull requests, Actions, Metadata = Read-only**.
3. روی سرور: `cd ~/lifeagent && python3 deploy/configure.py` → در مرحله GitHub توکن را بده (بقیه را با Enter نگه دار) → `sudo docker compose up -d`.

### Google (Gmail، تقویم، Drive)
1. [console.cloud.google.com](https://console.cloud.google.com) → پروژه جدید.
2. **APIs & Services → Library** → Enable: Gmail API، Google Calendar API، Google Drive API، Google Tasks API، Google Docs API، Google Sheets API.
3. **OAuth consent screen**: External؛ ایمیل خودت در Test users؛ سپس **Publish app** (تا لاگین هر ۷ روز منقضی نشود).
4. **Credentials → Create credentials → OAuth client ID → Desktop app** → Client ID و Client secret.
5. روی سرور با `nano ~/lifeagent/.env` این‌ها را پر کن: `GOOGLE_OAUTH_CLIENT_ID`، `GOOGLE_OAUTH_CLIENT_SECRET`، `USER_GOOGLE_EMAIL` → `sudo docker compose up -d`.
6. **ورود یک‌باره:** روی کامپیوترت `ssh -i oracle.key -L 8000:localhost:8000 ubuntu@PUBLIC_IP` و این پنجره را باز نگه دار. در تلگرام بگو «ایمیل‌هامو چک کن»؛ لینکی که ربات می‌دهد را در مرورگر **همان کامپیوتر** باز کن و Allow بزن.
   اگر بعد از Allow صفحه وصل نشد: در `docker-compose.yml` بخش `ports` را موقتاً با `network_mode: host` عوض کن، `sudo docker compose up -d`، ورود را تکرار کن، و بعد برگردان.

---

## ۷. کارهای روزمره روی سرور

```bash
cd ~/lifeagent
sudo docker compose logs -f --tail 100      # لاگ زنده (خروج: Ctrl+C)
sudo docker compose ps                      # وضعیت (باید Up باشد)
sudo docker compose restart                 # ری‌استارت
bash deploy/setup-server.sh                 # به‌روزرسانی کد + build + ری‌استارت + چک سلامت
bash deploy/backup.sh                       # پشتیبان دستی
python3 deploy/configure.py                 # تغییر کلیدها (بعدش: sudo docker compose up -d)
nano .env                                   # تغییر تنظیمات (ساعت روال‌ها، مدل، …؛ بعدش: sudo docker compose up -d)
```

**بازگردانی از پشتیبان:**
```bash
cd ~/lifeagent && sudo docker compose down
mkdir -p /tmp/restore && tar xzf ~/lifeagent-backups/lifeagent-YYYY-MM-DD_HHMM.tgz -C /tmp/restore
cp /tmp/restore/lifeagent.sqlite3 data/ && rm -f data/lifeagent.sqlite3-wal data/lifeagent.sqlite3-shm
cp -r /tmp/restore/workspace/memory /tmp/restore/workspace/notes workspace/
sudo docker compose up -d
```

---

## ۸. کنترل هزینه

| ابزار | کار |
|---|---|
| سقف ماهانه در کنسول Anthropic | سقف قطعی خرج |
| `/cost` در تلگرام | هزینه تقریبی امروز و این ماه |
| `DAILY_BUDGET_USD` در `.env` | هشدار وقتی خرج روزانه از سقف رد شد |
| `LIFEAGENT_EFFORT=low` | ارزان‌تر و سریع‌تر (کمی کم‌دقت‌تر) |
| خالی گذاشتن روال‌ها (مثلاً `MIDDAY_CHECKIN_TIME=`) | حذف پیام‌های خودکار غیرضروری |
| `LIFEAGENT_MODEL=claude-opus-5-5` | بیشترین کیفیت (گران‌تر) — فقط اگر لازم شد |

---

## ۹. رفع اشکال

| پیام یا علامت | علت | راه‌حل |
|---|---|---|
| ربات اصلاً جواب نمی‌دهد | ربات خاموش است یا شناسه‌ات مجاز نیست | `sudo docker compose ps` و `logs`؛ `python3 deploy/configure.py --check` |
| `Conflict: terminated by other getUpdates request` | همین توکن جای دیگری هم روشن است | Codespace را Stop کن یا از ربات تستی جدا استفاده کن |
| `UNPROTECTED PRIVATE KEY FILE` (ویندوز) | دسترسی فایل کلید باز است | دستور `icacls` بخش ۳-۳ |
| `Permission denied (publickey)` | کلید یا کاربر اشتباه | کاربر `ubuntu` و همان فایل `oracle.key` |
| `Out of capacity` در Oracle | ظرفیت ARM پر است | Availability Domain دیگر یا چند ساعت بعد |
| `permission denied` روی `data/` | مالکیت فایل‌ها | `sudo chown -R $(id -u):$(id -g) data workspace && sudo docker compose up -d` |
| build روی سرور کوچک kill شد | کمبود رم | `free -h` (swap باید باشد)؛ اسکریپت را دوباره اجرا کن |
| doctor: `Anthropic: HTTP 401` | کلید اشتباه | `python3 deploy/configure.py` |
| doctor: `HTTP 400 ... credit balance` | اعتبار تمام شده | شارژ در Billing کنسول Anthropic |
| ربات جواب می‌دهد ولی «خطا: …» | خطای داخلی | `sudo docker compose logs --tail 200` را برای Claude بفرست |
| یادآور اذان نمی‌آید | `PRAYER_REMINDERS` خاموش یا API در دسترس نیست | `.env` را چک کن؛ doctor بخش prayer times؛ ربات هر ۳۰ دقیقه دوباره تلاش می‌کند |
| ویس کار نمی‌کند | کلید OpenAI ندارد/اشتباه است | `python3 deploy/configure.py` |

---

## پیوست: متغیرهای مهم `.env`

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | توکن ربات (الزامی) |
| `TELEGRAM_ALLOWED_USER_IDS` | — | شناسه‌های مجاز، با کاما (الزامی) |
| `ANTHROPIC_API_KEY` | — | کلید Anthropic (الزامی) |
| `LIFEAGENT_MODEL` / `LIFEAGENT_EFFORT` | `claude-sonnet-5-5` / `medium` | مدل و عمق فکر |
| `MORNING_BRIEF_TIME` / `MIDDAY_CHECKIN_TIME` / `EVENING_CHECKIN_TIME` | `08:00` / `14:00` / `23:00` | روال‌های روزانه (خالی = خاموش) |
| `WEEKLY_REVIEW` / `AI_DIGEST` | `fri 18:00` / `thu 10:00` | روال‌های هفتگی |
| `PRAYER_REMINDERS` / `PRAYER_CITY` / `PRAYER_TIMES` | `false` / `Tehran` / `fajr,dhuhr,maghrib` | یادآور اذان |
| `OPENAI_API_KEY` | — | ویس |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | — | GitHub |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` / `USER_GOOGLE_EMAIL` | — | Gmail/Calendar/Drive |
| `DAILY_BUDGET_USD` | — | هشدار هزینه روزانه |
| `TRUST_WINDOW_MINUTES` | `30` | مدت «تأیید موارد مشابه» |
