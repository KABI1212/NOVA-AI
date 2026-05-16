from __future__ import annotations

import importlib
import smtplib

import pytest

from services.email_service import EmailService
email_service_module = importlib.import_module("services.email_service")


def test_build_login_otp_email_renders_branded_html() -> None:
    service = EmailService()

    subject, text_body, html_body = service._build_login_otp_email(
        otp_code="123456",
        recipient_name="Alex",
    )

    assert "verification code" in subject.lower()
    assert "123456" in text_body
    assert "expires in 5 minutes" in text_body.lower()
    assert "NOVA AI" in html_body
    assert "Your one-time verification code" in html_body
    assert "Security note" in html_body
    assert "123456" in html_body


def test_build_registration_otp_email_renders_account_verification_copy() -> None:
    service = EmailService()

    subject, text_body, html_body = service._build_registration_otp_email(
        otp_code="123456",
        recipient_name="Alex",
    )

    assert "verify your nova ai account" in subject.lower()
    assert "Thanks for registering" in text_body
    assert "123456" in text_body
    assert "Welcome to NOVA AI" in html_body
    assert "Registration code" in html_body
    assert "activate your account" in html_body
    assert "123456" in html_body


def test_build_password_reset_otp_email_matches_branded_code_layout() -> None:
    service = EmailService()

    subject, text_body, html_body = service._build_password_reset_otp_email(
        otp_code="654321",
        recipient_name="Alex",
    )

    assert "password reset code" in subject.lower()
    assert "654321" in text_body
    assert "expires in 5 minutes" in text_body.lower()
    assert "Your one-time password reset code" in html_body
    assert "How to use it" in html_body
    assert "Security note" in html_body
    assert "654321" in html_body


def test_build_test_email_renders_delivery_confirmation() -> None:
    service = EmailService()

    subject, text_body, html_body = service._build_test_email(
        recipient_name="Alex",
    )

    assert "delivery test" in subject.lower()
    assert "test email" in text_body.lower()
    assert "Inbox delivery is working" in html_body
    assert "email provider is connected successfully" in html_body


def test_gmail_smtp_auth_failure_maps_to_app_password_message(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmailService()

    class _FakeSMTP:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context=None) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

    monkeypatch.setattr(email_service_module.settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service_module.settings, "SMTP_USER", "kabileshk702@gmail.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASS", "wrong-password")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(email_service_module.settings, "SMTP_USE_SSL", False)
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM", "kabileshk702@gmail.com")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM_ADDRESS", "")
    monkeypatch.setattr(email_service_module.smtplib, "SMTP", _FakeSMTP)

    with pytest.raises(email_service_module.EmailDeliveryError) as exc_info:
        service._send_via_smtp(
            recipient_email="someone@example.com",
            subject="Test",
            text_body="Hello",
            html_body="<p>Hello</p>",
        )

    assert "Google App Password" in str(exc_info.value)


def test_gmail_app_password_spaces_are_removed_before_login(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmailService()
    captured: dict = {}

    class _FakeSMTP:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context=None) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            captured["username"] = username
            captured["password"] = password

        def send_message(self, message, from_addr=None, to_addrs=None) -> None:
            return None

    monkeypatch.setattr(email_service_module.settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service_module.settings, "SMTP_USER", "kabileshkofficial@gmail.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASS", "gnnw osso ygck yhbx")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(email_service_module.settings, "SMTP_USE_SSL", False)
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM", "kabileshkofficial@gmail.com")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM_ADDRESS", "")
    monkeypatch.setattr(email_service_module.smtplib, "SMTP", _FakeSMTP)

    service._send_via_smtp(
        recipient_email="someone@example.com",
        subject="Test",
        text_body="Hello",
        html_body="<p>Hello</p>",
    )

    assert captured["username"] == "kabileshkofficial@gmail.com"
    assert captured["password"] == "gnnwossoygckyhbx"


def test_test_email_raises_when_provider_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmailService()

    monkeypatch.setattr(email_service_module.settings, "EMAIL_PROVIDER", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_HOST", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USER", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASS", "")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM", "")
    monkeypatch.setattr(email_service_module.settings, "SENDGRID_API_KEY", "")

    with pytest.raises(email_service_module.EmailDeliveryError):
        service.send_test_email(
            recipient_email="someone@example.com",
            recipient_name="Alex",
        )


def test_unknown_email_provider_reports_supported_values(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmailService()

    monkeypatch.setattr(email_service_module.settings, "EMAIL_PROVIDER", "mailgun")
    monkeypatch.setattr(email_service_module.settings, "SMTP_HOST", "")
    monkeypatch.setattr(email_service_module.settings, "SENDGRID_API_KEY", "")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM", "sender@example.com")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM_ADDRESS", "")

    with pytest.raises(email_service_module.EmailDeliveryError) as exc_info:
        service.send_test_email(
            recipient_email="someone@example.com",
            recipient_name="Alex",
        )

    assert "Unknown EMAIL_PROVIDER 'mailgun'" in str(exc_info.value)
    assert "smtp" in str(exc_info.value)
    assert "sendgrid" in str(exc_info.value)


def test_smtp_username_requires_password(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EmailService()

    monkeypatch.setattr(email_service_module.settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email_service_module.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USER", "sender@example.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASS", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM", "sender@example.com")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM_ADDRESS", "")

    with pytest.raises(email_service_module.EmailDeliveryError) as exc_info:
        service.send_test_email(
            recipient_email="someone@example.com",
            recipient_name="Alex",
        )

    assert "SMTP password is required" in str(exc_info.value)


def test_delivery_status_auto_detects_smtp_when_provider_is_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = EmailService()

    monkeypatch.setattr(email_service_module.settings, "DEBUG", False)
    monkeypatch.setattr(email_service_module.settings, "EMAIL_PROVIDER", "")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM", "sender@example.com")
    monkeypatch.setattr(email_service_module.settings, "EMAIL_FROM_ADDRESS", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USER", "sender@example.com")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASS", "secret-password")
    monkeypatch.setattr(email_service_module.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_service_module.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(email_service_module.settings, "SENDGRID_API_KEY", "")

    status = service.get_delivery_status()

    assert status == {
        "configured_provider": None,
        "provider": "smtp",
        "delivery_mode": "email",
        "ready": True,
    }
    assert service.can_send_real_email() is True
