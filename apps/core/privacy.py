import re

EMAIL_RE = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")


def mask_email(value: str) -> str:
    local, _separator, domain = value.partition("@")
    if not domain:
        return "[email]"
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 4:
        return "[phone]"
    return f"[phone ending {digits[-4:]}]"


def mask_contact_text(value: str | None, *, limit: int = 500) -> str:
    if not value:
        return ""
    masked = EMAIL_RE.sub(lambda match: mask_email(match.group(0)), value)
    masked = PHONE_RE.sub(lambda match: mask_phone(match.group(0)), masked)
    if len(masked) > limit:
        return f"{masked[:limit]}..."
    return masked
