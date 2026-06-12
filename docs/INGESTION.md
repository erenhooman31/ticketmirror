# Ingestion

Ingestion receives Gmail messages from one dedicated internal inbox and turns provider emails into mirrored bookings.

## Required Order

Raw emails must be stored before parsing. This preserves traceability when parsing fails, provider formats change, or operations needs to inspect the original message.

The expected flow is:

1. Fetch Gmail message metadata and body.
2. Store or update `RawEmail` by `gmail_message_id`.
3. Select a provider parser.
4. Parse deterministic fields from the plain text body.
5. Upsert a booking by `provider + provider_reference`.
6. Link the booking to the raw email.
7. Create booking events and review queue items when needed.

## Gmail Credentials

Do not commit real Gmail credentials. The integration must read credentials from environment variables:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_INBOX_LABEL`

The current Gmail module is scaffolding only. A production implementation should use least-privilege OAuth scopes and clear token rotation procedures.

## Error Handling

Parsing failures should update the raw email processing state and preserve the error. Ambiguous product mapping should create a review queue item rather than guessing.

Ingestion code should use database transactions around raw email state changes and booking upserts.

## Upsert Behavior

Incoming related emails must update existing bookings using provider and provider booking reference. Provider updates must create `BookingEvent` records.

Provider updates must not silently overwrite manual overrides. Future merge logic should explicitly decide whether a provider value is safe to apply, should be ignored, or should create a review item.
