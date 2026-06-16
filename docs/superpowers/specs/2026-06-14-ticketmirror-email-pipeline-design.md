# TicketMirror — Reliability-Hardened Email Pipeline (Design)

Date: 2026-06-14
Status: Approved design, pending spec review

## Purpose

An internal, non-customer-facing platform that mirrors OTA booking emails from a
single dedicated Gmail inbox into a structured operational view. Staff use it to
see which products are booked on a given date, how many people attend each
time slot, and to adjust bookings — without logging into each provider portal.

It is a **mirror**, not the source of truth. Provider emails are the source of
truth; this system reflects them and keeps an audit trail of internal changes.

## Scope

Small internal tool, single Gmail inbox, low booking volume, run by a small team.

Providers in scope (email-based, no API): GetYourGuide (GYG), Klook, Viator,
Tiqets, Tripster, Alle, Travel Experience, Sputnik8, and direct bookings.

## Key decisions (from brainstorming)

- **UI goal: exact parity with the user's live Bookeo** (Sea Land Travel
  Agency, Bookeo Tours & Activities). The operational screens must mirror the
  real Bookeo screens and workflows, verified against the live account on
  2026-06-14. The repo already pursues this and its parity model matches the
  live account.
- **Channel: email-first.** No partner/supplier API access is available or
  realistically obtainable, so parsing provider confirmation emails is the
  universal channel. APIs may be layered in later per-provider if access appears.
- **Stack: Python / Django.** Best fit for email/HTML parsing plus a small CRUD
  UI, and it is what the existing repo already uses.
- **Foundation: build on the existing codebase.** Keep the per-provider parsers,
  the data model, and the operational UI. These are the valuable, expensive
  assets and they are reusable regardless of infrastructure.
- **Strip heavy infrastructure.** Remove Celery, Redis, Gmail Pub/Sub push, and
  the multi-container production stack. They add failure modes without adding
  value for a single-inbox internal tool.
- **Ingestion: poll Gmail every ~1 minute with a durable cursor.** This is both
  simpler and *more reliable* than push: after downtime the poller catches up
  from its last cursor; nothing is silently missed.
- **Database: PostgreSQL.**
- **Runtime: one always-on machine.** No public webhook required. A small VPS is
  an optional later move using the same code.

Rejected alternatives: n8n (replaces only the easy ingestion 20%, cannot build
the UI, adds a tool to maintain); no-code Zapier/Make→Sheets (cannot do reliable
per-provider parsing, upsert-on-update, or a capacity UI); real-time Pub/Sub
push (events lost during downtime, unnecessary for booking lead times).

## Bookeo parity — verified screen inventory (live, 2026-06-14)

Top navigation in the live account: **Home · Calendar · Customers · Marketing ·
Settings.** The mirror replicates the operational subset and drops the
sales/marketing side that does not apply to an email mirror.

- **Home** — two panels:
  - *Messages*: reverse-chronological feed of `New booking` / `Booking
    canceled` events (customer name, product, date/time, pax e.g. "4 adults").
    Filters: All / Unread / Mark all as read.
  - *Agenda*: per-slot list for the period showing `X booked, Y available`
    (and `blocked`). Period tabs: Today / 3 days / 7 days / Print.
- **Calendar** — daily product grid titled "Group tours – <date>":
  - Left: month date-picker + Navigation tree (e.g. Group tours, Boat).
  - Columns = products; cells = time slots showing `X booked, Y available`
    and `blocked`.
  - View toggles: Rows / Boxes / Cancelled. Color legend: No bookings / Some
    bookings / Fully booked / Blocked. Per-slot `+`. iCal / Print export.
- **Customers** — customer list/profiles (repo has detailed click-maps).
- **Settings** — product (Tours & Activities) and scheduling configuration
  (repo has detailed click-maps; product seeds mirror the live products).

Live products confirmed: GYG - 1 Hours, VIATOR 1 SAAT, VIATOR 2H, GYG - 2 SAAT
(SL-1), GYG - 2 SAAT SL-(2-3), NEW VIATOR 2H V2, NEW VIATOR 2H TRANSFER,
VIATOR/GYG OLD CITY, VIATOR/GYG TWO CONTINENTS. These match the repo seeds.

**Parity scope note:** since bookings arrive by email from OTAs (not direct
online sales), the Bookeo **Marketing** tab, the public booking page, payment
processing, and waivers are **out of scope** for the mirror. Parity targets the
operational views (Home, Calendar, Customers) and the product/scheduling
settings that drive capacity.

## Architecture

A single Django app organized as a **store-then-parse pipeline**.

```
Gmail inbox
  │  poll every ~1 min using a durable cursor (Gmail historyId / last message id)
  ▼
[1] STORE raw email, untouched, always           → ingestion.RawEmail
  │
  ▼
[2] PARSE per-provider (parser registry)
  │      ├─ fails / low confidence ─────────────▶ ReviewQueueItem (raw attached)
  ▼
[3] VALIDATE (date, traveler count, product all present?)
  │      ├─ fails ─────────────────────────────▶ ReviewQueueItem (raw attached)
  ▼
[4] UPSERT booking by (provider + booking reference)
        append BookingEvent (idempotent; modify updates, cancel cancels)
```

### Components and responsibilities

- **Gmail poller** (`manage.py` command run on a schedule): fetch messages newer
  than the stored cursor, hand each to ingestion, advance the cursor only after
  the raw email is durably stored. Idempotent on message id.
- **Raw store** (`ingestion.RawEmail`): persists the full raw email (headers,
  sender, body) before any parsing. Enables **replay**.
- **Parser registry** (`apps/ingestion/parsers/`): routes an email to the right
  provider parser (by sender / signature) and returns a structured result or a
  parse failure. Each parser is a small, independently testable unit.
- **Validation gate** (`ingestion.services`): asserts required fields are present
  and coherent before any write; otherwise routes to the review queue.
- **Upsert + audit** (`bookings.services`): matches on
  `provider + provider_booking_reference`, applies create/modify/cancel
  idempotently, and appends a `BookingEvent` instead of silent overwrite.
- **Review queue** (`bookings.ReviewQueueItem`): operational safety net for
  unparseable emails and unknown products, with the raw email shown.
- **Operational UI** (Django templates): daily view, per-slot capacity, audited
  booking edit, review queue.
- **Failure alert**: a daily summary ("N emails need attention") so silent
  failures surface within hours.

### Data model (existing, retained)

`Provider`, `TourActivity`, `ActivitySchedule`, `ActivityScheduleSlot`,
`ActivityScheduleException`, `ActivityPeopleRule`, `ProviderAlias`, `Booking`,
`BookingEvent`, `ReviewQueueItem`, `RawEmail`, `GmailSyncState`.

Product-name variance across providers is handled by `ProviderAlias` mapping a
provider's product name to a canonical `TourActivity`; an unrecognized name
routes the booking to the review queue rather than guessing.

## Reliability properties

1. **Replay.** Raw emails are always stored, so a fixed parser can be re-run over
   history. A provider format change becomes "fix parser, reprocess," not "lost
   bookings."
2. **Self-healing ingestion.** The durable poll cursor means downtime only delays
   ingestion; on restart the poller catches up. No reliance on undelivered push.
3. **Nothing silently lost.** Parse failures, low confidence, and unknown
   products all land in the review queue with the raw email attached, plus a
   daily alert.
4. **Idempotent, order-independent writes.** Reprocessing the same email is a
   no-op; out-of-order modify/cancel emails converge to the correct state.
5. **Validation before write.** Bookings missing a date, traveler count, or
   product are flagged, never written as partial garbage.

## User-facing requirements → coverage

| Requirement | Covered by |
|---|---|
| Internal, not customer-facing | Whole system; no public surface |
| Reservations received by email from many providers | Parser registry, per-provider parsers |
| Different products booked | `TourActivity` + scheduling model |
| Emails include traveler + booking info | Parsers → `Booking` fields |
| Same product, different provider names | `ProviderAlias` canonical mapping |
| One dedicated inbox | Single Gmail account, poller |
| Connect to Gmail | Gmail poller (API/IMAP) with cursor |
| Extract info from tickets | Parse step |
| Store all details incl. sender | `RawEmail` + `Booking` |
| See booked products for a date | Daily view |
| Change date / traveler count per booking | Audited override (`BookingEvent`) |
| People-per-slot visible | Capacity view on `ActivityScheduleSlot` |
| Trigger on every received email | 1-minute cursor-poll |
| Update a record when related email arrives | Upsert by provider + reference |

## Running it

- One always-on machine.
- PostgreSQL.
- App served by a simple WSGI server; the poller scheduled via cron or a Django
  scheduled command. No Redis, no Celery, no public webhook.
- Optional later: same code on a small VPS for off-network access.

## Implementation work (high level)

Because the goal is reliability and the existing code is currently unverified:

1. **Audit** what runs today: which commands work, what the parsers actually
   handle, current state of ingestion and UI.
2. **Strip infrastructure**: remove Celery, Redis, Gmail Pub/Sub push, and the
   multi-container prod stack. Wire the cursor-poll command as the single
   ingestion path.
3. **Harden the pipeline**: confirm and strengthen replay, review-queue, and
   validation paths with tests built on **real saved sample emails per
   provider**.
4. **Add the daily failure alert.**
5. **Document** the simplified run/deploy story.

## Out of scope (YAGNI)

- Customer-facing booking or payments.
- Bookeo Marketing tab, public booking page, and waivers (do not apply to an
  email mirror).
- Real-time sub-second triggering (Pub/Sub).
- Provider APIs (revisit later only if access becomes available).
- Multi-inbox support.
- Celery/Redis/distributed task processing.

## Resolved decisions (from spec review)

- **Gmail access:** keep the existing OAuth Gmail-API integration with a
  **read-only** scope for the poller; drop only the Pub/Sub push part and poll
  using a stored history cursor.
- **Failure alert:** **in-app banner / count** in the review queue (no outbound
  email). Can add an emailed daily summary later if needed.
