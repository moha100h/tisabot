#!/bin/bash
set -e

INSTALL_DIR="/opt/tisabot"
REPO_URL="https://github.com/moha100h/tisabot.git"

echo ""
echo "  TisaBot — نصب"
echo ""

[ $EUID -ne 0 ] && echo "با root اجرا کنید: sudo bash install.sh" && exit 1

# ── Docker ────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[*] نصب Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker --quiet
    systemctl start docker
fi
if ! docker compose version &>/dev/null 2>&1; then
    apt-get install -y docker-compose-plugin -qq 2>/dev/null || true
fi

# ── سورس کد ──────────────────────────────────────────────────
IS_UPDATE=0
if [ -d "$INSTALL_DIR/.git" ]; then
    IS_UPDATE=1
    echo "[*] آپدیت..."
    cd "$INSTALL_DIR"
    git fetch origin --quiet
    git reset --hard origin/main --quiet
else
    echo "[*] دانلود..."
    git clone "$REPO_URL" "$INSTALL_DIR" --quiet
fi
cd "$INSTALL_DIR"

# ── تنظیم .env ────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env

    echo ""
    while true; do
        printf "BOT_TOKEN (از @BotFather): "
        read -r BOT_TOKEN
        [ -n "$BOT_TOKEN" ] && break
        echo "خالی نباشد"
    done

    while true; do
        printf "ADMIN_ID (آیدی عددی تلگرام): "
        read -r ADMIN_ID
        [[ "$ADMIN_ID" =~ ^[0-9]+$ ]] && break
        echo "باید عدد باشد"
    done

    PG_PASS=$(openssl rand -hex 24)
    sed -i "s|your_bot_token_here|${BOT_TOKEN}|"   .env
    sed -i "s|your_telegram_admin_id|${ADMIN_ID}|" .env
    sed -i "s|CHANGE_BY_INSTALLER|${PG_PASS}|"     .env
    echo ""
    echo "[✓] .env ذخیره شد"
fi

# ── Build و اجرا ──────────────────────────────────────────────
docker compose down --remove-orphans 2>/dev/null || true
[ "$IS_UPDATE" -eq 0 ] && docker compose down -v 2>/dev/null || true

echo "[*] Build..."
docker compose build --no-cache bot

echo "[*] راه‌اندازی..."
docker compose up -d

echo "[*] صبر برای دیتابیس..."
for i in $(seq 1 30); do
    docker compose exec -T postgres pg_isready -U tisa -d tisabot &>/dev/null && break
    sleep 2
done

sleep 3
echo ""
docker compose ps
echo ""
echo "[*] لاگ بات:"
docker compose logs bot --tail=10
echo ""
echo "  ✅ نصب تمام شد"
echo "  لاگ زنده: docker compose -f $INSTALL_DIR/docker-compose.yml logs -f bot"
echo ""
