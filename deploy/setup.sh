#!/usr/bin/env bash
# deploy/setup.sh — One-shot production setup for Ubuntu 22.04+
# Usage: sudo bash deploy/setup.sh

set -euo pipefail

APP_DIR="/opt/arthaai"
APP_USER="arthaai"
LOG_DIR="/var/log/arthaai"
PYTHON="python3.11"

echo "============================================"
echo " ArthAI — Production Setup"
echo "============================================"

# ── System packages ────────────────────────────────────────────────────────
echo "[1/8] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev \
    gcc g++ libgomp1 nginx certbot python3-certbot-nginx \
    sqlite3 curl git logrotate

# ── App user ───────────────────────────────────────────────────────────────
echo "[2/8] Creating app user..."
id -u $APP_USER &>/dev/null || useradd -m -s /bin/bash -d $APP_DIR $APP_USER

# ── App directory ──────────────────────────────────────────────────────────
echo "[3/8] Setting up application directory..."
mkdir -p $APP_DIR $LOG_DIR
cp -r . $APP_DIR/
chown -R $APP_USER:$APP_USER $APP_DIR $LOG_DIR

# ── Virtual environment ────────────────────────────────────────────────────
echo "[4/8] Creating Python virtual environment..."
sudo -u $APP_USER bash -c "
    cd $APP_DIR
    $PYTHON -m venv venv
    venv/bin/pip install --quiet --upgrade pip
    venv/bin/pip install --quiet -r requirements.txt
    venv/bin/pip install --quiet -r requirements-dashboard.txt
"

# ── Environment file ───────────────────────────────────────────────────────
echo "[5/8] Setting up .env file..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo "⚠️  Edit $APP_DIR/.env and add your API keys before starting!"
fi

# ── Streamlit config ───────────────────────────────────────────────────────
echo "[6/8] Configuring Streamlit..."
mkdir -p "$APP_DIR/.streamlit"
cp "$APP_DIR/.streamlit/config.toml" "$APP_DIR/.streamlit/config.toml" 2>/dev/null || true

# ── Systemd services ───────────────────────────────────────────────────────
echo "[7/8] Installing systemd services..."
cp "$APP_DIR/deploy/arthaai-dashboard.service" /etc/systemd/system/
cp "$APP_DIR/deploy/arthaai-agents.service"    /etc/systemd/system/
systemctl daemon-reload
systemctl enable arthaai-dashboard

# ── Log rotation ───────────────────────────────────────────────────────────
cat > /etc/logrotate.d/arthaai <<'EOF'
/var/log/arthaai/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl reload arthaai-dashboard >/dev/null 2>&1 || true
    endscript
}
EOF

# ── Nginx ──────────────────────────────────────────────────────────────────
echo "[8/8] Configuring Nginx..."
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/arthaai.conf
nginx -t && systemctl reload nginx || echo "⚠️  Fix nginx config and reload manually"

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo " Setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit $APP_DIR/.env — add your API keys"
echo "  2. sudo systemctl start arthaai-dashboard"
echo "  3. Open http://your-server-ip:8501"
echo "  4. (Optional) sudo systemctl start arthaai-agents"
echo ""
echo "Logs: journalctl -fu arthaai-dashboard"
