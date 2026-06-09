#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "╔══════════════════════════════════════╗"
echo "║        TisaBot Installer v2          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── پیش‌نیازها ────────────────────────────────────────────────
command -v docker  >/dev/null 2>&1 || error "Docker نصب نیست."
command -v git     >/dev/null 2>&1 || error "Git نصب نیست."
docker compose version >/dev/null 2>&1 || error "Docker Compose نصب نیست."

# ── مسیر نصب ─────────────────────────────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/opt/tisabot}"

if [ -d "$INSTALL_DIR/.git" ]; then
    warn "ریپو از قبل وجود دارد — git pull می‌زنم..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "کلون ریپو در $INSTALL_DIR ..."
    git clone https://github.com/moha100h/tisabot.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── ورودی‌های کاربر ───────────────────────────────────────────
ENV_FILE="$INSTALL_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    warn ".env از قبل وجود دارد. آپدیت می‌کنم فقط مقادیر خالی رو..."
    source "$ENV_FILE" 2>/dev/null || true
fi

if [ -z "${BOT_TOKEN:-}" ]; then
    read -rp "🤖 Bot Token: " BOT_TOKEN
    [ -z "$BOT_TOKEN" ] && error "Bot Token نمی‌تواند خالی باشد."
fi

if [ -z "${ADMIN_ID:-}" ]; then
    read -rp "👤 Admin Telegram ID: " ADMIN_ID
    [[ "$ADMIN_ID" =~ ^[0-9]+$ ]] || error "Admin ID باید عدد باشد."
fi

# ── رمز خودکار PostgreSQL ─────────────────────────────────────
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    POSTGRES_PASSWORD=$(tr -dc 'A-Za-z0-9!@#%^&*' </dev/urandom | head -c 24)
    info "رمز PostgreSQL خودکار ساخته شد."
fi

POSTGRES_DB="${POSTGRES_DB:-tisabot}"
POSTGRES_USER="${POSTGRES_USER:-tisa}"

# ── نوشتن .env ────────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
# ── اجباری ──────────────────────────────────────────────────
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}

# ── پایگاه داده ─────────────────────────────────────────────
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── مسیرها ──────────────────────────────────────────────────
MEDIA_DIR=/app/media
BACKUP_DIR=/app/backups
EOF

chmod 600 "$ENV_FILE"
info ".env نوشته شد."

# ── پاک کردن volume قدیمی اگر رمز عوض شده ──────────────────
OLD_PASS=$(docker inspect tisa_postgres 2>/dev/null \
    | python3 -c "import sys,json; e=json.load(sys.stdin)[0]['Config']['Env']; \
      print(next((x.split('=',1)[1] for x in e if x.startswith('POSTGRES_PASSWORD=')),'')" \
    2>/dev/null || true)

if [ -n "$OLD_PASS" ] && [ "$OLD_PASS" != "$POSTGRES_PASSWORD" ]; then
    warn "رمز PostgreSQL تغییر کرده — volume قدیمی پاک می‌شود (داده‌ها حذف می‌شوند)..."
    docker compose down -v 2>/dev/null || true
    info "Volume پاک شد."
fi

# ── بیلد و اجرا ───────────────────────────────────────────────
info "در حال بیلد..."
docker compose build --no-cache

info "در حال راه‌اندازی..."
docker compose up -d

# ── وضعیت ────────────────────────────────────────────────────
sleep 5
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose ps
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if docker compose ps | grep -q "tisa_bot.*Up"; then
    info "✅ بات با موفقیت راه‌اندازی شد!"
    echo ""
    echo "  📋 لاگ‌ها:  docker compose logs -f bot"
    echo "  🛑 توقف:    docker compose down"
    echo "  🔄 ری‌استارت: docker compose restart bot"
else
    error "بات بالا نیامد. لاگ‌ها را بررسی کنید: docker compose logs bot"
fi
