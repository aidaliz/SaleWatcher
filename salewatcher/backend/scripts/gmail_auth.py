#!/usr/bin/env python
"""
CLI script to authenticate with Gmail API for local development.

This script starts a local server to handle the OAuth2 callback.
Run this once locally to generate the token file.

Usage:
    python scripts/gmail_auth.py
"""
import json
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email_ingest import GmailClient


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback on local server."""

    def do_GET(self):
        """Handle GET request (OAuth callback)."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if 'error' in params:
            error = params['error'][0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
            <html>
            <body>
                <h1>Authentication Failed</h1>
                <p>Error: {error}</p>
                <p>You can close this window.</p>
            </body>
            </html>
            """.encode())
            self.server.auth_code = None
            self.server.auth_error = error
            return

        if 'code' in params:
            code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write("""
            <html>
            <body>
                <h1>Authentication Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """.encode())
            self.server.auth_code = code
            self.server.auth_error = None
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write("""
            <html>
            <body>
                <h1>Invalid Request</h1>
                <p>No authorization code received.</p>
            </body>
            </html>
            """.encode())
            self.server.auth_code = None
            self.server.auth_error = "No code received"

    def log_message(self, format, *args):
        """Suppress HTTP logging."""
        pass


def main():
    print("Gmail API Authentication (Local Development)")
    print("=" * 50)
    print()

    # Check for required environment variables
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("ERROR: Gmail OAuth credentials not configured!")
        print()
        print("Please set the following environment variables:")
        print("  GMAIL_CLIENT_ID=your-client-id")
        print("  GMAIL_CLIENT_SECRET=your-client-secret")
        print()
        print("To get these credentials:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project or select existing one")
        print("3. Enable the Gmail API")
        print("4. Go to Credentials → Create Credentials → OAuth client ID")
        print("5. Select 'Web application' as application type")
        print("6. Add 'http://localhost:8080/callback' as authorized redirect URI")
        print("7. Copy the Client ID and Client Secret")
        print()
        return 1

    # Use localhost callback for CLI authentication
    redirect_uri = "http://localhost:8080/callback"

    print(f"Client ID: {client_id[:20]}...")
    print(f"Redirect URI: {redirect_uri}")
    print()

    # Create client with local redirect URI
    client = GmailClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    # Start local server for callback
    server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
    server.auth_code = None
    server.auth_error = None

    # Get authorization URL
    auth_url = client.get_auth_url(state="local_auth")

    print("Opening browser for authentication...")
    print()
    print("If browser doesn't open, visit this URL:")
    print(auth_url)
    print()

    # Open browser
    webbrowser.open(auth_url)

    print("Waiting for authentication...")

    # Wait for callback
    while server.auth_code is None and server.auth_error is None:
        server.handle_request()

    if server.auth_error:
        print()
        print(f"FAILED: Authentication error: {server.auth_error}")
        return 1

    print("Received authorization code, exchanging for tokens...")

    try:
        # Exchange code for tokens
        token_data = client.exchange_code(server.auth_code)

        # Save token to file
        token_path = Path("gmail_token.json")
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)

        print()
        print("SUCCESS! Gmail authentication complete.")
        print(f"Token saved to {token_path}")
        print()

        # Verify authentication works
        if client.authenticate_with_token(token_data):
            print("Token verified successfully!")
            print()
            print("You can now sync emails using:")
            print("  python scripts/sync_emails.py --brand gamestop")
            print()
            print("For web deployment, set GMAIL_TOKEN_JSON environment variable:")
            print(f"  export GMAIL_TOKEN_JSON='{json.dumps(token_data)}'")
            return 0
        else:
            print("WARNING: Token saved but verification failed.")
            return 1

    except Exception as e:
        print()
        print(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
