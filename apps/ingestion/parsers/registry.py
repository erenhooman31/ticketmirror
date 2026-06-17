import re

from .alle import AlleParser
from .bookeo import BookeoParser
from .common import effective_message
from .direct import DirectParser
from .getyourguide import GetYourGuideParser
from .klook import KlookParser
from .sputnik8 import Sputnik8Parser
from .tiqets import TiqetsParser
from .travel_experience import TravelExperienceParser
from .tripster import TripsterParser
from .viator import ViatorParser

PROVIDER_PATTERNS = {
    "bookeo": {
        "sender": [r"noreply@bookeo\.com", r"\bbookeo\b"],
        "subject": [
            r"New booking\s+-",
            r"Booking canceled\s+-",
            r"Booking cancelled\s+-",
            r"Booking changed\s+-",
        ],
        "body": [r"Booking details", r"powered by Bookeo", r"Booking number\s*:"],
    },
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
    "alle": {
        "sender": [r"\balle\b", r"alletravel"],
        "subject": [r"\balle\b"],
        "body": [r"\bAlle\b", r"\bALLE-[A-Z0-9-]+\b"],
    },
    "travel-experience": {
        "sender": [r"travel[-_. ]?experience"],
        "subject": [r"travel experience"],
        "body": [r"Travel Experience", r"\bTE-[A-Z0-9-]+\b"],
    },
    "direct": {
        "sender": [r"@example\.com", r"@internal\.local"],
        "subject": [r"direct booking", r"internal booking"],
        "body": [r"\bDIR-[A-Z0-9-]+\b"],
    },
}

RELAXED_BODY_MARKERS = {
    "bookeo": [r"Booking details", r"powered by Bookeo", r"Booking number\s*:"],
    "getyourguide": [r"GetYourGuide", r"\bGYG[A-Z0-9-]+\b"],
    "viator": [r"Viator", r"Tripadvisor"],
    "tiqets": [r"Tiqets"],
    "tripster": [r"Tripster", r"experience\.tripster"],
    "sputnik8": [r"Sputnik8", r"Participants \(tickets\)"],
    "klook": [r"Klook"],
    "alle": [r"\bAlle\b"],
    "travel-experience": [r"Travel Experience"],
    "direct": [r"\bDIR-[A-Z0-9-]+\b"],
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
        sender_matches = _matches_any(effective_sender, groups["sender"])
        subject_matches = _matches_any(effective_subject, groups["subject"])
        body_matches = _matches_any(body_text, groups["body"])
        relaxed_body_matches = _matches_any(
            body_text,
            RELAXED_BODY_MARKERS.get(provider_code, groups["body"]),
        )
        if sender_matches:
            score += 0.5
        if subject_matches:
            score += 0.3
        if body_matches:
            score += 0.2
        if not _is_acceptable_candidate(
            sender_matches=sender_matches,
            subject_matches=subject_matches,
            body_matches=body_matches,
            relaxed_body_matches=relaxed_body_matches,
        ):
            continue
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


def _is_acceptable_candidate(
    *,
    sender_matches: bool,
    subject_matches: bool,
    body_matches: bool,
    relaxed_body_matches: bool,
) -> bool:
    if sender_matches:
        return True
    return subject_matches and body_matches and relaxed_body_matches


for parser in (
    AlleParser,
    BookeoParser,
    DirectParser,
    GetYourGuideParser,
    KlookParser,
    Sputnik8Parser,
    TiqetsParser,
    TravelExperienceParser,
    TripsterParser,
    ViatorParser,
):
    register_parser(parser)
