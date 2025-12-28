#!/usr/bin/env python
"""
CLI script to authenticate with Gmail API.

This script opens a browser window for OAuth2 authentication.
Run this once locally to generate the token file.

Usage:
    python scripts/gmail_auth.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email_ingest import GmailClient


def main():
    print("Gmail API Authentication")
    print("=" * 40)
    print()
    print("This will open a browser window to authenticate with your Gmail account.")
    print("Make sure you have gmail_credentials.json in the backend directory.")
    print()

    # Check for credentials file
    creds_path = Path("gmail_credentials.json")
    if not creds_path.exists():
        print("ERROR: gmail_credentials.json not found!")
        print()
        print("To get this file:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project or select existing one")
        print("3. Enable the Gmail API")
        print("4. Go to Credentials → Create Credentials → OAuth client ID")
        print("5. Select 'Desktop app' as application type")
        print("6. Download the JSON and save as gmail_credentials.json")
        print()
        return 1

    print("Found gmail_credentials.json")
    print()

    # Authenticate
    client = GmailClient(
        credentials_path="gmail_credentials.json",
        token_path="gmail_token.json",
    )

    print("Opening browser for authentication...")
    print()

    if client.authenticate():
        print()
        print("SUCCESS! Gmail authentication complete.")
        print("Token saved to gmail_token.json")
        print()
        print("You can now sync emails using:")
        print("  - Dashboard: Go to Settings → Email Sync")
        print("  - CLI: python scripts/sync_emails.py --brand gamestop")
        return 0
    else:
        print()
        print("FAILED: Gmail authentication failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
