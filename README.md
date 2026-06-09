# TisaBot — ربات مدیریت املاک

## نصب

```bash
git clone https://github.com/moha100h/tisabot.git /opt/tisabot
cd /opt/tisabot
bash install.sh
```

اسکریپت دو چیز می‌پرسد:
- `BOT_TOKEN` — از [@BotFather](https://t.me/BotFather)
- `ADMIN_ID` — آیدی عددی تلگرام (از [@userinfobot](https://t.me/userinfobot))

بقیه تنظیمات از داخل ربات → `/admin` → **⚙️ تنظیمات**

---

## دستورات مفید

```bash
# لاگ زنده
docker compose -f /opt/tisabot/docker-compose.yml logs -f bot

# ری‌استارت
docker compose -f /opt/tisabot/docker-compose.yml restart bot

# وضعیت
docker compose -f /opt/tisabot/docker-compose.yml ps

# آپدیت
cd /opt/tisabot && bash install.sh
```

---

## تنظیمات از پنل ادمین

بعد از نصب، `/admin` بزن → **⚙️ تنظیمات**:

| کلید | توضیح |
|------|-------|
| `review_group_id` | آیدی گروه بازبینی آگهی‌ها |
| `backup_group_id` | آیدی گروه دریافت بکاپ |
| `contact_info` | متن تماس با ما |
| `about_us` | متن درباره ما |
