from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from typing import Any

import requests

from config.settings import settings


logger = logging.getLogger(__name__)
SUPPORTED_EMAIL_PROVIDERS = {"sendgrid", "resend", "brevo", "smtp", "console", "gmail_relay", "gmail", "apps_script"}


class EmailDeliveryError(RuntimeError):
    """Raised when transactional email delivery fails."""


class EmailService:
    def _resolved_provider(self) -> str:
        configured_provider = (settings.EMAIL_PROVIDER or "").strip().lower()
        if configured_provider:
            if configured_provider not in SUPPORTED_EMAIL_PROVIDERS:
                return configured_provider

            if configured_provider in {"gmail_relay", "gmail", "apps_script"}:
                if (settings.GMAIL_RELAY_URL or "").strip():
                    return "gmail_relay"
                logger.warning(
                    "EMAIL_PROVIDER=%s configured but GMAIL_RELAY_URL is missing; falling back to autodetect.",
                    configured_provider,
                )

            if configured_provider == "smtp":
                return "smtp"

            # Explicit API providers remain authoritative only when they are actually
            # configured; otherwise the app can still fall back to another available
            # provider during autodetect.
            if configured_provider == "resend":
                if (settings.RESEND_API_KEY or "").strip() and self._configured_from_address():
                    return "resend"
                logger.warning("EMAIL_PROVIDER=resend configured but RESEND_API_KEY or EMAIL_FROM is missing; falling back to autodetect.")

            if configured_provider == "sendgrid":
                if (settings.SENDGRID_API_KEY or "").strip() and self._configured_from_address():
                    return "sendgrid"
                logger.warning("EMAIL_PROVIDER=sendgrid configured but SENDGRID_API_KEY or EMAIL_FROM is missing; falling back to autodetect.")

            if configured_provider == "brevo":
                if (settings.BREVO_API_KEY or "").strip() and self._configured_from_address():
                    return "brevo"
                logger.warning("EMAIL_PROVIDER=brevo configured but BREVO_API_KEY or EMAIL_FROM is missing; falling back to autodetect.")

            if configured_provider == "console":
                return "console"

        # Autodetect provider by available credentials (preferred order).
        if (settings.GMAIL_RELAY_URL or "").strip():
            return "gmail_relay"

        if (settings.SMTP_HOST or "").strip() and self._configured_from_address():
            return "smtp"

        if (settings.RESEND_API_KEY or "").strip() and self._configured_from_address():
            return "resend"

        if (settings.SENDGRID_API_KEY or "").strip() and self._configured_from_address():
            return "sendgrid"

        if (settings.BREVO_API_KEY or "").strip() and self._configured_from_address():
            return "brevo"

        if settings.DEBUG:
            return "console"

        return ""

    def get_delivery_status(self) -> dict:
        provider = self._resolved_provider()
        from_address_ready = bool(self._configured_from_address())
        smtp_host_ready = bool((settings.SMTP_HOST or "").strip())
        smtp_username = self._configured_smtp_username()
        smtp_password = self._configured_smtp_password()
        sendgrid_key_ready = bool((settings.SENDGRID_API_KEY or "").strip())
        resend_key_ready = bool((settings.RESEND_API_KEY or "").strip())
        brevo_key_ready = bool((settings.BREVO_API_KEY or "").strip())
        gmail_relay_ready = bool((settings.GMAIL_RELAY_URL or "").strip())

        if provider == "gmail_relay":
            return {
                "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
                "provider": "gmail_relay",
                "delivery_mode": "email" if gmail_relay_ready else "unconfigured",
                "ready": gmail_relay_ready,
            }

        if provider == "resend":
            ready = from_address_ready and resend_key_ready
            return {
                "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
                "provider": "resend",
                "delivery_mode": "email" if ready else "unconfigured",
                "ready": ready,
            }

        if provider == "sendgrid":
            ready = from_address_ready and sendgrid_key_ready
            return {
                "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
                "provider": "sendgrid",
                "delivery_mode": "email" if ready else "unconfigured",
                "ready": ready,
            }

        if provider == "brevo":
            ready = from_address_ready and brevo_key_ready
            return {
                "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
                "provider": "brevo",
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

        if provider == "console":
            return {
                "configured_provider": (settings.EMAIL_PROVIDER or "").strip().lower() or None,
                "provider": "console",
                "delivery_mode": "console",
                "ready": True,
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

    def send_registration_otp(
        self,
        *,
        recipient_email: str,
        otp_code: str,
        recipient_name: str = "",
    ) -> str:
        subject, text_body, html_body = self._build_registration_otp_email(
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
        if provider == "gmail_relay":
            self._send_via_gmail_relay(
                recipient_email=recipient_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            return "email"

        if provider == "resend":
            self._send_via_resend(
                recipient_email=recipient_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            return "email"

        if provider == "sendgrid":
            self._send_via_sendgrid(
                recipient_email=recipient_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            return "email"

        if provider == "brevo":
            self._send_via_brevo(
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

        if provider == "console":
            self._send_via_console(
                recipient_email=recipient_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            return "console"

        configured_provider = (settings.EMAIL_PROVIDER or "").strip().lower()
        if configured_provider and configured_provider not in SUPPORTED_EMAIL_PROVIDERS:
            raise EmailDeliveryError(
                f"Unknown EMAIL_PROVIDER '{configured_provider}'. Use 'gmail_relay', 'resend', 'sendgrid', 'brevo', 'smtp', or 'console'."
            )

        raise EmailDeliveryError(self._configuration_error_message())

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

    def _build_registration_otp_email(
        self,
        *,
        otp_code: str,
        recipient_name: str,
    ) -> tuple[str, str, str]:
        greeting_name = recipient_name.strip() or "there"
        app_name = settings.APP_NAME
        expiry_minutes = settings.AUTH_OTP_EXPIRE_MINUTES
        subject = f"Verify your {app_name} account"

        text_body = (
            f"Hi {greeting_name},\n\n"
            f"Thanks for registering for {app_name}. Use this verification code to activate your account:\n\n"
            f"{otp_code}\n\n"
            f"This code expires in {expiry_minutes} minutes.\n\n"
            "Enter the code on the verification screen to complete your registration.\n"
            f"If you did not create a {app_name} account, you can ignore this email."
        )

        html_body = self._build_email_shell(
            preheader=f"Your {app_name} account verification code is {otp_code}. It expires in {expiry_minutes} minutes.",
            eyebrow="Account verification",
            title=f"Welcome to {app_name}",
            greeting_name=greeting_name,
            intro_html=(
                f"Thanks for registering for <strong>{escape(app_name)}</strong>. "
                "Use the code below to verify your email address and activate your account."
            ),
            highlight_html=f"""
              <div style="margin:0 0 14px;font-size:12px;line-height:1.5;color:#cbd5e1;letter-spacing:0.12em;text-transform:uppercase;">
                Registration code
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
                  Next step
                </div>
                <div style="margin:0 0 8px;font-size:15px;line-height:1.7;color:#0f172a;">
                  Return to the {escape(app_name)} verification screen and enter the six-digit code exactly as shown.
                </div>
                <div style="margin:0;font-size:15px;line-height:1.7;color:#0f172a;">
                  Your account will be activated after the code is verified.
                </div>
              </div>
              <div style="margin:0;padding:16px 18px;border-radius:16px;background:#fff7ed;border:1px solid #fed7aa;">
                <div style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#9a3412;font-weight:700;">
                  Security note
                </div>
                <div style="margin:0;font-size:14px;line-height:1.7;color:#9a3412;">
                  If you did not create this account, you can ignore this message. No account access is granted until the code is verified.
                </div>
              </div>
            """.strip(),
            footer_html=(
                "This is an automated account verification email from "
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
            f"Use this password reset code to continue resetting your {app_name} password:\n\n"
            f"{otp_code}\n\n"
            f"This code expires in {expiry_minutes} minutes.\n\n"
            "Enter the code on the password reset screen to continue.\n"
            "If you did not request this, you can ignore this email."
        )

        html_body = self._build_email_shell(
            preheader=f"Your {app_name} password reset code is {otp_code}. It expires in {expiry_minutes} minutes.",
            eyebrow="Account security",
            title="Your one-time password reset code",
            greeting_name=greeting_name,
            intro_html=(
                f"Use the code below to continue resetting your <strong>{escape(app_name)}</strong> password. "
                "For your security, this code is short-lived and can only be used once."
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
            body_html=f"""
              <div style="margin:0 0 18px;padding:16px 18px;border-radius:16px;background:#f8fafc;border:1px solid #e2e8f0;">
                <div style="margin:0 0 10px;font-size:13px;line-height:1.5;color:#475569;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">
                  How to use it
                </div>
                <div style="margin:0 0 8px;font-size:15px;line-height:1.7;color:#0f172a;">
                  1. Return to the password reset screen in {escape(app_name)}.
                </div>
                <div style="margin:0 0 8px;font-size:15px;line-height:1.7;color:#0f172a;">
                  2. Enter the six-digit code exactly as shown above.
                </div>
                <div style="margin:0;font-size:15px;line-height:1.7;color:#0f172a;">
                  3. Set your new password before the code expires.
                </div>
              </div>
              <div style="margin:0;padding:16px 18px;border-radius:16px;background:#fff7ed;border:1px solid #fed7aa;">
                <div style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#9a3412;font-weight:700;">
                  Security note
                </div>
                <div style="margin:0;font-size:14px;line-height:1.7;color:#9a3412;">
                  If this wasn&apos;t you, ignore this message. Your current password stays unchanged until a valid code is used.
                </div>
              </div>
            """.strip(),
            footer_html=(
                "This is an automated account security email from "
                f"{escape(app_name)}. Please do not reply unless you configured a reply-to address."
            ),
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

    def _smtp_fallback_available(self) -> bool:
        return bool((settings.SMTP_HOST or "").strip() and self._configured_from_address())

    def _resend_testing_only_error(self, response_text: str | None) -> bool:
        if not response_text:
            return False
        lower = response_text.lower()
        return (
            "testing emails to your own email address" in lower
            or "verify a domain at resend.com/domains" in lower
            or "invalid from address" in lower
        )

    def _send_via_gmail_relay(
        self,
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        relay_url = (settings.GMAIL_RELAY_URL or "").strip()
        from_name = (settings.EMAIL_FROM_NAME or "").strip() or settings.APP_NAME

        if not relay_url:
            raise EmailDeliveryError("GMAIL_RELAY_URL is required when EMAIL_PROVIDER=gmail_relay.")

        payload: dict[str, Any] = {
            "to": recipient_email,
            "subject": subject,
            "htmlBody": html_body,
            "textBody": text_body,
            "fromName": from_name,
        }
        if (settings.GMAIL_RELAY_SECRET or "").strip():
            payload["secret"] = (settings.GMAIL_RELAY_SECRET or "").strip()

        try:
            response = requests.post(
                relay_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=settings.SMTP_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
            if not response.ok:
                logger.error("gmail_relay_send_failed status=%s response=%s", response.status_code, response.text)
                response.raise_for_status()

            # Attempt to parse response if it returns an error JSON
            try:
                data = response.json()
                if isinstance(data, dict) and data.get("status") == "error":
                    raise EmailDeliveryError(f"Gmail relay error: {data.get('message', 'Unknown error')}")
            except (ValueError, TypeError):
                pass
        except requests.RequestException as exc:
            err_msg = "Gmail Relay could not deliver the verification email."
            if hasattr(exc, "response") and exc.response is not None:
                err_msg += f" (Status {exc.response.status_code}: {exc.response.text})"
            raise EmailDeliveryError(err_msg) from exc

    def _send_via_resend(
        self,
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        api_key = (settings.RESEND_API_KEY or "").strip()
        from_header = self._from_header()

        if not api_key:
            raise EmailDeliveryError("RESEND_API_KEY is required when EMAIL_PROVIDER=resend.")

        payload: dict[str, Any] = {
            "from": from_header,
            "to": [recipient_email],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }

        reply_to = (settings.EMAIL_REPLY_TO or "").strip()
        if reply_to:
            payload["reply_to"] = reply_to

        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            )
            if not response.ok:
                logger.error("resend_send_failed status=%s response=%s", response.status_code, response.text)
                if self._resend_testing_only_error(response.text) and self._smtp_fallback_available():
                    logger.warning(
                        "resend_testing_only_error_detected; falling back to configured SMTP delivery for %s",
                        recipient_email,
                    )
                    self._send_via_smtp(
                        recipient_email=recipient_email,
                        subject=subject,
                        text_body=text_body,
                        html_body=html_body,
                    )
                    return
                response.raise_for_status()
        except requests.RequestException as exc:
            response_text = getattr(getattr(exc, "response", None), "text", "") or ""
            if self._resend_testing_only_error(response_text) and self._smtp_fallback_available():
                logger.warning(
                    "resend_testing_only_error_detected; falling back to configured SMTP delivery for %s",
                    recipient_email,
                )
                self._send_via_smtp(
                    recipient_email=recipient_email,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
                return
            err_msg = "Resend could not deliver the verification email."
            if hasattr(exc, "response") and exc.response is not None:
                err_msg += f" (Status {exc.response.status_code}: {exc.response.text})"
            raise EmailDeliveryError(err_msg) from exc

    def _send_via_brevo(
        self,
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        api_key = (settings.BREVO_API_KEY or "").strip()
        from_address = self._from_address()
        from_name = (settings.EMAIL_FROM_NAME or "").strip() or "NOVA AI"

        if not api_key:
            raise EmailDeliveryError("BREVO_API_KEY is required when EMAIL_PROVIDER=brevo.")

        payload: dict[str, Any] = {
            "sender": {"name": from_name, "email": from_address},
            "to": [{"email": recipient_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body,
        }

        reply_to = (settings.EMAIL_REPLY_TO or "").strip()
        if reply_to:
            payload["replyTo"] = {"email": reply_to}

        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            )
            if not response.ok:
                logger.error("brevo_send_failed status=%s response=%s", response.status_code, response.text)
                response.raise_for_status()
        except requests.RequestException as exc:
            err_msg = "Brevo could not deliver the verification email."
            if hasattr(exc, "response") and exc.response is not None:
                err_msg += f" (Status {exc.response.status_code}: {exc.response.text})"
            raise EmailDeliveryError(err_msg) from exc

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
            if not response.ok:
                logger.error("sendgrid_send_failed status=%s response=%s", response.status_code, response.text)
                response.raise_for_status()
        except requests.RequestException as exc:
            err_msg = "SendGrid could not deliver the verification email."
            if hasattr(exc, "response") and exc.response is not None:
                err_msg += f" (Status {exc.response.status_code}: {exc.response.text})"
            raise EmailDeliveryError(err_msg) from exc

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
        if smtp_username and not smtp_password:
            raise EmailDeliveryError(
                "SMTP password is required when SMTP_USER or SMTP_USERNAME is set. "
                "Set SMTP_PASS or SMTP_PASSWORD."
            )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = from_header
        message["To"] = recipient_email

        reply_to = (settings.EMAIL_REPLY_TO or "").strip()
        if reply_to:
            message["Reply-To"] = reply_to

        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        context = ssl.create_default_context()
        configured_port = settings.SMTP_PORT or (465 if settings.SMTP_USE_SSL else 587)

        # Respect the configured SMTP port exactly; do not silently switch from
        # the intended Gmail TLS configuration (587) to implicit SSL on 465.
        attempts: list[tuple[str, str, int]] = []
        if settings.SMTP_USE_SSL:
            attempts.append(("ssl", host, configured_port))
        else:
            if settings.SMTP_USE_TLS:
                attempts.append(("tls", host, configured_port))
            else:
                attempts.append(("plain", host, configured_port))

        last_error: Exception | None = None

        for mode, target_host, target_port in attempts:
            try:
                if mode == "ssl":
                    with smtplib.SMTP_SSL(
                        target_host,
                        target_port,
                        context=context,
                        timeout=settings.SMTP_TIMEOUT_SECONDS,
                    ) as client:
                        if smtp_username:
                            client.login(smtp_username, smtp_password)
                        client.send_message(message, from_addr=from_address, to_addrs=[recipient_email])
                    return
                else:
                    with smtplib.SMTP(
                        target_host,
                        target_port,
                        timeout=settings.SMTP_TIMEOUT_SECONDS,
                    ) as client:
                        if mode == "tls":
                            client.starttls(context=context)
                        if smtp_username:
                            client.login(smtp_username, smtp_password)
                        client.send_message(message, from_addr=from_address, to_addrs=[recipient_email])
                    return
            except smtplib.SMTPAuthenticationError as exc:
                logger.error(
                    "smtp_auth_failed host=%s port=%s username=%s mode=%s smtp_code=%s smtp_error=%s",
                    target_host,
                    target_port,
                    smtp_username,
                    mode,
                    getattr(exc, "smtp_code", None),
                    getattr(exc, "smtp_error", b"").decode("utf-8", errors="ignore"),
                )
                # On authentication failures, prefer to surface an error in production,
                # but allow a console fallback during local development for easier testing.
                if settings.DEBUG:
                    logger.warning(
                        "SMTP auth failed but DEBUG=True, falling back to console delivery: host=%s port=%s username=%s",
                        target_host,
                        target_port,
                        smtp_username,
                    )
                    self._send_via_console(
                        recipient_email=recipient_email,
                        subject=subject,
                        text_body=text_body,
                        html_body=html_body,
                    )
                    return

                if target_host.lower() == "smtp.gmail.com":
                    raise EmailDeliveryError(
                        "Gmail rejected the SMTP login. Use a Google App Password, not your normal Gmail password."
                    ) from exc
                raise EmailDeliveryError("SMTP login failed. Check the username and password for your mail provider.") from exc
            except (smtplib.SMTPException, OSError) as exc:
                logger.warning(
                    "smtp_attempt_failed mode=%s host=%s port=%s error=%s",
                    mode,
                    target_host,
                    target_port,
                    exc,
                )
                last_error = exc

        if last_error:
            if settings.DEBUG:
                logger.warning("smtp_failed_falling_back_to_console in debug mode: %s", last_error)
                self._send_via_console(
                    recipient_email=recipient_email,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
                return
            raise EmailDeliveryError("SMTP could not deliver the verification email.") from last_error

    def _send_via_console(
        self,
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        logger.info(
            "\n" + "="*60 +
            f"\n[CONSOLE EMAIL] Sending email to: {recipient_email}"
            f"\nSubject: {subject}"
            f"\nBody:\n{text_body}"
            "\n" + "="*60
        )

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

    def _configuration_error_message(self) -> str:
        return (
            "Email delivery is not configured. For Gmail Relay, set EMAIL_PROVIDER=gmail_relay and "
            "GMAIL_RELAY_URL. For SMTP, set EMAIL_PROVIDER=smtp, SMTP_HOST, SMTP_PORT, "
            "SMTP_USER, and SMTP_PASS. For Brevo, set EMAIL_PROVIDER=brevo and BREVO_API_KEY. "
            "For Resend, set EMAIL_PROVIDER=resend and RESEND_API_KEY."
        )


email_service = EmailService()