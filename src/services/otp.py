import asyncio
import hashlib
import hmac
import http.client
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models import PhoneOtpCode


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


async def _send_smsir_code(phone: str, code: str) -> None:
    settings = get_settings()
    template_id: int | str = settings.smsir_template_id
    if settings.smsir_template_id.isdigit():
        template_id = int(settings.smsir_template_id)

    payload = {
        "mobile": phone,
        "templateId": template_id,
        "parameters": [
            {
                "name": settings.smsir_code_parameter,
                "value": code,
            }
        ],
    }
    headers = {
        "Accept": "text/plain",
        "Content-Type": "application/json",
        "X-API-KEY": _require_ascii_header_value("SMSIR_API_KEY", settings.smsir_api_key),
    }
    url = f"{settings.smsir_api_url.rstrip('/')}/send/verify"
    try:
        status_code, response_text = await asyncio.to_thread(
            _post_smsir_verify,
            url,
            payload,
            headers,
            settings.smsir_timeout_seconds,
        )
    except (OSError, UnicodeError) as exc:
        raise OtpError(f"Could not call sms.ir: {exc}") from exc

    if status_code >= 400:
        raise OtpError(f"sms.ir rejected OTP request with status {status_code}.")

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise OtpError("sms.ir returned an invalid response body.") from exc

    if int(data.get("status", 0)) != 1:
        message = data.get("message") or "sms.ir did not accept OTP request."
        raise OtpError(f"sms.ir OTP failed: {message}")


def _post_smsir_verify(url: str, payload: dict, headers: dict, timeout_seconds: int) -> tuple[int, str]:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout_seconds)
    try:
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        response_body = response.read().decode("utf-8")
        return response.status, response_body
    finally:
        conn.close()


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
