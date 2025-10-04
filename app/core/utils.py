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
    """Sends a magic login link to a user's email via SendGrid.

    Args:
        recipient (str): The email address of the recipient.
        token (str): The magic link token to include in the login URL.
    """
    login_url = f"http://localhost:3000/profile/login/magic-link?token={token}"
    message = Mail(
        from_email=EMAIL_SENDER,
        to_emails=recipient,
        subject="Your Magic Login Link",
        html_content=f"""
            <p>Click the link below to log in:</p>
            <p><a href="{login_url}">Log in</a></p>
            <p>This link will expire in 15 minutes.</p>
        """
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        print(f"SendGrid Error: {e}")