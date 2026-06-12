# Parsers

Provider parsers convert stable plain-text OTA email formats into normalized booking data.

## Current Structure

Parser files live under `apps/ingestion/parsers/`:

- `base.py`: parser interface and `ParsedBooking` DTO.
- `registry.py`: provider parser registry.
- `getyourguide.py`
- `klook.py`
- `sputnik8.py`
- `tiqets.py`
- `tripster.py`
- `viator.py`

The provider parser modules are placeholders until real provider samples and deterministic extraction rules are added.

## Parser Requirements

Parsers must be deterministic. Prefer explicit regular expressions, field labels, and provider-specific parsing logic over fuzzy matching.

Each parser should extract, when present:

- Provider code.
- Provider booking/reference number.
- Provider product name and product code.
- Service date.
- Time slot.
- Guest name, email, and phone.
- Party size.
- Booking status.
- Provider notes or special instructions.

Do not use traveler name as a unique identifier. Do not treat subject lines alone as reliable identifiers.

## Testing Requirements

Every parser change must include tests with representative email body fixtures. Tests should cover:

- New booking email.
- Update email.
- Cancellation email, when provider supports it.
- Missing optional fields.
- Unknown or changed product names.

Tests must assert normalized `ParsedBooking` output and booking upsert behavior where relevant.

## AI Extraction

AI extraction may only be introduced later as a fallback for exceptional cases. It must not be the primary parser path. If added, it must store enough metadata for review and must not auto-apply ambiguous results without safeguards.
