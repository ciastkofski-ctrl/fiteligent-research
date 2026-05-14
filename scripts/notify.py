from __future__ import annotations
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_email(
    subject: str,
    html_body: str,
    plain_fallback: str | None = None,
    attachments: list[Path] | None = None,
    logo_path: Path | None = None,
) -> None:
    """Send the digest email via SMTP using env vars.

    Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO
    """
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    sender = os.environ["SMTP_FROM"]
    recipient = os.environ["SMTP_TO"]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    if plain_fallback:
        msg.set_content(plain_fallback)
    else:
        msg.set_content("This email requires an HTML-capable client.")

    msg.add_alternative(html_body, subtype="html")

    # Inline the logo as a CID-referenced attachment if requested
    if logo_path and logo_path.exists():
        with open(logo_path, "rb") as f:
            # Find the HTML alternative and attach the inline image to it
            for part in msg.iter_parts():
                if part.get_content_subtype() == "html":
                    part.add_related(
                        f.read(),
                        maintype="image",
                        subtype="svg+xml",
                        cid="logo",
                        filename=logo_path.name,
                    )
                    break

    for att in attachments or []:
        with open(att, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=att.name,
            )

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def send_failure_alert(stage: str, error: str, run_date_iso: str) -> None:
    """Lightweight plain-text alert for run failures. Falls back to stderr if SMTP misconfigured."""
    try:
        send_email(
            subject=f"[Fiteligent Research] FAILED {run_date_iso}",
            html_body=f"<pre>{error}</pre>",
            plain_fallback=f"Stage: {stage}\n\n{error}",
        )
    except Exception as alert_err:
        import sys
        sys.stderr.write(
            f"[notify] FAILED to send failure alert ({alert_err}). "
            f"Original failure (stage={stage}, run_date={run_date_iso}):\n{error}\n"
        )
