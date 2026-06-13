# Bookeo Product Inspection Summary

Inspected date: 2026-06-13

These notes use Bookeo as a functional reference only. Do not copy Bookeo branding, exact UI copy, layout, icons, visual design, CSS, or trade dress into TicketMirror.

| Product | Suggested canonical product | Variant | Slot type | Current schedule times | Other schedule times | Capacity rule found | Needs clarification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR | Bosphorus Cruise | 2-hour Viator alias | fixed_time | 11:00, 14:00, 19:00 | Seasonal rows visible; times not expanded | 250 seats per slot | Confirm future-season times |
| 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR | Bosphorus Cruise | 2-hour Viator alias V2 | fixed_time | 11:00, 14:00, 19:00 | Seasonal rows visible; times not expanded | 250 seats per slot | Confirm alias relationship with first Viator product |
| 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER | Bosphorus Cruise | 2-hour Viator transfer | fixed_time | 11:00, 14:00, 19:00 | Historical seasonal rows visible; times not expanded | 250 seats per slot | Confirm pickup timing and shared capacity |
| 2 Hours Bosphorus Tour SL-1 | Bosphorus Cruise | 2-hour GYG SL-1 | fixed_time | 11:00 | Default season row visible; times not expanded | 250 seats per slot | Confirm meaning of SL-1 |
| GYG 2 Hours Bosphorus Tour SL-(2-3) | Bosphorus Cruise | 2-hour GYG SL-2-3 | fixed_time | 14:00, 19:00 | Seasonal rows visible; times not expanded | 250 seats per slot | Confirm split from SL-1 |
| Istanbul Old City And Bosphorus Tour | Istanbul Old City and Bosphorus Tour | Viator alias | half_day | 8:30 | Default season row visible; times not expanded | 50 seats per slot | Confirm duration and shared inventory |
| Istanbul Two Continents Tour By Bus And Bosphorus Cruise | Istanbul Two Continents Tour | Viator alias | full_day | 8:15 | Default season row visible; times not expanded | 50 seats per slot | Confirm duration |
| Istanbul Old City And Bosphorus Tour - GYG | Istanbul Old City and Bosphorus Tour | GYG alias | half_day | 8:15 | Default season row visible; times not expanded | 50 seats per slot | Confirm why time differs from Viator alias |
| Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG | Istanbul Two Continents Tour | GYG alias | full_day | 8:15 | No rows captured | 50 seats per slot | Confirm shared inventory with Viator alias |
| 1 Hours Bosphorus Tour viator | Bosphorus Cruise | 1-hour Viator alias | fixed_time | 17:00 | No rows captured | 250 seats per slot | Confirm one-hour shared capacity |
| 1 Hours Bosphorus Tour GYG | Bosphorus Cruise | 1-hour GYG alias | fixed_time | 17:00 | No rows captured | 250 seats per slot | Confirm shared capacity with Viator alias |
| gyg yacht | Yacht Experience | GYG yacht | private_group | No fixed slots visible | No rows captured | Not visible | Confirm capacity, duration, and scheduling model |

## High-Level Observations

- The Bosphorus cruise products appear to be provider aliases and operational variants around 1-hour and 2-hour fixed departures.
- The transfer product should likely be a variant under the same cruise canonical product, but pickup timing was not visible in the inspected schedule area.
- Old City and Two Continents tours appear to be separate canonical products with smaller 50-seat capacity.
- GYG and Viator products often appear to be provider aliases rather than separate canonical products.
- The yacht product did not expose the same fixed-slot scheduling grid and should be handled separately after manual confirmation.
