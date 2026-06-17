import logging
import re
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def contains_cyrillic(text: str | None) -> bool:
    return bool(text and CYRILLIC_RE.search(text))


def to_english(text: str | None) -> str:
    if not text:
        return ""
    if not getattr(settings, "TRANSLATE_ENABLED", True):
        return text
    if not contains_cyrillic(text):
        return text
    try:
        return _translate_text(text)
    except Exception:
        logger.exception("Offline RU->EN translation failed; using original text.")
        return text


def _translate_text(text: str) -> str:
    translation = _ru_en_translation()
    return translation.translate(text)


@lru_cache(maxsize=1)
def _ru_en_translation():
    try:
        import argostranslate.translate
    except ImportError as exc:
        raise RuntimeError("argostranslate is not installed") from exc

    from_language = None
    to_language = None
    for language in argostranslate.translate.get_installed_languages():
        if language.code == "ru":
            from_language = language
        elif language.code == "en":
            to_language = language

    if not from_language or not to_language:
        raise RuntimeError("Argos ru->en language package is not installed")

    translation = from_language.get_translation(to_language)
    if not translation:
        raise RuntimeError("Argos ru->en translation is unavailable")
    return translation
