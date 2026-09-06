import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models import PhoneOtpCode


logger = logging.getLogger(__name__)


class OtpError(Exception):
    pass


class OtpRateLimitError(OtpError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("برای ارسال دوباره کد کمی صبر کن.")
        self.retry_after_seconds = retry_after_seconds


_OTP_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


@dataclass
class OtpRequestResult:
    phone: str
    expires_in_seconds: int
    resend_after_seconds: int
    provider: str
    mock_code: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_code(phone: str, code: str) -> str:
    settings = get_settings()
    secret = settings.admin_session_secret.encode("utf-8")
    message = f"{phone}:{code}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _generate_code() -> str:
    settings = get_settings()
    digits = max(4, min(settings.otp_code_digits, 8))
    upper_bound = 10**digits
    return f"{secrets.randbelow(upper_bound):0{digits}d}"


def normalize_otp_code(code: str) -> str:
    return code.translate(_OTP_DIGIT_TRANSLATION).strip()


def _require_ascii_header_value(name: str, value: str) -> str:
    try:
        value.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise OtpError(f"{name} must be the real sms.ir ASCII value from .env, not a placeholder.") from exc
    return value


def _latest_code(db: Session, phone: str) -> PhoneOtpCode | None:
    return db.scalars(
        select(PhoneOtpCode)
        .where(PhoneOtpCode.phone == phone)
        .order_by(PhoneOtpCode.created_at.desc(), PhoneOtpCode.id.desc())
        .limit(1)
    ).first()


async def _send_smsir_verify_template(
    phone: str,
    *,
    api_key: str,
    template_id: str,
    parameters: list[dict[str, str]],
    api_key_name: str,
    purpose: str,
) -> None:
    settings = get_settings()
    if not api_key.strip() or not template_id.strip():
        raise OtpError(f"sms.ir {purpose} configuration is incomplete.")

    normalized_template_id: int | str = template_id
    if template_id.isdigit():
        normalized_template_id = int(template_id)
    payload = {
        "mobile": phone,
        "templateId": normalized_template_id,
        "parameters": parameters,
    }
    headers = {
        "Accept": "text/plain",
        "Content-Type": "application/json",
        "X-API-KEY": _require_ascii_header_value(api_key_name, api_key),
    }
    url = f"{settings.smsir_api_url.rstrip('/')}/send/verify"
    try:
        status_code, response_text = await _post_smsir_verify(
            url,
            payload,
            headers,
            settings.smsir_timeout_seconds,
        )
    except (httpx.RequestError, UnicodeError, ValueError) as exc:
        raise OtpError(f"Could not call sms.ir: {exc}") from exc

    if status_code >= 400:
        raise OtpError(f"sms.ir rejected {purpose} with status {status_code}.")

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise OtpError("sms.ir returned an invalid response body.") from exc

    if int(data.get("status", 0)) != 1:
        message = data.get("message") or f"sms.ir did not accept {purpose}."
        raise OtpError(f"sms.ir {purpose} failed: {message}")


async def _send_smsir_code(phone: str, code: str) -> None:
    settings = get_settings()
    await _send_smsir_verify_template(
        phone,
        api_key=settings.smsir_api_key,
        template_id=settings.smsir_template_id,
        parameters=[
            {
                "name": settings.smsir_code_parameter,
                "value": code,
            }
        ],
        api_key_name="SMSIR_API_KEY",
        purpose="OTP request",
    )


async def send_welcome_sms(phone: str, full_name: str) -> bool:
    """Send the optional, templated welcome message without blocking sign-in."""
    settings = get_settings()
    if not settings.smsir_welcome_enabled:
        return False

    normalized_name = " ".join(full_name.split())
    if not normalized_name:
        logger.warning("Skipping welcome SMS because the new account has no display name.")
        return False

    try:
        await _send_smsir_verify_template(
            phone,
            api_key=settings.smsir_welcome_api_key,
            template_id=settings.smsir_welcome_template_id,
            parameters=[
                {
                    "name": settings.smsir_welcome_name_parameter,
                    "value": normalized_name,
                }
            ],
            api_key_name="SMSIR_WELCOME_API_KEY",
            purpose="welcome SMS",
        )
    except OtpError as exc:
        logger.warning(
            "Welcome sms.ir send failed for phone ending in %s: %s",
            phone[-4:],
            exc,
        )
        return False
    return True


async def _post_smsir_verify(
    url: str,
    payload: dict,
    headers: dict,
    timeout_seconds: int,
) -> tuple[int, str]:
    async with httpx.AsyncClient(timeout=timeout_seconds, trust_env=False) as client:
        response = await client.post(url, json=payload, headers=headers)
    return response.status_code, response.text


async def request_otp(db: Session, phone: str) -> OtpRequestResult:
    settings = get_settings()
    now = _now()
    latest = _latest_code(db, phone)
    if latest and latest.consumed_at is None:
        elapsed = int((now - _as_utc(latest.last_sent_at)).total_seconds())
        retry_after = settings.otp_resend_seconds - elapsed
        if retry_after > 0:
            raise OtpRateLimitError(retry_after)

    code = _generate_code()
    provider = "mock" if settings.otp_mock else "smsir"
    otp = PhoneOtpCode(
        phone=phone,
        code_hash=_hash_code(phone, code),
        provider=provider,
        expires_at=now + timedelta(minutes=settings.otp_expire_minutes),
        last_sent_at=now,
    )
    db.add(otp)
    db.commit()

    if not settings.otp_mock:
        try:
            await _send_smsir_code(phone, code)
        except OtpError:
            db.delete(otp)
            db.commit()
            raise

    return OtpRequestResult(
        phone=phone,
        expires_in_seconds=settings.otp_expire_minutes * 60,
        resend_after_seconds=settings.otp_resend_seconds,
        provider=provider,
        mock_code=code if settings.otp_mock else None,
    )


def verify_otp(db: Session, phone: str, code: str) -> bool:
    settings = get_settings()
    now = _now()
    otp = _latest_code(db, phone)
    if not otp or otp.consumed_at is not None:
        return False
    if _as_utc(otp.expires_at) < now:
        return False
    if otp.attempt_count >= settings.otp_max_attempts:
        return False

    otp.attempt_count += 1
    expected = _hash_code(phone, normalize_otp_code(code))
    if not hmac.compare_digest(otp.code_hash, expected):
        db.commit()
        return False

    otp.consumed_at = now
    db.commit()
    return True
