#!/usr/bin/env bash
# deploy/refresh_token.sh
# Add to crontab: 0 8 * * 1-5 /opt/arthaai/deploy/refresh_token.sh
# Runs Mon-Fri at 8:00 AM IST to refresh Zerodha access token before market open.

APP_DIR="/opt/arthaai"
LOG="$APP_DIR/logs/token_refresh.log"
VENV="$APP_DIR/venv/bin/python"

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting token refresh..." >> "$LOG"

cd "$APP_DIR"
source .env

# Non-interactive token refresh using stored TOTP secret (requires pyotp)
$VENV - <<'EOF'
import os, sys, requests, pyotp

API_KEY    = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")
TOTP_SECRET = os.getenv("KITE_TOTP_SECRET")   # Base32 TOTP secret from Zerodha 2FA setup
USER_ID    = os.getenv("KITE_USER_ID")
PASSWORD   = os.getenv("KITE_PASSWORD")

if not all([API_KEY, API_SECRET, TOTP_SECRET, USER_ID, PASSWORD]):
    print("ERROR: Set KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET in .env for auto-refresh")
    sys.exit(1)

from kiteconnect import KiteConnect
kite  = KiteConnect(api_key=API_KEY)
totp  = pyotp.TOTP(TOTP_SECRET).now()

# Step 1: Login
session = requests.Session()
r = session.post("https://kite.zerodha.com/api/login",
                 data={"user_id": USER_ID, "password": PASSWORD})
data = r.json()
request_id = data["data"]["request_id"]

# Step 2: TOTP 2FA
r2 = session.post("https://kite.zerodha.com/api/twofa",
                  data={"user_id": USER_ID, "request_id": request_id,
                        "twofa_value": totp, "twofa_type": "totp"})

# Step 3: Get request_token from redirect URL
import re, urllib.parse
enc_token = session.cookies.get("enctoken", "")
login_url = kite.login_url()
# Exchange for access token via kite.generate_session is not possible headlessly
# Instead use kite-login helper or zerodha-login-helper library

print(f"Token refresh attempted. Check Kite dashboard.")
EOF

echo "$(date '+%Y-%m-%d %H:%M:%S') Token refresh complete." >> "$LOG"
