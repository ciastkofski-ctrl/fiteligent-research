"""One-off SMTP smoke test.

Sends an email using the existing dry-run output. Does NOT touch git or
seen.json. Use to verify Gmail SMTP credentials before running a real
digest send.

Usage:
    python scripts/test_email.py [dry_run_date]

If dry_run_date is omitted, uses the most recent dry-run output.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from scripts.notify import send_email


def main() -> int:
    dry_root = REPO_ROOT / "digests" / "_dry"
    if not dry_root.exists():
        print("No digests/_dry/ directory found — run a dry-run first.")
        return 1

    if len(sys.argv) > 1:
        run_dir = dry_root / sys.argv[1]
    else:
        runs = sorted(d for d in dry_root.iterdir() if d.is_dir())
        if not runs:
            print("No dry-run output found in digests/_dry/.")
            return 1
        run_dir = runs[-1]

    print(f"Using dry-run output from: {run_dir.name}")

    email_body = run_dir / "email_body.html"
    digest_md = run_dir / "digest.md"
    angles_md = run_dir / "angles.md"

    if not email_body.exists():
        print(f"Missing {email_body}. Re-run dry-run with rendering enabled.")
        return 1

    send_email(
        subject=f"[TEST] Fiteligent Research SMTP smoke test ({run_dir.name})",
        html_body=email_body.read_text(encoding="utf-8"),
        attachments=[digest_md, angles_md],
        logo_path=REPO_ROOT / "brand" / "logo.svg",
    )
    print("Email submitted to SMTP. Check the inbox for SMTP_TO.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
