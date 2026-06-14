# Final Bookeo Gap Audit

Date: 2026-06-14

This audit compares the scoped Bookeo live inspection against the current TicketMirror implementation. Bookeo was treated as read-only: only navigation, opening cancelable dialogs, DOM inspection, and screenshots were used.

## Proof Set

Bookeo proof:
- `bookeo-home-redacted-2026-06-14.png`
- `bookeo-calendar-redacted-2026-06-14.png`
- `bookeo-customers-redacted-2026-06-14.png`
- `bookeo-settings-general-2026-06-14.png`
- `bookeo-settings-schedule-2026-06-14.png`
- `bookeo-settings-current-schedule-edit-dialog-2026-06-14.png`
- `bookeo-settings-schedule-copy-dialog-2026-06-14.png`
- `bookeo-settings-people-2026-06-14.png`

TicketMirror proof:
- `ticketmirror-home-2026-06-14.png`
- `ticketmirror-calendar-2026-06-14.png`
- `ticketmirror-customers-2026-06-14.png`
- `ticketmirror-inbox-2026-06-14.png`
- `ticketmirror-raw-email-2026-06-14.png`
- `ticketmirror-settings-tours-general-2026-06-14.png`
- `ticketmirror-settings-tours-schedule-2026-06-14.png`
- `ticketmirror-settings-current-schedule-edit-dialog-2026-06-14.png`
- `ticketmirror-settings-tours-schedule-copy-dialog-2026-06-14.png`
- `ticketmirror-settings-other-schedule-edit-dialog-2026-06-14.png`
- `ticketmirror-settings-tours-people-2026-06-14.png`
- `ticketmirror-users-roles-2026-06-14.png`

## Gap Table

| Area | Bookeo behavior | TicketMirror behavior | Severity | Required fix | Status |
| --- | --- | --- | --- | --- | --- |
| Primary navigation | Home, Calendar, Customers, Settings, with Bookeo account chrome. | Home, Calendar, Customers, Inbox, Settings. Inbox is TicketMirror-specific and required by scope. | Blocking | Add Inbox as a primary nav item while preserving the requested order. | Verified |
| Home message footer | Footer filters stay on Home and switch message filter state. | `All` incorrectly linked to Customers and `Unread` to Inbox. | Blocking | Keep `All` and `Unread` on Home with `messages=all/unread`. | Fixed and verified by `test_dashboard_message_footer_filters_stay_on_home`. |
| Home agenda and booking modal | Bookeo home shows operational messages and agenda-like upcoming items. Booking edits are made in modal-style operational context. | Dashboard renders Messages, Agenda, and booking modal with date, time, traveler count, status, attendance, and reason fields. | Blocking | Verify modal does not expose raw developer-only fields and booking edits create Messages entries. | Verified by browser proof and tests. |
| Calendar shell | Bookeo shows date navigation, Today, mini-calendar, navigation tree, search, rows/cards, canceled/manual state controls, capacity and slot drill-in. | TicketMirror Calendar has date nav, Today, mini calendar, search, category/activity/provider filters, canceled/manual review toggles, rows/cards, capacity, remaining, slot click, booking click, print/export. | Blocking | Preserve Bookeo-like control density and capacity math. | Verified by browser proof and tests. |
| Calendar canceled top control | Bookeo has top canceled control and side controls. | TicketMirror side checkbox is functional; top label is display-only. | Low | No change required for scoped completion because the functional canceled toggle is present and tested. | Verified accepted. |
| Customers search/list/detail | Bookeo customers has search, alphabet filter, paginated list, selected detail, email/phone links, booking history. | TicketMirror has search, alphabet filter, Bookeo-style count, customer directory/detail, booking table, and now email/phone contact links when values exist. | Medium | Add contact links in selected customer detail. | Fixed and verified by browser proof and customer test. |
| Customers pagination | Bookeo displays large-account pagination. | TicketMirror displays count for the current internal dataset. | Low | No change required for scoped MVP; pagination is only needed when the internal customer set grows beyond the current page size. | Verified accepted. |
| Settings General | Bookeo product General exposes name, code/visibility-style fields, nickname/display metadata, Save/Cancel. | TicketMirror General has name, internal display name, active/category/notes/display settings, provider alias creation, existing aliases, Save/Back. | Blocking | Keep Bookeo product structure while retaining TicketMirror mapping fields required for ingestion. | Verified by browser proof. |
| Settings Schedule current schedule | Bookeo shows current schedule weekly grid with add icons, slot edit dialog, copy days, bulk seat change. | TicketMirror shows weekly grid, add/edit slot links, slot edit dialog with day/start/seats/save/cancel/delete, copy days and bulk seats flows. | Blocking | Match fields and cancelable edit flow. | Verified by browser proof and tests. |
| Settings Schedule other schedules | Bookeo has other schedule table and a new/change copy dialog. Existing other schedule edit includes save/cancel/delete and copy-like behavior. | TicketMirror has other schedule table, copy-source dialog, existing schedule editor, and Copy action for existing schedules. | Blocking | Add Bookeo-scoped Copy action on existing other schedule editor. | Fixed and verified by `test_other_schedule_editor_can_copy_existing_schedule` and screenshot proof. |
| Settings Schedule duration | Bookeo has duration day/hour/minute controls. | TicketMirror has scoped duration controls for day/hour/minute and Save/Cancel. | Blocking | Preserve duration section in Schedule tab. | Verified by browser proof. |
| Settings People | Bookeo scoped People tab controls number of people per booking and capacity-related values. | TicketMirror People tab controls min/max people and assigned/default capacity. Hidden capacity note is preserved across scoped saves. | Blocking | Prevent scoped People save from erasing `capacity_note`. | Fixed and verified by `test_people_tab_preserves_capacity_note_when_scoped_form_omits_it`. |
| Inbox table and raw email | Bookeo has no Inbox equivalent; this is TicketMirror-specific scope. | Inbox lists parsed emails, missing/review states, provider/sender/subject/reference/product/date/pax/lead/status, raw view, reprocess, ignore. | Blocking | Ensure raw email view and admin review flows exist. | Verified by browser proof and tests. |
| Inbox ignore | Ignoring a raw email should close related review work. | Raw email was ignored, but related open `ReviewQueueItem`s stayed open. | Blocking | Mark related open review items ignored with resolver and timestamp. | Fixed and verified by `test_inbox_ignore_closes_related_review_items`. |
| Parser providers | Scope includes Alle and Travel Experience. | Parser registry includes Alle and Travel Experience, with sender/provider detection tightened. | Blocking | Add provider parsers and tests. | Verified by parser tests. |
| Booking statuses | Scope requires CLEAR, GELDI, GELMEDI, SONRA GELECEK attendance/status changes. | Booking edit includes attendance status with required values. | Blocking | Add field, migration, form/view/template support, and audit events. | Verified by tests. |
| Capacity | Bookeo seats drive remaining capacity; no-shows should not consume capacity. | TicketMirror capacity counts pending/manual review, excludes canceled/rejected/parse failed/duplicate and excludes `GELMEDI`. | Blocking | Update capacity service and tests. | Verified by tests. |
| Users & Roles | Bookeo account area supports staff/admin management. | TicketMirror Settings has Users & Roles with create user and role update controls gated to admin. | Blocking | Add scoped admin user creation and role management. | Verified by browser proof and tests. |

## Final Result

All scoped blocking gaps are fixed and verified. Remaining low-severity differences are accepted as out-of-scope for this MVP or covered by an equivalent functional control.
