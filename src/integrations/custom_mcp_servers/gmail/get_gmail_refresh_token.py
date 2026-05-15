"""Helper script to generate a Gmail OAuth2 refresh token.

Usage:
    1. Go to Google Cloud Console → APIs & Services → Credentials
    2. Download your OAuth client credentials JSON (rename to client_secret.json)
    3. Run: python get_gmail_refresh_token.py
    4. The script opens a browser for authorization
    5. Copy the refresh_token, client_id, and client_secret into the web form

Requirements:
    pip install google-auth-oauthlib
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    # Check for client_secret.json
    creds_path = "client_secret.json"
    if not os.path.exists(creds_path):
        print("❌ Error: client_secret.json not found in current directory.")
        print()
        print("How to get it:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Click 'Create Credentials' → 'OAuth client ID'")
        print("  3. Choose 'Desktop app' as application type")
        print("  4. Click 'Create', then click 'DOWNLOAD JSON'")
        print("  5. Rename the downloaded file to 'client_secret.json'")
        print("  6. Place it in this directory and run again")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ Error: google-auth-oauthlib is not installed.")
        print("Run: pip install google-auth-oauthlib")
        sys.exit(1)

    # Read client credentials to show client_id and client_secret
    with open(creds_path, "r", encoding="utf-8") as f:
        client_config = json.load(f)

    client_id = client_config["installed"]["client_id"]
    client_secret = client_config["installed"]["client_secret"]

    print("=" * 60)
    print("Gmail OAuth2 Refresh Token Generator")
    print("=" * 60)
    print()
    print(f"Client ID:     {client_id}")
    print(f"Client Secret: {client_secret[:10]}...")
    print()
    print("A browser window will open for authorization.")
    print("Please log in with the Gmail account you want to use.")
    print()

    # Run OAuth flow
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes=SCOPES)
    creds = flow.run_local_server(port=0)

    refresh_token = creds.refresh_token

    print()
    print("=" * 60)
    print("✅ SUCCESS! Copy these values into the web form:")
    print("=" * 60)
    print()
    print(f"GMAIL_REFRESH_TOKEN: {refresh_token}")
    print(f"GMAIL_CLIENT_ID:     {client_id}")
    print(f"GMAIL_CLIENT_SECRET: {client_secret}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
