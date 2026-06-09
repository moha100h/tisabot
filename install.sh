#!/bin/bash
# ============================================================
# TisaBot — Real Estate Telegram Bot  |  install.sh v2.0
# ============================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step()    { echo -e "\n${CYAN}${BOLD}══════════════════════════════════════${NC}"; \
            echo -e "${CYAN}${BOLD}  $1${NC}"; \
            echo -e "${CYAN}${BOLD}══════════════════════════════════════${NC}"; }

INSTALL_DIR="/opt/tisabot"
REPO_URL="https://github.com/moha100h/tisabot.git"

echo -e "\n${CYAN}${BOLD}  TisaBot — ربات مدیریت املاک${NC}\n"

[[ $EUID -ne 0 ]] && error "با root اجرا کنید: sudo bash install.sh"

# ── 1. پیش‌نیازها ─────────────────────────────────────────────
step "1/5 — پیش‌نیازها"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
for pkg in curl git ca-certificates gnupg openssl; do
    command -v "$pkg" &>/dev/null || apt-get install -y "$pkg" -qq
done
success "پیش‌نیازها OK"

# ── 2. Docker ─────────────────────────────────────────────────
step "2/5 — Docker"
if ! command -v docker &>/dev/null; then
    info "نصب Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker --quiet
    systemctl start docker
fi
if ! docker compose version &>/dev/null 2>&1; then
    apt-get install -y docker-compose-plugin -qq 2>/dev/null || true
fi
success "Docker: $(docker --version)"

# ── 3. سورس کد ────────────────────────────────────────────────
step "3/5 — سورس کد"
IS_UPDATE=0
if [ -d "$INSTALL_DIR/.git" ]; then
    IS_UPDATE=1
    cd "$INSTALL_DIR"
    git fetch origin --quiet
    git reset --hard origin/main --quiet
    success "آپدیت شد"
else
    git clone "$REPO_URL" "$INSTALL_DIR" --quiet
    success "Clone شد"
fi
cd "$INSTALL_DIR"

# ── 4. تنظیم .env ─────────────────────────────────────────────
step "4/5 — تنظیم .env"
if [ ! -f ".env" ]; then
    cp .env.example .env

    echo ""
    echo -e "${YELLOW}  فقط دو مورد زیر لازم است:${NC}"
    echo ""

    # خواندن BOT_TOKEN از /dev/tty (نه stdin)
    while true; do
        printf "  🤖 BOT_TOKEN (از @BotFather): "
        read BOT_TOKEN < /dev/tty
        [[ -n "$BOT_TOKEN" ]] && break
        warn "BOT_TOKEN نمی‌تواند خالی باشد"
    done

    while true; do
        printf "  👤 ADMIN_ID (آیدی عددی تلگرام): "
        read ADMIN_ID < /dev/tty
        [[ "$ADMIN_ID" =~ ^[0-9]+$ ]] && break
        warn "ADMIN_ID باید عدد باشد (مثال: 123456789)"
    done

    PG_PASS=$(openssl rand -hex 24)

    sed -i "s|your_bot_token_here|${BOT_TOKEN}|"       .env
    sed -i "s|your_telegram_admin_id|${ADMIN_ID}|"     .env
    sed -i "s|CHANGE_BY_INSTALLER|${PG_PASS}|"         .env

    success ".env تنظیم شد"
else
    warn ".env موجود است — تغییر نمی‌دهیم"
fi

# ── 5. Build و راه‌اندازی ─────────────────────────────────────
step "5/5 — Build و راه‌اندازی"
docker compose down --remove-orphans 2>/dev/null || true
[ "$IS_UPDATE" -eq 0 ] && docker compose down -v 2>/dev/null || true

info "Build image..."
docker compose build --no-cache bot

info "راه‌اندازی سرویس‌ها..."
docker compose up -d

info "صبر برای PostgreSQL..."
RETRIES=0
until docker compose exec -T postgres pg_isready -U tisa -d tisabot &>/dev/null; do
    RETRIES=$((RETRIES+1))
    [ $RETRIES -ge 30 ] && error "PostgreSQL راه‌اندازی نشد"
    sleep 2
done
success "PostgreSQL آماده"

sleep 4
echo ""
docker compose ps
echo ""
info "لاگ‌های بات:"
docker compose logs bot --tail=15 2>&1 || true

echo -e "\n${GREEN}${BOLD}  ✅ نصب با موفقیت انجام شد!${NC}\n"
echo -e "  ${BOLD}docker compose logs -f bot${NC}   # لاگ زنده"
echo -e "  ${BOLD}docker compose restart bot${NC}   # ری‌استارت"
echo -e "  ${BOLD}bash $0${NC}                      # آپدیت"
echo ""
