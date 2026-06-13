# Parsers

Provider parsers convert stable plain-text OTA email formats into normalized booking data.

## Current Structure

Parser files live under `apps/ingestion/parsers/`:

- `base.py`: parser interface and `ParsedBooking` DTO.
- `common.py`: shared deterministic helpers for whitespace, dates, times, money, forwarded headers, and confidence.
- `registry.py`: provider parser registry.
- `direct.py`
- `getyourguide.py`
- `klook.py`
- `sputnik8.py`
- `tiqets.py`
- `tripster.py`
- `viator.py`

The provider parser modules use regular expressions and labeled-field parsing. They are intentionally deterministic and do not call external AI services.

## Parser Requirements

Parsers must be deterministic. Prefer explicit regular expressions, field labels, and provider-specific parsing logic over fuzzy matching.

Each parser should extract, when present:

- Provider code.
- Provider booking/reference number.
- Provider order reference.
- Event type.
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

Provider confidence is high only when provider, booking reference, travel date, product name, and traveler count are found. Missing references should produce manual-review output rather than an exception.

## Provider Assumptions

The parser fixtures include anonymized examples derived from real provider
templates. Names, emails, phone numbers, and references are fake but preserve the
provider label structure.

### GetYourGuide

- New booking emails may be forwarded through the internal Gmail inbox.
- The booking reference appears under `Reference number` on the next line.
- Product name can appear as the first text line after a non-logo image block.
- Service date and start time appear together under the service `Date` block,
  while the forwarded email header also has a `Date:` line. The parser prefers
  the service block.
- Participant count may appear as a group product, for example `Group up to 10
  (9 Persons)`. The parser counts the actual persons value, not the unit count.

### Tiqets

- New booking emails use `Reference ID`, `Visit date`, `Time`, and ticket-count
  labels such as `Adult 4`.
- Product name appears after `Selected language`.
- The order number in the subject and body is treated as both provider booking
  reference and provider order reference when no separate order field exists.

### Viator

- Booking confirmation and urgent request templates use a `Booking Details`
  section.
- `Booking Reference`, `Tour Name`, `Travel Date`, `Travelers`, `Product Code`,
  `Tour Option` or `Tour Grade`, `Tour Grade Code`, `Tour Language`, `Meeting
  Point`, and `Special Requirements` are parsed explicitly.
- Urgent request subjects are classified as booking requests rather than
  confirmed bookings.

### Tripster

- Russian new-order templates can carry the reference in the subject as `№`.
- The product name can appear inside Russian quotation marks in the subject.
- Russian month names in the subject are mapped deterministically.
- The year is inferred from a year present in the forwarded headers/body; if a
  year is not present, parser output should be treated as needing review before
  operational use.

### Sputnik8

- Russian booking templates can carry the order number in the subject after
  `заказ`.
- The product name can appear inside quotes in the subject.
- `Date and time` and `Participants (tickets)` are supported when present in the
  body.
- Russian month names in the subject are mapped deterministically.

### Klook

- Klook remains conservative until anonymized real samples are added.
- Missing reference, date, or traveler count should produce manual-review output
  instead of raising parser exceptions.

## AI Extraction

AI extraction may only be introduced later as a fallback for exceptional cases. It must not be the primary parser path. If added, it must store enough metadata for review and must not auto-apply ambiguous results without safeguards.
