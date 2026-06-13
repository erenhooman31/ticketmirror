import re

from .common import effective_message
from .direct import DirectParser
from .getyourguide import GetYourGuideParser
from .klook import KlookParser
from .sputnik8 import Sputnik8Parser
from .tiqets import TiqetsParser
from .tripster import TripsterParser
from .viator import ViatorParser

PROVIDER_PATTERNS = {
    "getyourguide": {
        "sender": [r"getyourguide", r"\bgyg\b"],
        "subject": [r"getyourguide", r"\bgyg\b"],
        "body": [r"GetYourGuide", r"\bGYG[A-Z0-9-]+\b"],
    },
    "viator": {
        "sender": [r"viator", r"tripadvisor"],
        "subject": [r"viator"],
        "body": [r"\bBR-[A-Z0-9-]+\b", r"Viator"],
    },
    "tiqets": {
        "sender": [r"tiqets"],
        "subject": [r"tiqets"],
        "body": [r"Tiqets", r"Order ID\s*[:#-]\s*\d{5,}"],
    },
    "tripster": {
        "sender": [r"tripster"],
        "subject": [r"tripster", r"Новый заказ"],
        "body": [r"Tripster", r"experience\.tripster", r"\bTS-[A-Z0-9-]+\b"],
    },
    "sputnik8": {
        "sender": [r"sputnik8"],
        "subject": [r"sputnik8", r"Новая бронь"],
        "body": [r"Sputnik8", r"\bSP8-[A-Z0-9-]+\b", r"Participants \(tickets\)"],
    },
    "klook": {
        "sender": [r"klook"],
        "subject": [r"klook"],
        "body": [r"Klook", r"\bKL[A-Z0-9-]*\d[A-Z0-9-]*\b"],
    },
    "direct": {
        "sender": [r"@example\.com", r"@internal\.local"],
        "subject": [r"direct booking", r"internal booking"],
        "body": [r"\bDIR-[A-Z0-9-]+\b"],
    },
}

_registry = {}


def register_parser(parser_class) -> None:
    _registry[parser_class.provider_code] = parser_class


def get_parser(provider_code: str):
    parser_class = _registry.get(provider_code)
    if parser_class is None:
        return None
    return parser_class()


def detect_provider(
    subject: str,
    sender: str,
    body_text: str,
) -> tuple[str | None, float]:
    effective_subject, effective_sender, _forwarded = effective_message(
        subject=subject,
        sender=sender,
        body_text=body_text,
    )
    candidates = []
    for provider_code, groups in PROVIDER_PATTERNS.items():
        score = 0
        if _matches_any(effective_sender, groups["sender"]):
            score += 0.5
        if _matches_any(effective_subject, groups["subject"]):
            score += 0.3
        if _matches_any(body_text, groups["body"]):
            score += 0.2
        if score:
            candidates.append((provider_code, round(min(score, 1), 2)))
    if not candidates:
        return None, 0
    return max(candidates, key=lambda item: item[1])


def parse_email(raw_email):
    provider_code, _confidence = detect_provider(
        raw_email.subject,
        raw_email.gmail_outer_sender,
        raw_email.body_text,
    )
    if not provider_code:
        provider_code = "direct"
    parser = get_parser(provider_code)
    if parser is None:
        raise ValueError(f"No parser registered for provider: {provider_code}")
    return parser.parse(raw_email)


def parse_by_provider(
    provider_code: str,
    subject: str,
    sender: str,
    body_text: str,
):
    parser = get_parser(provider_code)
    if parser is None:
        raise ValueError(f"No parser registered for provider: {provider_code}")
    return parser.parse_content(subject=subject, sender=sender, body_text=body_text)


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, value or "", re.IGNORECASE) for pattern in patterns)


for parser in (
    DirectParser,
    GetYourGuideParser,
    KlookParser,
    Sputnik8Parser,
    TiqetsParser,
    TripsterParser,
    ViatorParser,
):
    register_parser(parser)
