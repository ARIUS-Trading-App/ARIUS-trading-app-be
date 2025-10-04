import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from jose import jwt
from datetime import datetime, timedelta

from app.core.config import settings

SENDGRID_API_KEY = settings.SENDGRID_API_KEY
EMAIL_SENDER = settings.EMAIL_SENDER
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
FRONTEND_BASE_URL = settings.FRONTEND_BASE_URL

def create_magic_token(email: str) -> str:
    """Creates a JWT token for a passwordless "magic link" login.

    Args:
        email (str): The user's email address to be encoded in the token.

    Returns:
        str: The generated JSON Web Token.
    """
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def send_email_link(recipient: str, token: str):
    """Sends a visually rich magic login email via SendGrid in ARIUS style."""
    base_url = FRONTEND_BASE_URL.rstrip('/')
    login_url = f"{base_url}/profile/login/magic-link?token={token}"

    # Styled HTML email (dark, neon accents, safe for most clients with inline CSS)
    html = f"""
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>ARIUS Magic Link</title>
  </head>
  <body style=\"margin:0; padding:0; background-color:#0B1220; color:#E5E7EB; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', Arial, 'Noto Sans', 'Apple Color Emoji','Segoe UI Emoji','Segoe UI Symbol', sans-serif;\">
    <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"background:#0B1220;\">
      <tr>
        <td align=\"center\" style=\"padding:32px 16px;\">
          <table role=\"presentation\" width=\"600\" cellspacing=\"0\" cellpadding=\"0\" style=\"max-width:600px; width:100%; background:linear-gradient(180deg, rgba(15,23,42,0.95), rgba(15,23,42,0.9)); border:1px solid rgba(99,102,241,0.25); border-radius:16px; overflow:hidden; box-shadow:0 0 30px rgba(0,240,255,0.12);\">
            <tr>
              <td style=\"padding:28px 24px; background:radial-gradient(1200px 300px at 10% -20%, rgba(0,240,255,0.18), transparent), radial-gradient(1000px 300px at 100% 0%, rgba(236,72,153,0.12), transparent); border-bottom:1px solid rgba(99,102,241,0.2);\">
                <div style=\"font-weight:700; font-size:20px; letter-spacing:.4px; color:#00F0FF;\">ARIUS</div>
                <div style=\"margin-top:4px; font-size:14px; color:#9CA3AF;\">Advanced Tactical Interface</div>
              </td>
            </tr>
            <tr>
              <td style=\"padding:28px 24px 8px 24px;\">
                <h1 style=\"margin:0; font-size:22px; line-height:1.3; color:#E5E7EB;\">One‑Click Secure Access</h1>
                <p style=\"margin:12px 0 0; font-size:14px; color:#B0B6C2; line-height:1.6;\">Tap the button below to sign in to your ARIUS console.</p>
              </td>
            </tr>
            <tr>
              <td align=\"center\" style=\"padding:12px 24px 4px 24px;\">
                <a href=\"{login_url}\" style=\"display:inline-block; padding:14px 22px; background:#00F0FF; color:#0B1220; text-decoration:none; border-radius:12px; font-weight:700; letter-spacing:.3px; box-shadow:0 0 20px rgba(0,240,255,0.35);\">Access ARIUS</a>
              </td>
            </tr>
            <tr>
              <td style=\"padding:8px 24px 0 24px;\" align=\"center\">
                <div style=\"font-size:12px; color:#9CA3AF;\">Or copy &amp; paste this link in your browser:</div>
                <div style=\"margin-top:8px; font-size:12px; color:#E5E7EB; word-break:break-all; background:rgba(2,6,23,0.6); border:1px solid rgba(99,102,241,0.25); padding:10px 12px; border-radius:8px;\">{login_url}</div>
              </td>
            </tr>
            <tr>
              <td style=\"padding:18px 24px 8px 24px;\">
                <div style=\"height:1px; background:linear-gradient(90deg, rgba(0,240,255,0.25), rgba(99,102,241,0.2), rgba(236,72,153,0.25));\"></div>
              </td>
            </tr>
            <tr>
              <td style=\"padding:8px 24px 24px 24px;\">
                <p style=\"margin:0; font-size:12px; color:#93A3B8; line-height:1.6;\">If you didn’t request this, you can safely ignore this email. The link will expire in 7 days.</p>
              </td>
            </tr>
          </table>
          <div style=\"margin-top:14px; font-size:11px; color:#6B7280;\">© {datetime.utcnow().year} ARIUS</div>
        </td>
      </tr>
    </table>
  </body>
 </html>
    """

    message = Mail(
        from_email=EMAIL_SENDER,
        to_emails=recipient,
        subject="Your ARIUS Magic Login Link",
        html_content=html,
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        print(f"SendGrid Error: {e}")