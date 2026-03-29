"""
utils/auth.py — Zerodha Kite Connect daily authentication
Run this script every morning before market open to get a fresh access_token.

Usage:
  python utils/auth.py
"""

import os
import webbrowser
from dotenv import load_dotenv, set_key
load_dotenv(override=True)

try:
    from kiteconnect import KiteConnect
except ImportError:
    print("kiteconnect not installed. Run: pip install kiteconnect")
    exit(1)


def authenticate():
    api_key    = os.getenv("KITE_API_KEY")
    api_secret = os.getenv("KITE_API_SECRET")

    if not api_key or not api_secret:
        print("ERROR: KITE_API_KEY and KITE_API_SECRET must be set in .env")
        exit(1)

    kite      = KiteConnect(api_key=api_key)
    login_url = kite.login_url()

    print(f"\n{'='*60}")
    print("ArthAI — Zerodha Authentication")
    print(f"{'='*60}")
    print(f"\n1. Opening Zerodha login in browser...")
    print(f"   URL: {login_url}\n")
    webbrowser.open(login_url)

    print("2. Log in with your Zerodha credentials")
    print("3. After login, you'll be redirected to a URL like:")
    print("   https://your-redirect-url?request_token=xxxxxxxx&action=login\n")

    request_token = input("4. Paste the request_token from the URL: ").strip()

    try:
        data         = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]

        # Save to .env
        set_key(".env", "KITE_ACCESS_TOKEN", access_token)
        print(f"\n✅ Access token saved to .env")
        print(f"   Token: {access_token[:20]}...")
        print(f"\nArthAI is ready to trade. Run: python main.py")

    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        exit(1)


if __name__ == "__main__":
    authenticate()
