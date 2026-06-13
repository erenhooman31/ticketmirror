# Architecture

ticketmirror is a server-rendered Django application for internal operations teams. It mirrors reservations from OTA provider emails and presents bookings by date, product, variant, and time slot.

## System Shape

The MVP is a Django monolith with a PostgreSQL database, Redis, and Celery:

- Django handles admin, dashboard pages, CSV exports, and business services.
- PostgreSQL stores raw emails, parsed bookings, provider mappings, internal operational fields, audit events, and review queue items.
- Redis is used as the Celery broker and result backend.
- Celery runs background ingestion tasks such as fetching Gmail messages.

There is no separate frontend application. Normal user workflows should use Django templates, with role-restricted configuration inside Settings. Django admin is reserved for emergency superuser or developer access.

## Data Flow

1. Celery fetches messages from the dedicated Gmail inbox.
2. The raw message is stored in `ingestion.RawEmail`.
3. A provider-specific parser converts raw email text into a normalized parsed booking object.
4. The upsert service finds or creates the booking by provider and provider booking reference.
5. Product aliases map provider product names to canonical internal products and variants.
6. Ambiguous mappings create review queue items.
7. Every create, provider update, manual edit, or review condition creates a booking event.

## Boundaries

Provider data and internal operational data must remain distinct. Provider payloads and raw email bodies support traceability. Active internal fields support operations, manual corrections, capacity reporting, and CSV exports.

Provider updates must not silently overwrite manual overrides. Any future merge policy should explicitly compare provider values, internal active values, and manual override history.

## Internal Roles

The initial role model is stored on `accounts.UserProfile`:

- `admin`: full internal administration.
- `operator`: operational booking review and editing.
- `viewer`: read-only internal access.

Role enforcement should be added at view and admin action boundaries as features expand.
