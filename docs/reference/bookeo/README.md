# Bookeo-Inspired Feature References

This directory captures neutral functional observations from a live Bookeo operator session inspected on 2026-06-13. The purpose is to help plan TicketMirror operator features without copying Bookeo branding, visual design, wording, icons, CSS, layout, or trade dress.

Bookeo is reference material only. TicketMirror features must use TicketMirror terminology, data models, permission rules, audit behavior, and interface design.

## Files

- `screen-template.md`: reusable format for documenting a TicketMirror screen before implementation.
- `feature-backlog.md`: candidate TicketMirror features grouped by the observed functional area that inspired them.
- `workflows.md`: cross-screen operator and admin workflows with expected outcomes and acceptance direction.

## Observed Functional Areas

The opened Bookeo session exposed these areas:

- Operations home: recent event stream, booking-change messages, agenda, capacity counts, unread/all filters, day-range controls, and print.
- Schedule calendar: date picker, previous/next/today navigation, category and product grouping, search by customer or booking identifier, row/box display modes, canceled visibility, capacity blocks, new-booking entry points, print, and iCal export.
- Customer directory: customer search, alphabet filter, pagination, contact rows, new customer, merge, import, export, waiver search, and display preferences.
- Marketing and distribution tools: public booking entry links, promotions, vouchers, prepaid packages, referral/social growth tools, review collection, social media, distribution channels, outbound campaigns, abandoned-booking follow-up, customer account area, memberships, and conversion analytics.
- Administration settings: business profile, regional and localization settings, theme/layout controls, notifications, reminders, post-visit email, custom messages/terms, taxes, tours and activities, resources, closure periods, booking preferences, waiting lists, customer-detail requirements, waivers, pricing seasons, and third-party integrations.
- Account/help/session links: account settings, help, and sign out. These are noted only as navigation primitives; they are not TicketMirror feature commitments.

## Reference Rules

- Describe operator jobs and system behavior, not Bookeo visuals or copy.
- Do not preserve Bookeo product names, icons, colors, button text, screenshots, CSS, or layout proportions.
- Do not use real traveler names, emails, phone numbers, booking numbers, or voucher values.
- Convert observations into TicketMirror acceptance criteria before implementation.
- Prefer TicketMirror terms: booking, provider, product, activity, schedule, slot, capacity, review queue, raw email, parser event, audit event, operator, viewer, and admin.
- Treat public booking, payments, customer self-service, marketing automation, and third-party sync as out of scope unless explicitly selected.

## Implementation Gate

A reference item is ready to become an implementation task when it includes:

- Roles and permission boundaries.
- Data shown and source model or service.
- Filters, controls, and query behavior.
- Click behavior, navigation behavior, and non-JavaScript fallback where relevant.
- Empty, loading, success, error, and permission-denied states.
- Audit/logging requirements and masking requirements.
- Acceptance criteria that can be converted into tests.
