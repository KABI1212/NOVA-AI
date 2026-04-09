from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

import requests

from config.settings import settings


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when transactional email delivery fails."""


class EmailService:
    def _resolved_provider(self) -> str:
        configured_provider = (settings.EMAIL_PROVIDER or "").strip().lower()
        if configured_provider:
            return configured_provider

        if (settings.SENDGRID_API_KEY or "").strip() and self._configured_from_address():
            return "sendgrid"

        if (settings.SMTP_HOST or "").strip() and self._configured_from_address():
            return "smtp"

        return ""

    def get_delivery_status(self) -> dict:
        provider = self._resolved_provider()
        from_address_ready = bool(self._configured_from_address())
        smtp_host_ready = bool((settings.SMTP_HOST or "").strip())
        smtp_username = self._configured_smtp_username()
        smtp_password = self._configured_smtp_password()
        sendgrid_key_ready = bool((settings.SENDGRID_API_KEY or "").strip())

        if provider == "sendgrid":
            ready = from_address_ready and sendgrid_key_ready
            return {
                "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
                "provider": "sendgrid",
                "delivery_mode": "email" if ready else "unconfigured",
                "ready": ready,
            }

        if provider == "smtp":
            auth_ready = (not smtp_username) or bool(smtp_password)
            ready = from_address_ready and smtp_host_ready and auth_ready
            return {
                "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
                "provider": "smtp",
                "delivery_mode": "email" if ready else "unconfigured",
                "ready": ready,
            }

        return {
            "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
            "provider": None,
            "delivery_mode": "unconfigured",
            "ready": False,
        }

    def can_send_real_email(self) -> bool:
        return bool(self.get_delivery_status().get("ready"))

    def send_login_otp(
        self,
        *,
        recipient_email: str,
        otp_code: str,
        recipient_name: str = "",
    ) -> str:
        subject, text_body, html_body = self._build_login_otp_email(
            otp_code=otp_code,
            recipient_name=recipient_name,
        )
        return self._deliver_email(
            recipient_email=recipient_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    def send_password_reset_otp(
        self,
        *,
        recipient_email: str,
        otp_code: str,
        recipient_name: str = "",
    ) -> str:
        subject, text_body, html_body = self._build_password_reset_otp_email(
            otp_code=otp_code,
            recipient_name=recipient_name,
        )
        return self._deliver_email(
            recipient_email=recipient_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    def send_test_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str = "",
    ) -> str:
        subject, text_body, html_body = self._build_test_email(
            recipient_name=recipient_name,
        )
        return self._deliver_email(
            recipient_email=recipient_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    def _deliver_email(
        self,
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> str:
        provider = self._resolved_provider()
        if provider == "sendgrid":
            self._send_via_sendgrid(
                recipient_email=recipient_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            return "email"

        if provider == "smtp":
            self._send_via_smtp(
                recipient_email=recipient_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            return "email"

        raise EmailDeliveryError(
            "Email delivery is not configured. Set EMAIL_PROVIDER=smtp and provide SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, and EMAIL_FROM."
        )

    def _build_login_otp_email(
        self,
        *,
        otp_code: str,
        recipient_name: str,
    ) -> tuple[str, str, str]:
        greeting_name = recipient_name.strip() or "there"
        app_name = settings.APP_NAME
        expiry_minutes = settings.AUTH_OTP_EXPIRE_MINUTES
        subject = f"{app_name} login verification code"

        text_body = (
            f"Hi {greeting_name},\n\n"
            f"Use this verification code to finish signing in to {app_name}:\n\n"
            f"{otp_code}\n\n"
            f"This code expires in {expiry_minutes} minutes.\n\n"
            "Enter the code on the verification screen to complete your sign-in.\n"
            "If you did not try to sign in, you can ignore this email."
        )

        html_body = self._build_email_shell(
            preheader=f"Your {app_name} verification code is {otp_code}. It expires in {expiry_minutes} minutes.",
            eyebrow="Secure sign-in verification",
            title="Your one-time verification code",
            greeting_name=greeting_name,
            intro_html=(
                f"Use the code below to continue signing in to <strong>{escape(app_name)}</strong>. "
                "For your security, this code is short-lived and can only be used once."
            ),
            highlight_html=f"""
              <div style="margin:0 0 14px;font-size:12px;line-height:1.5;color:#cbd5e1;letter-spacing:0.12em;text-transform:uppercase;">
                Verification code
              </div>
              <div style="margin:0 0 8px;font-size:38px;line-height:1;font-weight:800;letter-spacing:10px;color:#ffffff;">
                {escape(otp_code)}
              </div>
              <div style="font-size:13px;line-height:1.6;color:#bfdbfe;">
                Expires in {expiry_minutes} minutes
              </div>
            """.strip(),
            body_html=f"""
              <div style="margin:0 0 18px;padding:16px 18px;border-radius:16px;background:#f8fafc;border:1px solid #e2e8f0;">
                <div style="margin:0 0 10px;font-size:13px;line-height:1.5;color:#475569;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">
                  How to use it
                </div>
                <div style="margin:0 0 8px;font-size:15px;line-height:1.7;color:#0f172a;">
                  1. Return to the verification screen in {escape(app_name)}.
                </div>
                <div style="margin:0 0 8px;font-size:15px;line-height:1.7;color:#0f172a;">
                  2. Enter the six-digit code exactly as shown above.
                </div>
                <div style="margin:0;font-size:15px;line-height:1.7;color:#0f172a;">
                  3. Finish sign-in before the code expires.
                </div>
              </div>
              <div style="margin:0;padding:16px 18px;border-radius:16px;background:#fff7ed;border:1px solid #fed7aa;">
                <div style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#9a3412;font-weight:700;">
                  Security note
                </div>
                <div style="margin:0;font-size:14px;line-height:1.7;color:#9a3412;">
                  If you did not try to sign in, you can ignore this message. Your password was not sent in this email.
                </div>
              </div>
            """.strip(),
            footer_html=(
                "This is an automated security email from "
                f"{escape(app_name)}. Please do not reply unless you configured a reply-to address."
            ),
        )

        return subject, text_body, html_body

    def _build_password_reset_otp_email(
        self,
        *,
        otp_code: str,
        recipient_name: str,
    ) -> tuple[str, str, str]:
        greeting_name = recipient_name.strip() or "there"
        app_name = settings.APP_NAME
        expiry_minutes = settings.AUTH_OTP_EXPIRE_MINUTES
        subject = f"{app_name} password reset code"

        text_body = (
            f"Hi {greeting_name},\n\n"
            f"You requested a password reset for {app_name}.\n"
            f"Use this verification code to continue:\n\n"
            f"{otp_code}\n\n"
            f"This code expires in {expiry_minutes} minutes.\n\n"
            "If you did not request this, you can ignore this email."
        )

        html_body = self._build_email_shell(
            preheader=f"Your {app_name} password reset code is {otp_code}.",
            eyebrow="Account security",
            title="Reset your password",
            greeting_name=greeting_name,
            intro_html=(
                "Use the one-time code below to set a new password for your account. "
                "This helps keep your account secure."
            ),
            highlight_html=f"""
              <div style="margin:0 0 14px;font-size:12px;line-height:1.5;color:#cbd5e1;letter-spacing:0.12em;text-transform:uppercase;">
                Password reset code
              </div>
              <div style="margin:0 0 8px;font-size:38px;line-height:1;font-weight:800;letter-spacing:10px;color:#ffffff;">
                {escape(otp_code)}
              </div>
              <div style="font-size:13px;line-height:1.6;color:#bfdbfe;">
                Expires in {expiry_minutes} minutes
              </div>
            """.strip(),
            body_html="""
              <div style="margin:0;padding:16px 18px;border-radius:16px;background:#fff7ed;border:1px solid #fed7aa;">
                <div style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#9a3412;font-weight:700;">
                  Didn&apos;t request this?
                </div>
                <div style="margin:0;font-size:14px;line-height:1.7;color:#9a3412;">
                  If this wasn&apos;t you, ignore this message. Your current password stays unchanged until a valid code is used.
                </div>
              </div>
            """.strip(),
            footer_html=f"This automated message was sent by {escape(app_name)}.",
        )

        return subject, text_body, html_body

    def _build_test_email(
        self,
        *,
        recipient_name: str,
    ) -> tuple[str, str, str]:
        greeting_name = recipient_name.strip() or "there"
        app_name = settings.APP_NAME
        subject = f"{app_name} email delivery test"

        text_body = (
            f"Hi {greeting_name},\n\n"
            f"This is a test email from {app_name}.\n"
            "If you received this message, inbox delivery is working correctly."
        )

        html_body = self._build_email_shell(
            preheader=f"This is a delivery test from {app_name}.",
            eyebrow="Email delivery test",
            title="Inbox delivery is working",
            greeting_name=greeting_name,
            intro_html=(
                f"This is a confirmation email from <strong>{escape(app_name)}</strong>. "
                "If this landed in your inbox, your email provider settings are working correctly."
            ),
            highlight_html="""
              <div style="margin:0;font-size:22px;line-height:1.4;font-weight:800;color:#ffffff;">
                Your email provider is connected successfully
              </div>
            """.strip(),
            body_html="""
              <div style="margin:0;padding:16px 18px;border-radius:16px;background:#ecfdf5;border:1px solid #a7f3d0;">
                <div style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#166534;font-weight:700;">
                  What this confirms
                </div>
                <div style="margin:0;font-size:14px;line-height:1.7;color:#166534;">
                  Transactional emails from this app can now be delivered to a real inbox, including login verification codes.
                </div>
              </div>
            """.strip(),
            footer_html=(
                "You can now use this same mail configuration for login OTP verification and other account emails."
            ),
        )

        return subject, text_body, html_body

    def _build_email_shell(
        self,
        *,
        preheader: str,
        eyebrow: str,
        title: str,
        greeting_name: str,
        intro_html: str,
        highlight_html: str,
        body_html: str,
        footer_html: str,
    ) -> str:
        app_name = escape(settings.APP_NAME)

        return f"""
<html>
  <body style="margin:0;padding:0;background:#e2e8f0;font-family:Arial,'Segoe UI',sans-serif;color:#0f172a;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
      {escape(preheader)}
    </div>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#e2e8f0;margin:0;padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:620px;">
            <tr>
              <td style="padding:0 0 14px 0;text-align:center;font-size:12px;line-height:1.6;letter-spacing:0.18em;text-transform:uppercase;color:#475569;font-weight:700;">
                {app_name}
              </td>
            </tr>
            <tr>
              <td style="background:linear-gradient(135deg,#0f172a 0%,#1d4ed8 100%);border-radius:24px 24px 0 0;padding:22px 28px 18px 28px;color:#ffffff;">
                <div style="margin:0 0 10px;font-size:12px;line-height:1.5;letter-spacing:0.16em;text-transform:uppercase;color:#bfdbfe;font-weight:700;">
                  {escape(eyebrow)}
                </div>
                <div style="margin:0;font-size:30px;line-height:1.2;font-weight:800;color:#ffffff;">
                  {escape(title)}
                </div>
              </td>
            </tr>
            <tr>
              <td style="background:#ffffff;border:1px solid #cbd5e1;border-top:none;border-radius:0 0 24px 24px;padding:28px;">
                <div style="margin:0 0 14px;font-size:16px;line-height:1.7;color:#0f172a;">
                  Hi {escape(greeting_name)},
                </div>
                <div style="margin:0 0 20px;font-size:15px;line-height:1.8;color:#334155;">
                  {intro_html}
                </div>
                <div style="margin:0 0 22px;padding:22px 24px;border-radius:22px;background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);box-shadow:0 18px 40px rgba(15,23,42,0.22);text-align:center;">
                  {highlight_html}
                </div>
                <div style="margin:0 0 20px;">
                  {body_html}
                </div>
                <div style="padding-top:18px;border-top:1px solid #e2e8f0;font-size:13px;line-height:1.7;color:#64748b;">
                  {footer_html}
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()

    def _send_via_sendgrid(
        self,
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        api_key = (settings.SENDGRID_API_KEY or "").strip()
        from_address = self._from_address()
        from_name = (settings.EMAIL_FROM_NAME or "").strip()

        if not api_key:
            raise EmailDeliveryError("SENDGRID_API_KEY is required when EMAIL_PROVIDER=sendgrid.")

        payload = {
            "personalizations": [{"to": [{"email": recipient_email}]}],
            "from": {
                "email": from_address,
                **({"name": from_name} if from_name else {}),
            },
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body},
            ],
        }

        reply_to = (settings.EMAIL_REPLY_TO or "").strip()
        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        try:
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EmailDeliveryError("SendGrid could not deliver the verification email.") from exc

    def _send_via_smtp(
        self,
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        host = (settings.SMTP_HOST or "").strip()
        from_address = self._from_address()
        from_header = self._from_header()
        smtp_username = self._configured_smtp_username()
        smtp_password = self._configured_smtp_password()

        # Google shows app passwords grouped with spaces, but SMTP expects the raw 16-character value.
        if host.lower() == "smtp.gmail.com":
            normalized_password = smtp_password.replace(" ", "")
            if len(normalized_password) == 16:
                smtp_password = normalized_password

        if not host:
            raise EmailDeliveryError("SMTP_HOST is required when EMAIL_PROVIDER=smtp.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = from_header
        message["To"] = recipient_email

        reply_to = (settings.EMAIL_REPLY_TO or "").strip()
        if reply_to:
            message["Reply-To"] = reply_to

        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        smtp_factory = smtplib.SMTP_SSL if settings.SMTP_USE_SSL else smtplib.SMTP
        context = ssl.create_default_context()

        try:
            with smtp_factory(host, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as client:
                if not settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
                    client.starttls(context=context)
                if smtp_username:
                    client.login(smtp_username, smtp_password)
                client.send_message(message, from_addr=from_address, to_addrs=[recipient_email])
        except smtplib.SMTPAuthenticationError as exc:
            logger.error(
                "smtp_auth_failed host=%s port=%s username=%s smtp_code=%s smtp_error=%s",
                host,
                settings.SMTP_PORT,
                smtp_username,
                getattr(exc, "smtp_code", None),
                getattr(exc, "smtp_error", b"").decode("utf-8", errors="ignore"),
            )
            if host.lower() == "smtp.gmail.com":
                raise EmailDeliveryError(
                    "Gmail rejected the SMTP login. Use a Google App Password, not your normal Gmail password."
                ) from exc
            raise EmailDeliveryError("SMTP login failed. Check the username and password for your mail provider.") from exc
        except smtplib.SMTPException as exc:
            raise EmailDeliveryError("SMTP could not deliver the verification email.") from exc
        except OSError as exc:
            raise EmailDeliveryError("SMTP connection failed while sending the verification email.") from exc

    def _from_address(self) -> str:
        from_address = self._configured_from_address()
        if not from_address:
            raise EmailDeliveryError("EMAIL_FROM is required for email delivery.")
        return from_address

    def _from_header(self) -> str:
        from_address = self._from_address()
        from_name = (settings.EMAIL_FROM_NAME or "").strip()
        if not from_name:
            return from_address
        return f"{from_name} <{from_address}>"

    def _configured_from_address(self) -> str:
        return (
            (settings.EMAIL_FROM or "").strip()
            or (settings.EMAIL_FROM_ADDRESS or "").strip()
        )

    def _configured_smtp_username(self) -> str:
        return (
            (settings.SMTP_USER or "").strip()
            or (settings.SMTP_USERNAME or "").strip()
        )

    def _configured_smtp_password(self) -> str:
        return (
            (settings.SMTP_PASS or "").strip()
            or (settings.SMTP_PASSWORD or "").strip()
        )


email_service = EmailService()
