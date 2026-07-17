"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext, DragOverlay, PointerSensor, KeyboardSensor, useSensor, useSensors,
  type DragEndEvent, type DragStartEvent,
} from "@dnd-kit/core";
import { addDays, addMonths, startOfWeek, endOfWeek, startOfMonth, endOfMonth, format } from "date-fns";
import { appointmentsApi, patientsApi } from "@/lib/api/client";
import type { Appointment, Patient, NewAppointmentDraft, AppointmentType } from "@/lib/calendar/types";
import { buildWeekDays, resolveDragEnd, parseDraggableId, typeLabel, SLOT_MINUTES } from "@/lib/calendar/utils";
import { CalendarHeader, type CalendarView } from "@/components/calendar/calendar-header";
import { PatientPanel } from "@/components/calendar/patient-panel";
import { CalendarWeekView } from "@/components/calendar/calendar-week-view";
import { CalendarMonthView } from "@/components/calendar/calendar-month-view";
import { AppointmentDialog, type AppointmentSubmit } from "@/components/calendar/appointment-dialog";

function extractError(err: unknown): string {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Something went wrong";
}

export default function CalendarPage() {
  const qc = useQueryClient();
  const [view, setView] = useState<CalendarView>("week");
  const [anchor, setAnchor] = useState<Date>(new Date());
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<AppointmentType | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [draft, setDraft] = useState<NewAppointmentDraft | null>(null);
  const [editing, setEditing] = useState<Appointment | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  // Visible date range for the query.
  const [rangeStart, rangeEnd] = useMemo(() => {
    if (view === "month") return [startOfWeek(startOfMonth(anchor), { weekStartsOn: 1 }), endOfWeek(endOfMonth(anchor), { weekStartsOn: 1 })];
    if (view === "day") return [anchor, addDays(anchor, 1)];
    const ws = startOfWeek(anchor, { weekStartsOn: 1 });
    return [ws, addDays(ws, 7)];
  }, [view, anchor]);

  const rangeKey = `${rangeStart.toISOString()}_${rangeEnd.toISOString()}`;

  const { data: appointments = [] } = useQuery<Appointment[]>({
    queryKey: ["appointments", rangeKey, typeFilter],
    queryFn: () =>
      appointmentsApi
        .list({ start: rangeStart.toISOString(), end: rangeEnd.toISOString(), type: typeFilter ?? undefined })
        .then((r) => r.data),
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["patients"],
    queryFn: () => patientsApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (payload: AppointmentSubmit) => appointmentsApi.create(payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["appointments"] }); closeDialog(); },
    onError: (err) => setFormError(extractError(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<AppointmentSubmit> }) => appointmentsApi.update(id, payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["appointments"] }); closeDialog(); },
    onError: (err) => setFormError(extractError(err)),
  });

  const rescheduleMutation = useMutation({
    mutationFn: ({ id, start, end }: { id: number; start: Date; end: Date }) =>
      appointmentsApi.update(id, { start_at: start.toISOString(), end_at: end.toISOString() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
    onError: (err) => { alert(extractError(err)); qc.invalidateQueries({ queryKey: ["appointments"] }); },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  );

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const res = resolveDragEnd(String(event.active.id), event.over ? String(event.over.id) : null, appointments);
    if (!res) return;
    if (res.kind === "reschedule") {
      rescheduleMutation.mutate({ id: res.appointmentId, start: res.start, end: res.end });
    } else {
      setEditing(null);
      setDraft({ patientId: res.patientId, start: res.start, end: new Date(res.start.getTime() + SLOT_MINUTES * 60_000) });
      setFormError(null);
      setDialogOpen(true);
    }
  }

  function openNew() {
    const start = new Date(anchor); start.setHours(9, 0, 0, 0);
    setEditing(null);
    setDraft({ start, end: new Date(start.getTime() + SLOT_MINUTES * 60_000) });
    setFormError(null);
    setDialogOpen(true);
  }

  function openEdit(appt: Appointment) {
    setDraft(null);
    setEditing(appt);
    setFormError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setDraft(null);
    setFormError(null);
  }

  function onResizeEnd(appt: Appointment, newEnd: Date) {
    rescheduleMutation.mutate({ id: appt.id, start: new Date(appt.start_at), end: newEnd });
  }

  const step = (dir: 1 | -1) => {
    if (view === "month") setAnchor((a) => addMonths(a, dir));
    else if (view === "day") setAnchor((a) => addDays(a, dir));
    else setAnchor((a) => addDays(a, dir * 7));
  };

  const label =
    view === "month" ? format(anchor, "MMMM yyyy")
    : view === "day" ? format(anchor, "EEEE, MMM d, yyyy")
    : `${format(rangeStart, "MMM d")} – ${format(addDays(rangeStart, 6), "MMM d, yyyy")}`;

  const days = view === "day" ? [anchor] : buildWeekDays(anchor);

  // Drag preview content for the overlay.
  const active = activeId ? parseDraggableId(activeId) : null;
  const activePatient = active?.kind === "patient" ? patients.find((p) => p.id === active.id) : null;
  const activeAppt = active?.kind === "appt" ? appointments.find((a) => a.id === active.id) : null;

  return (
    <div className="flex flex-col h-full">
      <CalendarHeader
        view={view} onView={setView} label={label}
        onPrev={() => step(-1)} onNext={() => step(1)} onToday={() => setAnchor(new Date())}
        onNew={openNew} typeFilter={typeFilter} onTypeFilter={setTypeFilter}
      />
      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="flex flex-1 min-h-0">
          <PatientPanel patients={patients} search={search} onSearch={setSearch} />
          {view === "month" ? (
            <CalendarMonthView anchor={anchor} appointments={appointments} onOpen={openEdit} />
          ) : (
            <CalendarWeekView days={days} appointments={appointments} onOpen={openEdit} onResizeEnd={onResizeEnd} />
          )}
        </div>
        <DragOverlay>
          {activePatient && (
            <div className="rounded-lg border bg-card px-3 py-2 text-sm shadow-lg">{activePatient.full_name}</div>
          )}
          {activeAppt && (
            <div className="rounded-md border bg-card px-2 py-1 text-[11px] shadow-lg">
              {activeAppt.patient_name ?? "Patient"} · {typeLabel(activeAppt.appointment_type)}
            </div>
          )}
        </DragOverlay>
      </DndContext>

      <AppointmentDialog
        open={dialogOpen}
        onClose={closeDialog}
        patients={patients}
        draft={draft}
        editing={editing}
        isPending={createMutation.isPending || updateMutation.isPending}
        error={formError}
        onSubmit={(payload) => {
          setFormError(null);
          if (editing) updateMutation.mutate({ id: editing.id, payload });
          else createMutation.mutate(payload);
        }}
      />
    </div>
  );
}
