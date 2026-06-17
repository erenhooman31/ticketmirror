# Ingestion

Ingestion polls one dedicated internal Gmail inbox and turns provider emails into mirrored bookings.

## Required Order

Raw emails must be stored before parsing. This preserves traceability when parsing fails, provider formats change, or operations needs to inspect the original message.

The expected flow is:

1. Fetch Gmail message metadata and body.
2. Store or update `RawEmail` by `gmail_message_id`.
3. Select a provider parser.
4. Parse deterministic fields from the plain text body.
5. Upsert a booking by underlying OTA identity across channels, then by provider and provider booking reference.
6. Link the booking to the raw email.
7. Create booking events and review queue items when needed.

`poll_gmail_once()` is the scheduled ingestion entrypoint. It uses `GmailSyncState.latest_history_id`, stores every fetched message before parsing, and advances the cursor only after the raw email storage step succeeds. Duplicate Gmail messages are deduplicated by `RawEmail.gmail_message_id`.

`process_gmail_message(message_data)` remains available for normalized Gmail payloads. `process_raw_email(raw_email_id)` detects the provider, selects the registered deterministic parser, and calls `upsert_booking_from_parsed()`.

## Gmail Credentials

Do not commit real Gmail credentials. The integration reads credentials from environment variables:

- `GMAIL_MAILBOX`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_INBOX_LABEL`

Use an OAuth refresh token with read-only Gmail access. Tests mock Gmail responses; no real Google credentials are required.

## Gmail Polling

Run one cycle:

```bash
python manage.py poll_gmail
```

Run continuously:

```bash
python manage.py poll_gmail --loop --interval 60
```

Production compose runs the continuous poller as its own service. After downtime, the poller catches up from Gmail history. If the stored history ID has expired, it falls back to a date-bounded recent-message list and resumes from the newest stored message history ID.

`GmailSyncState` stores the latest processed history ID per mailbox plus a short-lived poll lock. The lock prevents overlapping poller processes from double-processing the same cycle.

## Error Handling

Parsing failures update the raw email processing state and preserve the error. Ambiguous provider alias mapping creates a review queue item rather than guessing.

Ingestion code uses transactions around raw email state changes and booking upserts. Pending raw emails can be retried with:

```bash
python manage.py process_pending_emails
```

Unexpected pending-email processing failures create parser-error review queue items.

`python manage.py repair_parsed_booking_display_fields` is a safe repair command for already stored raw emails. By default it scans only `pending`, `needs_review`, and `failed` rows, bounded to 500 emails. It supports `--status`, `--since`, `--limit`, and `--quiet`. Per-row parser failures mark that `RawEmail` as `failed`, create a review item, continue the loop, and the command exits successfully.

If a parser cannot find `provider_booking_reference`, ingestion must not create a normal booking. The raw email is marked `needs_review` and a `reference_missing` review item is created.

Low-confidence parses may create or update a booking when a reference exists, but the raw email remains in review and a `low_confidence_parse` review item is opened.

## Upsert Behavior

Incoming related emails first resolve by underlying OTA identity across any channel. If no OTA identity match exists, ingestion falls back to provider plus provider booking reference.

Bookeo transition behavior is conservative: a Bookeo-only provisional booking can be promoted to the direct OTA identity when a later email supplies the OTA reference or when the direct OTA email matches the provisional booking on lead traveler, date, time, traveler count, and product context. The merge updates the existing booking identity and appends a booking event; it does not delete raw emails or manual edit history.

Provider updates must not silently overwrite manual overrides. The merge rules are:

- New bookings copy parsed provider fields into both provider fields and active operational fields.
- Existing bookings update provider fields.
- Active date, time, slot type, traveler count, and status are updated only when the corresponding active field is not listed in `manual_override_fields`.
- If a provider update differs from a manually overridden active field, ingestion creates a `manual_override_conflict` review item and a `conflict_detected` booking event.
- Cancellation emails set status to `cancelled` unless `status` is manually overridden.
- Capacity-impacting traveler count changes are recorded in the update event old/new values.

Provider alias matching is deliberately conservative:

1. Approved alias by provider product code and option code.
2. Approved alias by exact raw product and option names.
3. Case-insensitive exact raw product and option name suggestions.
4. Fuzzy suggestions only for review.

If no approved alias is matched, ingestion still stores the booking when a reference exists, but opens a `provider_alias_missing` review item.
