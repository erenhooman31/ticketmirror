CANONICAL_PROVIDER_LABELS = {
    "bookeo": "Bookeo",
    "getyourguide": "GetYourGuide",
    "viator": "Viator",
    "klook": "Klook",
    "tiqets": "Tiqets",
    "tripster": "Tripster",
    "sputnik8": "Sputnik8",
    "alle": "Alle",
    "travel-experience": "Travel Experience",
    "direct": "Sea Land / Direct",
}


def provider_display_name(provider_code: str) -> str:
    return CANONICAL_PROVIDER_LABELS.get(
        provider_code,
        provider_code.replace("-", " ").title(),
    )
