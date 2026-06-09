# 🏠 TisaBot — ربات مدیریت املاک

ربات تلگرامی حرفه‌ای برای آژانس‌های املاک — ثبت آگهی، جستجو، بازبینی گروهی، پنل مدیریت کامل.

**Stack:** Python 3.11 · aiogram 3.x · PostgreSQL 15 · Redis 7 · Docker

---

## ⚡️ نصب سریع (یک دستور)

```bash
curl -fsSL https://raw.githubusercontent.com/moha100h/tisabot/main/install.sh | bash
```

فقط دو چیز می‌پرسد:
- `BOT_TOKEN` — از [@BotFather](https://t.me/BotFather)
- `ADMIN_ID` — آیدی عددی تلگرام شما (از [@userinfobot](https://t.me/userinfobot))

بقیه تنظیمات از داخل پنل مدیریت ربات قابل تغییر است.

---

## 📋 پیش‌نیازها

| مورد | نسخه |
|------|------|
| Ubuntu/Debian | 20.04 / 22.04 / 24.04 / Debian 11-12 |
| RAM | حداقل 512 MB |
| Disk | حداقل 2 GB |
| Docker | نصب خودکار توسط install.sh |

---

## 🔧 نصب دستی

```bash
# 1. Clone
git clone https://github.com/moha100h/tisabot.git
cd tisabot

# 2. تنظیم .env
cp .env.example .env
nano .env   # فقط BOT_TOKEN و ADMIN_ID را پر کنید

# 3. Build و راه‌اندازی
docker compose build --no-cache bot
docker compose up -d

# 4. مشاهده لاگ
docker compose logs -f bot
```

---

## ⚙️ تنظیمات از پنل مدیریت

پس از راه‌اندازی، با `/admin` وارد پنل شوید → **⚙️ تنظیمات**:

| کلید | توضیح | مثال |
|------|-------|------|
| `review_group_id` | آیدی گروه بازبینی آگهی‌ها | `-1001234567890` |
| `backup_group_id` | آیدی گروه دریافت بکاپ | `-1001234567890` |
| `backup_interval_hours` | فاصله بکاپ خودکار (ساعت) | `6` |
| `contact_info` | متن تماس با ما | `📞 021-12345678` |
| `about_us` | متن درباره ما | `آژانس تیسا...` |
| `rules` | قوانین ثبت آگهی | `...` |
| `max_listing_images` | حداکثر تصویر هر آگهی | `3` |
| `max_image_size_mb` | حداکثر حجم تصویر (MB) | `5` |
| `max_listings_per_user` | حداکثر آگهی هر کاربر | `10` |

> **نکته:** برای دریافت آیدی گروه، ربات را به گروه اضافه کنید و یک پیام ارسال کنید.
> سپس از [@userinfobot](https://t.me/userinfobot) آیدی گروه را بگیرید.

---

## 👥 نقش‌ها

| نقش | دسترسی |
|-----|--------|
| `user` | ثبت آگهی، جستجو، مشاهده |
| `admin` | پنل مدیریت، تأیید/رد آگهی، مدیریت کاربران |
| `super` | همه موارد + افزودن ادمین جدید |

**افزودن ادمین:** پنل مدیریت → 👥 مدیریت کاربران → 👑 افزودن ادمین

---

## 🔄 آپدیت

```bash
cd /opt/tisabot
bash install.sh
```

اسکریپت به‌صورت خودکار تشخیص می‌دهد که نصب قبلی وجود دارد و فقط آپدیت می‌کند.

---

## 💾 بکاپ و ریستور

**بکاپ دستی:** پنل مدیریت → 💾 بکاپ

**بکاپ خودکار:** هر N ساعت (قابل تنظیم از پنل) — فایل tar.gz شامل:
- dump کامل PostgreSQL
- پوشه media (تصاویر آگهی‌ها)

**ریستور:**
```bash
# کپی فایل بکاپ به سرور
scp backup_YYYYMMDD_HHMMSS.tar.gz user@server:/opt/tisabot/

# استخراج
cd /opt/tisabot
tar -xzf backup_YYYYMMDD_HHMMSS.tar.gz

# ریستور دیتابیس
docker compose exec -T postgres psql -U tisa -d tisabot < db_YYYYMMDD_HHMMSS.sql
```

---

## 🐛 عیب‌یابی

```bash
# مشاهده لاگ زنده
docker compose logs -f bot

# وضعیت سرویس‌ها
docker compose ps

# ری‌استارت
docker compose restart bot

# ری‌استارت کامل
docker compose down && docker compose up -d

# بررسی اتصال دیتابیس
docker compose exec postgres pg_isready -U tisa -d tisabot
```

**مشکل رایج:** اگر بات بالا نمی‌آید:
1. `docker compose logs bot` را بررسی کنید
2. مطمئن شوید `BOT_TOKEN` و `ADMIN_ID` در `.env` درست است
3. مطمئن شوید پورت‌های 5432 و 6379 آزاد هستند

---

## 📁 ساختار پروژه

```
tisabot/
├── install.sh              # نصب/آپدیت خودکار
├── docker-compose.yml
├── .env.example
└── bot/
    ├── main.py             # نقطه ورود
    ├── config.py           # تنظیمات env
    ├── Dockerfile
    ├── requirements.txt
    ├── db/
    │   ├── database.py     # SQLAlchemy async engine
    │   ├── models.py       # مدل‌های دیتابیس
    │   └── repository.py   # CRUD operations
    ├── handlers/
    │   ├── register.py     # FSM ثبت‌نام
    │   ├── user.py         # داشبورد کاربر
    │   ├── listing.py      # ویزارد ثبت آگهی
    │   ├── search.py       # جستجوی ملک
    │   ├── admin.py        # پنل مدیریت
    │   └── backup.py       # بکاپ دستی
    ├── keyboards/
    │   └── main.py         # کیبوردها
    ├── middlewares/
    │   └── auth.py         # احراز هویت
    └── services/
        └── backup_service.py  # بکاپ زمان‌بندی‌شده
```

---

## 📄 لایسنس

MIT License — آزاد برای استفاده تجاری و شخصی.
