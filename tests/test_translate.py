from types import SimpleNamespace

from django.test import override_settings

from apps.ingestion.parsers.alle import AlleParser
from apps.ingestion.translate import contains_cyrillic, to_english


def test_contains_cyrillic_detects_russian_text():
    assert contains_cyrillic("Новый заказ")
    assert not contains_cyrillic("New order")


@override_settings(TRANSLATE_ENABLED=True)
def test_to_english_uses_stubbed_translator_for_cyrillic(monkeypatch):
    monkeypatch.setattr(
        "apps.ingestion.translate._translate_text",
        lambda text: "New order" if "Новый" in text else text,
    )

    assert to_english("Новый заказ") == "New order"
    assert to_english("Already English") == "Already English"


@override_settings(TRANSLATE_ENABLED=True)
def test_to_english_translation_failure_returns_original(monkeypatch, caplog):
    def fail(_text):
        raise RuntimeError("model missing")

    monkeypatch.setattr("apps.ingestion.translate._translate_text", fail)

    assert to_english("Новый заказ") == "Новый заказ"
    assert "Offline RU->EN translation failed" in caplog.text


@override_settings(TRANSLATE_ENABLED=False)
def test_to_english_disabled_returns_original(monkeypatch):
    def fail(_text):
        raise AssertionError("translator should not be called")

    monkeypatch.setattr("apps.ingestion.translate._translate_text", fail)

    assert to_english("Новый заказ") == "Новый заказ"


def _stub_translation(original, translated):
    return original, translated


@override_settings(TRANSLATE_ENABLED=True)
def test_parser_runs_on_translated_subject_and_body(monkeypatch):
    translations = dict(
        [
            _stub_translation(
                "Alle бронирование ALLE-RU-1",
                "Alle booking: ALLE-RU-1",
            ),
            _stub_translation(
                "\n".join(
                    [
                        "Экскурсия: Морская прогулка",
                        "Дата: 2026-06-17",
                        "Время: 14:00",
                        "Участники: 2",
                        "Клиент: Tatyana K.",
                    ]
                ),
                "\n".join(
                    [
                        "Product: Bosphorus Boat Cruise with Audio Guide",
                        "Date: 2026-06-17",
                        "Time: 14:00",
                        "Participants: 2",
                        "Customer: Tatyana K.",
                    ]
                ),
            ),
        ]
    )
    monkeypatch.setattr(
        "apps.ingestion.translate._translate_text",
        lambda text: translations[text],
    )
    raw_email = SimpleNamespace(
        subject="Alle бронирование ALLE-RU-1",
        gmail_outer_sender="bookings@alletravel.example",
        original_forwarded_sender=None,
        body_text="\n".join(
            [
                "Экскурсия: Морская прогулка",
                "Дата: 2026-06-17",
                "Время: 14:00",
                "Участники: 2",
                "Клиент: Tatyana K.",
            ]
        ),
    )

    parsed = AlleParser().parse(raw_email)

    assert parsed.provider_booking_reference == "ALLE-RU-1"
    assert parsed.raw_product_name == "Bosphorus Boat Cruise with Audio Guide"
    assert parsed.travel_date.isoformat() == "2026-06-17"
    assert parsed.start_time.isoformat() == "14:00:00"
    assert parsed.traveler_count == 2
    assert parsed.lead_traveler_name == "Tatyana K."
    assert parsed.raw_fields["translation_applied"] is True
    assert parsed.raw_fields["translated_subject"] == "Alle booking: ALLE-RU-1"
