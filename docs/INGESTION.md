# Ingestion

Ingestion receives Gmail messages from one dedicated internal inbox and turns provider emails into mirrored bookings.

## Required Order

Raw emails must be stored before parsing. This preserves traceability when parsing fails, provider formats change, or operations needs to inspect the original message.

The expected flow is:

1. Fetch Gmail message metadata and body.
2. Store or update `RawEmail` by `gmail_message_id`.
3. Select a provider parser.
4. Parse deterministic fields from the plain text body.
5. Upsert a booking by `provider + provider_booking_reference`.
6. Link the booking to the raw email.
7. Create booking events and review queue items when needed.

`process_gmail_message(message_data)` is the entrypoint for Gmail payloads. It
stores or updates `RawEmail` by `gmail_message_id` before parsing. If the same
message has already been processed, the duplicate is ignored and no extra
booking event is created.

`process_raw_email(raw_email_id)` detects the provider, selects the registered
deterministic parser, and calls `upsert_booking_from_parsed()`.

## Gmail Credentials

Do not commit real Gmail credentials. The integration must read credentials from environment variables:

- `GMAIL_MAILBOX`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_PUBSUB_TOPIC`
- `GMAIL_WEBHOOK_AUDIENCE`
- `GOOGLE_CLOUD_PROJECT`

The Gmail client uses OAuth refresh-token placeholders from the environment and
normalizes Gmail API messages into the payload shape required by `RawEmail`.
Tests mock Gmail responses; no real Google credentials are required.

## Gmail Setup Flow

1. Create or choose the dedicated Gmail mailbox used for provider booking mail.
2. Create a Google Cloud project and Pub/Sub topic for Gmail push notifications.
3. Configure OAuth credentials with the least-privilege Gmail scopes needed to
   read messages, history, and manage the mailbox watch.
4. Store the mailbox address, OAuth client ID, client secret, refresh token,
   Pub/Sub topic, webhook audience placeholder, and project ID as environment
   variables. Do not commit real values.
5. Deploy the application endpoint at `/ingestion/gmail/webhook/`.
6. Run `python manage.py setup_gmail_watch` to register the Gmail watch.
7. Run `python manage.py sync_recent_gmail --limit 100` after initial setup or
   after an outage to queue recent messages for reconciliation.
8. Run `python manage.py process_pending_emails` to retry raw emails that were
   stored but not parsed.

The webhook accepts Pub/Sub-style JSON, decodes `message.data`, minimally
validates `emailAddress` and `historyId`, queues `process_gmail_notification`,
and returns immediately.

`GmailSyncState` stores the latest processed history ID and watch expiration per
mailbox. Notification processing lists Gmail history since the stored history
ID, queues individual message fetches, and updates the sync state after
successful enqueueing.

## Error Handling

Parsing failures should update the raw email processing state and preserve the error. Ambiguous product mapping should create a review queue item rather than guessing.

Ingestion code should use database transactions around raw email state changes and booking upserts.

Celery retries Gmail notification processing and message fetches with backoff.
Duplicate Gmail messages are deduplicated by `RawEmail.gmail_message_id`. Pending
raw emails can be retried with `process_pending_raw_emails`, and unexpected
pending-email processing failures create parser-error review queue items.

If a parser cannot find `provider_booking_reference`, ingestion must not create
a normal booking. The raw email is marked `needs_review` and a
`reference_missing` review item is created.

Low-confidence parses may create or update a booking when a reference exists,
but the booking is marked `manual_review` and a `low_confidence_parse` review
item is opened.

## Upsert Behavior

Incoming related emails must update existing bookings using provider and provider booking reference. Provider updates must create `BookingEvent` records.

Provider updates must not silently overwrite manual overrides. Future merge logic should explicitly decide whether a provider value is safe to apply, should be ignored, or should create a review item.

The merge rules are:

- New bookings copy parsed provider fields into both provider fields and active operational fields.
- Existing bookings always update provider fields.
- Active date, time, slot type, traveler count, and status are updated only when the corresponding active field is not listed in `manual_override_fields`.
- If a provider update differs from a manually overridden active field, ingestion creates a `manual_override_conflict` review item and a `conflict_detected` booking event.
- Cancellation emails set status to `cancelled` unless `status` is manually overridden.
- Capacity-impacting traveler count changes are recorded in the update event old/new values.

Product alias matching is deliberately conservative:

1. Approved alias by provider product code and option code.
2. Approved alias by exact raw product and option names.
3. Case-insensitive exact raw product and option name suggestions.
4. Fuzzy suggestions only for review.

If no approved alias is matched, ingestion still stores the booking when a
reference exists, but opens a `product_alias_missing` review item.
