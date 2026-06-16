# Bookeo History Import

`import_bookeo_history` imports historical bookings from the operator's own
Bookeo account into TicketMirror. It does not import customers separately:
TicketMirror's Customers view is derived from `Booking.lead_traveler_*`, so
imported bookings populate customer history automatically.

## Prerequisites

- Run migrations.
- Run `python manage.py seed_bookeo_products` first so the 12 Bookeo products
  and approved `bookeo` `ProviderAlias` rows exist.
- Set credentials before the Bookeo account is cancelled:

```bash
set BOOKEO_API_KEY=...
set BOOKEO_SECRET_KEY=...
```

## Command

```bash
python manage.py import_bookeo_history --from 2024-05-19 --to 2027-06-17
```

Useful options:

- `--dry-run`: fetches and classifies records without writing bookings, events,
  reviews, or checkpoint state.
- `--state-file PATH`: resume checkpoint path. Default:
  `.bookeo_history_import_state.json`.
- `--items-per-page 100`: Bookeo's maximum page size.
- `--throttle-seconds 0.25`: delay between requests. Increase this if Bookeo
  returns HTTP 429.

## Bookeo API Usage

The importer calls `https://api.bookeo.com/v2`:

- `GET /bookings` with `beginDate`, `endDate`, `itemsPerPage=100`,
  `expandParticipants=true`, and `expandCustomer=true`.
- `GET /bookings/{bookingNumber}` when a list payload lacks expanded customer or
  participant data.

Authentication is sent on every request with `X-Bookeo-apiKey` and
`X-Bookeo-secretKey`. The import walks event-date windows of at most 31 days,
then follows Bookeo pagination with `pageNavigationToken` and `pageNumber`.
HTTP 429 and transient 5xx responses are retried with exponential backoff; 429
honors Bookeo's `Retry-After` header.

## Field Mapping

- Bookeo `bookingNumber` is stored as the identity only when no underlying OTA
  reference is found.
- If Bookeo notes/custom fields contain an OTA provider and OTA booking
  reference, the booking identity becomes `provider + OTA reference`, and the
  Bookeo number is stored in `provider_order_reference` as `Bookeo <number>`.
  This matches the email ingestion identity rule and prevents duplicate bookings.
- Event start maps to `provider_travel_date` and `provider_start_time`.
- Participants map to `provider_traveler_count`, `traveler_names`, and
  `ticket_breakdown`.
- Expanded customer data maps to lead traveler name, email, phone, and language.
- Bookeo status maps cancelled/rejected/confirmed/modified/pending states to
  TicketMirror `Booking.status`.
- Raw Bookeo JSON is stored in a system `BookingEvent` with event type
  `bookeo_history_import`.

## Safety

The import is idempotent and resumable. It uses the same
`provider + provider_booking_reference` key as existing bookings. Re-running an
unchanged import creates no duplicate bookings and no duplicate import events.

Manual overrides are respected: fields listed in `manual_override_fields` are
not overwritten on re-import. Unmapped products leave `activity` and
`schedule_slot` empty and create an open `PROVIDER_ALIAS_MISSING` review item.

## Runtime And Resume

Expect one `GET /bookings` request per 31-day event-date window plus additional
page requests for busy periods. With the default 0.25 second throttle, two years
of low-volume data usually takes minutes; increase the throttle if Bookeo asks
for slower traffic.

If the command is interrupted, rerun the same command. Completed windows are
skipped and an interrupted paginated window resumes from the stored page token.

## Limitations

- Bookeo fields not exposed by the API cannot be imported.
- Product mapping depends on approved `bookeo` aliases from
  `seed_bookeo_products`; unmapped or renamed Bookeo products require review.
- This is a one-way historical import. It does not set up ongoing webhooks or
  live synchronization.
