# Database

PostgreSQL is the production and local Docker database. SQLite is only used for tests when configured through `TEST_DATABASE_URL`.

## Main Model Groups

Accounts:

- `UserProfile`: one-to-one profile for the Django user with role values `admin`, `operator`, and `viewer`.

Bookings:

- `Provider`: OTA/provider identity such as Viator or Klook.
- `Product`: canonical internal product.
- `ProductVariant`: internal variant or time-slot-specific product option.
- `ProductAlias`: maps provider product names/codes to canonical products and variants.
- `CapacityRule`: date, weekday, and slot capacity override for a product variant.
- `Booking`: mirrored booking record keyed by provider and provider booking reference.
- `BookingEvent`: audit trail for creation, provider updates, manual overrides, status changes, and review conditions.
- `ReviewQueueItem`: operational queue for unmapped or ambiguous ingestion results.

Ingestion:

- `RawEmail`: stored Gmail message body, metadata, provider link, and processing state.
- `GmailSyncState`: Gmail mailbox history/watch state.

## Identity Rules

Bookings must be identified by `provider + provider_booking_reference`.

Do not use traveler name as a unique identifier. Do not infer identity from guest name, email subject, party size, or product name.

## Provider Values And Internal Values

Keep original provider data available through raw emails and provider-prefixed booking fields. Keep active internal values on booking fields used by operations.

Manual edits must update `Booking.manual_override_fields` and create `BookingEvent` records. Provider updates must create `BookingEvent` records and must not silently erase manual corrections.

## Capacity Rules

Capacity reporting should count confirmed active bookings separately from pending bookings:

- Confirmed bookings consume capacity.
- Pending bookings should be visible as pending demand.
- Cancelled, rejected, parse-failed, and duplicate-ignored records should not consume future operational capacity unless a later explicit rule says otherwise.

## Migration Rules

Every model change requires a migration. Migrations should be committed with the code that uses them. Do not edit applied migrations in a shared branch unless the team has explicitly agreed that the migration is not yet used anywhere.
