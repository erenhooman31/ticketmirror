import logging
import re
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
translation_failure_count = 0
_missing_translation_package_warning_logged = False


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
    except Exception as exc:
        global translation_failure_count

        translation_failure_count += 1
        logger.exception(
            "Offline RU->EN translation failed; returning original text. "
            "error_type=%s text_length=%s failure_count=%s",
            type(exc).__name__,
            len(text),
            translation_failure_count,
        )
        return text


def _translate_text(text: str) -> str:
    translation = _ru_en_translation()
    return translation.translate(text)


@lru_cache(maxsize=1)
def _ru_en_translation():
    try:
        import argostranslate.translate
    except ImportError as exc:
        _warn_missing_translation_package("argostranslate is not installed")
        raise RuntimeError("argostranslate is not installed") from exc

    from_language = None
    to_language = None
    for language in argostranslate.translate.get_installed_languages():
        if language.code == "ru":
            from_language = language
        elif language.code == "en":
            to_language = language

    if not from_language or not to_language:
        _warn_missing_translation_package("Argos ru->en language package is missing")
        raise RuntimeError("Argos ru->en language package is not installed")

    translation = from_language.get_translation(to_language)
    if not translation:
        _warn_missing_translation_package("Argos ru->en translation is unavailable")
        raise RuntimeError("Argos ru->en translation is unavailable")
    return translation


def _warn_missing_translation_package(reason: str) -> None:
    global _missing_translation_package_warning_logged

    if _missing_translation_package_warning_logged:
        return
    _missing_translation_package_warning_logged = True
    logger.warning(
        "Offline RU->EN translation package unavailable; Russian text will remain "
        "untranslated until the package is installed. reason=%s",
        reason,
    )
