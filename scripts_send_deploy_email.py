import argparse
import json
import os
import sys
from pathlib import Path

import resend
from dotenv import load_dotenv

DEFAULT_SECRETS_FILE = "/var/lib/labs/secrets/resend.env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a deployment notification email via Resend")
    parser.add_argument("app_name", nargs="?", default="hello", help="App slug under app.nphilou.ch")
    parser.add_argument("--secrets-file", default=DEFAULT_SECRETS_FILE, help="Path to env file with RESEND_API_KEY")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    secrets_file = Path(args.secrets_file)
    if secrets_file.exists():
        load_dotenv(dotenv_path=secrets_file, override=False)

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print(
            "Missing RESEND_API_KEY. Set it in your environment or secrets file (replace re_xxxxxxxxx with your real API key).",
            file=sys.stderr,
        )
        return 1

    recipient = os.environ.get("DEPLOY_NOTIFY_TO")
    if not recipient:
        print("Missing DEPLOY_NOTIFY_TO. Set it in your environment or secrets file.", file=sys.stderr)
        return 1
    sender = os.environ.get("DEPLOY_NOTIFY_FROM", "onboarding@resend.dev")
    app_url = f"https://app.nphilou.ch/{args.app_name}"

    resend.api_key = api_key

    response = resend.Emails.send(
        {
            "from": sender,
            "to": recipient,
            "subject": f"✅ App deployed: {args.app_name}",
            "html": f"<p>Your app is live: <a href=\"{app_url}\">{app_url}</a></p>",
        }
    )

    print(json.dumps(response, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
