# Calendar Scheduling with Drag-and-Drop — Design Spec

**Date:** 2026-07-16
**Branch:** `feature/calendar-scheduling-dragdrop`
**Status:** Approved design → ready for implementation plan

## Summary

Port the **calendar view + scheduling + drag-and-drop + hover** capability from
[FieldServicePro](https://github.com/patriottechsys/FieldServicePro.git) (a Flask/Jinja HVAC
field-service app) into **Dhanvantari** (Next.js 16 + FastAPI Ayurvedic EMR), so a doctor can
schedule patient appointments on a calendar with drag-to-book, drag-to-reschedule, resize, and
hover tooltips.

**This is a re-implementation, not a copy-paste.** FieldServicePro's calendar is server-rendered
Jinja + vanilla JS driving **FullCalendar 6**. Dhanvantari is a React/shadcn SPA. To keep
Dhanvantari's UI identical, the feature is **rebuilt natively** on the tools already in
Dhanvantari's stack (`@dnd-kit`, `date-fns`, shadcn/ui, Tailwind 4) — **FullCalendar is deliberately
not introduced**, because its own DOM/CSS would clash with the app's design language.

## Domain mapping (FieldServicePro → Dhanvantari)

| FieldServicePro | Dhanvantari | Notes |
|---|---|---|
| `Job` (schedulable entity) | **`Appointment`** | New model |
| `Technician` (assigned resource) | *dropped* | Single-doctor calendar; the logged-in `Practitioner` is the owner |
| `Client` | **`Patient`** | Existing model |
| `Division` → event color | **Appointment type** → event color | consultation / follow_up / therapy / panchakarma |
| Unassigned-jobs left panel | **Patient side-panel** | Drag a patient card onto a slot to book |

### Decisions (confirmed with user)

1. **Single doctor's own calendar** — matches the existing tenant model (`Practitioner` is the tenant
   root; patients belong to one practitioner). No staff/resource layer.
2. **Both booking modes** — click/drag an empty slot **and** drag a patient card from a side panel.
3. **Color by appointment type**, using the Ayurvedic palette tokens.
4. **All four "missing" enhancements** are in scope: double-booking prevention, full status workflow,
   patient email reminders, link to care plan/therapy.

## Scope / non-goals

- **In scope:** appointment CRUD, calendar Day/Week/Month views, drag-to-book, drag-to-reschedule,
  resize, hover tooltip, overlap prevention, status workflow, email reminders, plan/therapy linking.
- **Non-goals:** multi-practitioner lanes / resource timeline; recurring appointments (FieldServicePro's
  separate `RecurringSchedule` feature is **not** ported); patient-facing self-booking; SMS reminders;
  calendar sync (Google/iCal). These can be follow-on specs.

## Backend design (FastAPI — existing layered conventions, no new layers)

The backend is intentionally layered (not hexagonal) per project convention — schemas stay inline in
route modules, logic stays in async handlers, no `services/` layer.

### New model — `backend/app/models/appointment.py`

`class Appointment` (SQLAlchemy 2.0 typed style, mirrors `followup.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `practitioner_id` | `int` FK → `practitioners.id` | not null, indexed — tenant scope |
| `patient_id` | `int` FK → `patients.id` | not null, indexed |
| `start_at` | `DateTime(timezone=True)` | not null |
| `end_at` | `DateTime(timezone=True)` | not null |
| `appointment_type` | `Enum(AppointmentType)` | default `consultation` — drives calendar color |
| `status` | `Enum(AppointmentStatus)` | default `scheduled` |
| `reason` | `str \| None` | chief complaint / visit reason |
| `notes` | `str \| None` | |
| `location` | `str \| None` | free text (clinic / telehealth / room) |
| `plan_id` | `int \| None` FK → `consultation_plans.id` | link to care plan |
| `therapy_id` | `int \| None` FK → `therapies.id` | link to a therapy |
| `reminder_sent_at` | `DateTime(timezone=True) \| None` | |
| `created_at` / `updated_at` | `DateTime(timezone=True)` | `default`/`onupdate` = `now(utc)` |

Enums (Python `str, enum.Enum`, mapped via `Enum as SAEnum`):

- `AppointmentType`: `consultation`, `follow_up`, `therapy`, `panchakarma`
- `AppointmentStatus`: `scheduled`, `confirmed`, `completed`, `cancelled`, `no_show`

Relationships:

- `Appointment.patient` / `Appointment.practitioner` (`back_populates`)
- **Additive** to existing models: `Patient.appointments` and `Practitioner.appointments`
  (`lazy="dynamic"`, `cascade="all, delete-orphan"` on the patient side) — the only change to
  existing model files.

Register in `backend/app/models/__init__.py`: `from app.models.appointment import Appointment`
(+ add to `__all__`).

### Migration — `backend/alembic/versions/0011_appointments.py`

Hand-authored (matching existing style): `revision="0011"`, `down_revision="0010"`.
`op.create_table("appointments", ...)` with int PK, FKs (`practitioner_id`, `patient_id`,
`plan_id` nullable, `therapy_id` nullable), timezone-aware datetimes, enum types, indexes on
`practitioner_id`, `patient_id`, `start_at`. `downgrade()` drops the table and the two enum types
(`DROP TYPE IF EXISTS appointmenttype / appointmentstatus`).

### Routes — `backend/app/api/routes/appointments.py`

`router = APIRouter()` (no prefix — set at registration). Inline Pydantic v2 schemas
(`AppointmentCreate`, `AppointmentUpdate` with all-optional fields) + a module-level
`_appt_dict(obj) -> dict` serializer (isoformat datetimes, coalesce). Every handler is `async`,
injects `practitioner: Practitioner = Depends(get_current_practitioner)` and
`db: AsyncSession = Depends(get_db)`, and scopes all queries by
`Appointment.practitioner_id == practitioner.id`. Handlers use `await db.flush()` (not commit).

| Method | Path | Behavior |
|---|---|---|
| `GET` | `""` | List in a `[start, end)` window (calendar feed). Query params `start`, `end` (ISO), optional `status`, `type`, `patient_id`. Returns `list[_appt_dict]`, ordered by `start_at`. |
| `POST` | `""` (201) | Create. Validates patient belongs to practitioner. **Overlap check → `409`** if it collides with another non-`cancelled`/non-`no_show` appointment. Fires confirmation email if configured. Returns `{id, message}`. |
| `GET` | `/{id}` | Single appointment (`_appt_dict`). |
| `PATCH` | `/{id}` | Partial update from `model_dump(exclude_none=True)`. **Reschedule = patch `start_at`/`end_at`** (re-runs overlap check, excluding self). Also status change / edit / reassign. |
| `DELETE` | `/{id}` (204) | Hard delete. (Soft cancel is available via `PATCH status=cancelled`.) |
| `POST` | `/{id}/send-reminder` | Manually email the patient a reminder; stamps `reminder_sent_at`. |

**Overlap helper:** `_has_conflict(db, practitioner_id, start, end, exclude_id=None)` — selects
appointments for the practitioner where `status NOT IN (cancelled, no_show)` and the ranges overlap
(`existing.start_at < end AND existing.end_at > start`), excluding `exclude_id`. On conflict, raise
`HTTPException(409, detail="This time slot overlaps an existing appointment.")`.

**Email:** add `send_appointment_reminder(patient_name, email, practitioner_name, start_at, ...)` to
`backend/app/core/email.py`, following `send_followup_reminder`'s shape (guarded by
`settings.RESEND_API_KEY` — silently no-ops when unset). Called on create (confirmation) and by
`/send-reminder`.

**Registration in `backend/app/main.py`:** add `appointments` to the combined import on line 13 and
`app.include_router(appointments.router, prefix="/api/appointments", tags=["appointments"])` in the
router block.

## Frontend design (Next.js App Router + shadcn — looks 100% native)

**No FullCalendar, no new UI dependency.** The calendar is composed from existing primitives
(`rounded-xl border bg-card` cards, shadcn `Button/Dialog/Input/Select/Textarea/Badge`), the
existing `@dnd-kit` sensor pattern (from `sortable-assignment-list.tsx`), and `date-fns`. All colors
use existing semantic tokens (saffron `--primary`, forest `--sidebar`, `chart-1..5`, dosha colors) —
**no raw hex** for structural UI.

### New files (existing pages untouched)

| File | Responsibility |
|---|---|
| `src/app/(dashboard)/calendar/page.tsx` | Container: view/date state, filters, React Query queries + mutations, one `DndContext`, page layout. `"use client"`. |
| `src/components/calendar/calendar-header.tsx` | Day/Week/Month segmented switcher, prev/next/today nav, current-range title, "New appointment" button, type/status filter chips. |
| `src/components/calendar/calendar-week-view.tsx` | Time-grid week **and** day view (6am–8pm, 30-min slots, now-line, Mon–Fri shading). Day columns, droppable slots, positioned appointment blocks with side-by-side overlap layout. |
| `src/components/calendar/calendar-month-view.tsx` | Month day-grid; appointment chips per day; droppable day cells. |
| `src/components/calendar/appointment-block.tsx` | One event: colored by type, draggable + bottom resize handle, `onMouseEnter/Leave` → tooltip, click → edit dialog. |
| `src/components/calendar/appointment-tooltip.tsx` | Custom hover tooltip (patient · type · status · time · reason · "View patient →"), positioned via `getBoundingClientRect` like FieldServicePro. |
| `src/components/calendar/patient-panel.tsx` | Searchable left panel of draggable patient cards. |
| `src/components/calendar/appointment-dialog.tsx` | Create/edit form (patient, type, date, start/end or duration, reason, notes, link plan/therapy, status). shadcn `Dialog`. |
| `src/lib/calendar/utils.ts` | Pure helpers: week-days builder, slot list, time→pixel position/height, overlap side-by-side layout, snap-to-slot, `onDragEnd` resolution, type→token color map. |
| `src/lib/calendar/types.ts` | `Appointment`, `AppointmentType`, `AppointmentStatus` TS types (shared across calendar components). |

### Edits to existing frontend files (additive)

- `src/lib/api/client.ts`: add `appointmentsApi = { list, get, create, update, remove, sendReminder }`
  (arrow methods returning the axios promise, matching `followupsApi`).
- `src/app/(dashboard)/layout.tsx`: add `{ href: "/calendar", label: "Appointments", icon: CalendarDays }`
  to the `NAV` array + import `CalendarDays` from `lucide-react` (distinct from `CalendarCheck` used by
  Follow-ups).

### Layout

```
┌──────────────────────────────────────────────────────────┐
│ Appointments      [Day|Week|Month]  ‹ Today ›   [+ New]   │  ← header
├───────────┬──────────────────────────────────────────────┤
│ Patients  │  Mon   Tue   Wed   Thu   Fri   Sat   Sun      │
│ [search]  │ 6am ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░      │
│ ▸ Asha P. │ 7am ░░░░░░░░ ┌────────┐ ░░░░░░░░░░░░░░         │
│ ▸ Ravi K. │ 8am ░░░░░░░░ │Asha P. │ ← drag to reschedule  │
│ ▸ Meera…  │ 9am ░░░░░░░░ │Consult │   hover → tooltip      │
│ (drag →)  │10am ░░░░░░░░ └────────┘                        │
└───────────┴──────────────────────────────────────────────┘
```

### Drag-and-drop + hover mechanics (@dnd-kit)

- One page-level `DndContext` with `PointerSensor` (`activationConstraint: { distance: 5 }`) +
  `KeyboardSensor` — the same sensor setup as the existing sortable list.
- **Droppables:** each time slot (week/day) / day cell (month) is a `useDroppable` whose id encodes
  the target datetime, e.g. `slot:2026-07-16T09:30`.
- **Draggables:** patient cards (`patient:<id>`) and appointment blocks (`appt:<id>`) via
  `useDraggable`.
- **`onDragEnd`** (extracted to a pure function in `utils.ts` for unit testing):
  - `patient → slot` ⇒ open create dialog prefilled with patient + snapped start + default duration.
  - `appt → slot` ⇒ PATCH reschedule preserving duration (optimistic update; invalidate
    `["appointments"]`; on `409` revert + inline error).
- **Resize:** bottom handle on each block; pointer-drag adjusts `end_at` in slot increments; PATCH on
  release.
- **Hover tooltip:** `onMouseEnter/Leave` on a block toggles `appointment-tooltip`, positioned to the
  right of the block via `getBoundingClientRect`.

### Color-by-type mapping (Ayurvedic tokens)

`consultation` → primary/saffron tone; `follow_up` → accent/sage green; `therapy` → a `chart-*`
earthy tone; `panchakarma` → deeper terracotta/amber. Defined as a `type → { bg, border, text, dot }`
class map in `utils.ts`, using existing tokens only. Status is shown as a small badge/indicator on the
block (not color): `cancelled` renders muted + struck-through, `no_show` dashed, `completed` muted,
`confirmed` solid.

### Feedback / notifications

No toast library (the app has none). Follow existing conventions: form/mutation errors → inline banner
`text-destructive bg-destructive/10 rounded-lg px-3 py-2`; success → `invalidateQueries` + close dialog;
pending → disable button + swap label. The `409` overlap error surfaces as the dialog banner (on
create/edit) or a brief inline message + drag-revert (on drag reschedule).

### React Query wiring

- `appointmentsApi.list({ start, end, ...filters })` → `useQuery<Appointment[]>` with
  `queryKey: ["appointments", rangeKey, filters]`.
- `patientsApi.list()` → `useQuery` for the panel + dialog select.
- Create / update / delete / sendReminder → `useMutation` with `onSuccess` invalidating
  `["appointments"]` (+ closing dialog / resetting form). `staleTime` inherits the app default (30s).

## Testing

- **Backend (pytest, `backend/tests/`):** appointment create/list/patch/delete; overlap → `409`;
  overlap ignores `cancelled`/`no_show`; multi-tenant isolation (practitioner A cannot see/patch B's);
  status transitions; reschedule via PATCH re-checks overlap excluding self; reminder endpoint no-ops
  cleanly when `RESEND_API_KEY` unset.
- **Frontend (vitest + Testing Library):** `utils.ts` pure helpers — time→pixel positioning, overlap
  side-by-side layout, snap-to-slot, and `onDragEnd` resolution (patient→slot opens create; appt→slot
  reschedules with preserved duration); a render smoke test of the calendar page.
- Drag-drop is exercised through the extracted pure `onDragEnd`/layout functions rather than brittle
  DOM drag simulation.

## UI-sameness guarantee

The change is **additive**. The only edits to existing files are: `NAV` (+1 entry), `client.ts`
(+1 exported object), `models/__init__.py` + `main.py` (registration), `core/email.py` (+1 function),
and one relationship each on `Patient` / `Practitioner`. No existing page, component, style, or token
is modified. Every new surface uses the app's existing design system.

## Build sequence (for the implementation plan)

1. Backend model + enums + `Patient`/`Practitioner` relationships + `__init__` registration.
2. Alembic migration `0011_appointments.py`.
3. Routes (CRUD + overlap + reminder) + `main.py` registration + `email.py` helper.
4. Backend tests.
5. Frontend: `types.ts`, `utils.ts`, `appointmentsApi`, nav entry.
6. Calendar components (header → week/day view → month view → block → tooltip → patient panel → dialog).
7. Page container wiring (DndContext, queries, mutations).
8. Frontend tests.
9. End-to-end verification in the running app.
