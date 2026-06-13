import argparse
from pathlib import Path

from dotenv import dotenv_values
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.ingestion.gmail import GMAIL_READONLY_SCOPE


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def build_flow(client_secrets: Path | None) -> InstalledAppFlow:
    if client_secrets is not None:
        return InstalledAppFlow.from_client_secrets_file(
            str(client_secrets),
            scopes=[GMAIL_READONLY_SCOPE],
        )

    env = dotenv_values(ENV_FILE)
    client_id = str(env.get("GMAIL_CLIENT_ID") or "")
    client_secret = str(env.get("GMAIL_CLIENT_SECRET") or "")
    if not client_id or not client_secret:
        raise SystemExit(
            "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in backend/.env, "
            "or pass --client-secrets path/to/client_secret.json."
        )
    return InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=[GMAIL_READONLY_SCOPE],
    )


def write_refresh_token(refresh_token: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    replacement = f"GMAIL_REFRESH_TOKEN={refresh_token}"
    for index, line in enumerate(lines):
        if line.startswith("GMAIL_REFRESH_TOKEN="):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one-time Gmail read-only OAuth consent."
    )
    parser.add_argument(
        "--client-secrets",
        type=Path,
        help="Downloaded Google Desktop App OAuth client JSON.",
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Replace GMAIL_REFRESH_TOKEN in backend/.env after verification.",
    )
    args = parser.parse_args()

    flow = build_flow(args.client_secrets)
    credentials = flow.run_local_server(
        host="localhost",
        port=args.port,
        access_type="offline",
        prompt="consent",
    )
    if not credentials.refresh_token:
        raise SystemExit(
            "Google did not return a refresh token. Revoke the app grant in "
            "your Google Account, then run this script again."
        )
    granted_scopes = set(
        credentials.granted_scopes or credentials.scopes or []
    )
    if GMAIL_READONLY_SCOPE not in granted_scopes:
        raise SystemExit(
            "The OAuth grant does not include gmail.readonly. Revoke the "
            "existing app grant in your Google Account and run this again."
        )
    unexpected_scopes = granted_scopes - {GMAIL_READONLY_SCOPE}
    if unexpected_scopes:
        raise SystemExit(
            "Google returned a broader OAuth grant than Pulse permits: "
            + ", ".join(sorted(unexpected_scopes))
            + ". Revoke the existing app grant at "
            "https://myaccount.google.com/permissions and run this again."
        )
    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
    service.users().getProfile(userId="me").execute()
    print("Verified Gmail read-only access.")
    if args.write_env:
        write_refresh_token(credentials.refresh_token)
        print("Updated GMAIL_REFRESH_TOKEN in backend/.env.")
    else:
        print("\nAdd this value to backend/.env:")
        print(f"GMAIL_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()
