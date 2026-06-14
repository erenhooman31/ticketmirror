# Bookeo Customers Click Map

Inspection date: 2026-06-14

Source: authenticated Bookeo Customers at `cust_viewCustomers.html`.

Local screenshot saved at `docs/reference/bookeo/screenshots/bookeo-customers-2026-06-14.png`.
This image is not intended for commit because it contains real customer contact data.

No Bookeo mutations were submitted. Import, export, merge, save, delete, and sign-out actions were not clicked.

## Structure

Bookeo Customers is a dense directory page:

- search row with placeholder `Customer name or email address`
- alphabet filter row: `All a b c ... z`
- pagination: `1 - 50 of 43645`
- previous/next page controls
- two-column customer directory

Each customer cell shows:

- initials or short name marker
- customer/profile icon
- display name
- email as a `mailto:` link
- phone as a `callto:` link when present

The inspected page contained real customer contact data. TicketMirror documentation intentionally records the structure and field mapping, not a full committed PII export.

## Click Behavior

Controls inspected:

- Search field: accepts customer name or email.
- Alphabet filters: filter by initial.
- Pagination arrows: navigate result pages.
- Customer cells: open customer profile/detail.
- Email link: opens mail client via `mailto:`.
- Phone link: opens phone handler via `callto:`.

Skipped:

- Import/export/merge workflows: external or destructive/bulk data actions.
- Customer profile save/delete actions: mutating.
- Password or account-public-booking fields: outside TicketMirror scope.

## TicketMirror Mapping

TicketMirror Customers now uses booking-backed customer records because the app does not yet have a separate durable Customer model.

Implemented fields:

- display name from `Booking.lead_traveler_name`
- email from `Booking.lead_traveler_email`
- phone from `Booking.lead_traveler_phone`
- language from `Booking.language`
- booking history
- provider booking reference
- product/activity
- service date
- party size
- booking status

Directory behavior implemented:

- search by customer/contact/reference/product/provider data
- alphabet filter
- two-column customer directory with initials, name, email, phone
- selected customer details
- booking history rows linking to booking detail

## Neutral Field Map

| Bookeo visible field/control | TicketMirror source |
| --- | --- |
| Customer name | `Booking.lead_traveler_name` |
| Customer email | `Booking.lead_traveler_email` |
| Customer phone | `Booking.lead_traveler_phone` |
| Booking history | grouped `Booking` records |
| Booking reference | `Booking.provider_booking_reference` |
| Product/activity | `Booking.raw_product_name` or linked `TourActivity` |
| Service date/time | `Booking.active_travel_date`, `active_start_time` |
| Party size | `Booking.active_traveler_count` |
| Status | `Booking.status` display label |

Deferred intentionally:

- customer import/export
- profile merge
- customer notes/flags/approval policy
- participant profile merge
- addresses, gender, birth date, waiver metadata, membership
- customer password import

Reason: these are either outside the scoped operational mirror or require a separate privacy/audit design before committing real customer PII into TicketMirror.
