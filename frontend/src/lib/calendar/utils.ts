import { addDays, startOfWeek } from "date-fns";
import type { Appointment, AppointmentType, AppointmentStatus, DragResolution } from "./types";

export const SLOT_MIN_MINUTES = 6 * 60;   // 06:00
export const SLOT_MAX_MINUTES = 20 * 60;  // 20:00
export const SLOT_MINUTES = 30;
export const SLOT_PX = 28;                // height of one 30-min slot

export function buildWeekDays(anchor: Date): Date[] {
  const monday = startOfWeek(anchor, { weekStartsOn: 1 });
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
}

export function buildTimeSlots(): { minutes: number; label: string }[] {
  const slots: { minutes: number; label: string }[] = [];
  for (let m = SLOT_MIN_MINUTES; m < SLOT_MAX_MINUTES; m += SLOT_MINUTES) {
    const h = Math.floor(m / 60);
    const min = m % 60;
    const ampm = h < 12 ? "am" : "pm";
    const h12 = h % 12 === 0 ? 12 : h % 12;
    slots.push({ minutes: m, label: min === 0 ? `${h12}${ampm}` : `${h12}:${String(min).padStart(2, "0")}` });
  }
  return slots;
}

export function minutesSinceMidnight(d: Date): number {
  return d.getHours() * 60 + d.getMinutes();
}

export function positionForRange(start: Date, end: Date): { top: number; height: number } {
  const startMin = Math.max(minutesSinceMidnight(start), SLOT_MIN_MINUTES);
  const endMin = Math.min(minutesSinceMidnight(end), SLOT_MAX_MINUTES);
  const top = ((startMin - SLOT_MIN_MINUTES) / SLOT_MINUTES) * SLOT_PX;
  const height = Math.max(((endMin - startMin) / SLOT_MINUTES) * SLOT_PX, SLOT_PX * 0.6);
  return { top, height };
}

export interface LaidOutAppointment {
  appt: Appointment;
  column: number;
  columns: number;
}

// Greedy interval-graph column assignment for a single day's appointments.
export function layoutDay(appts: Appointment[]): LaidOutAppointment[] {
  const sorted = [...appts].sort(
    (a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()
  );
  const result: LaidOutAppointment[] = [];
  let cluster: Appointment[] = [];
  let clusterEnd = -Infinity;

  const flush = () => {
    if (cluster.length === 0) return;
    const colEnd: number[] = []; // last end-time per column
    const assign = new Map<number, number>();
    for (const a of cluster) {
      const s = new Date(a.start_at).getTime();
      let col = colEnd.findIndex((e) => e <= s);
      if (col === -1) { col = colEnd.length; colEnd.push(0); }
      colEnd[col] = new Date(a.end_at).getTime();
      assign.set(a.id, col);
    }
    const columns = colEnd.length;
    for (const a of cluster) result.push({ appt: a, column: assign.get(a.id)!, columns });
    cluster = [];
    clusterEnd = -Infinity;
  };

  for (const a of sorted) {
    const s = new Date(a.start_at).getTime();
    if (s >= clusterEnd && cluster.length > 0) flush();
    cluster.push(a);
    clusterEnd = Math.max(clusterEnd, new Date(a.end_at).getTime());
  }
  flush();
  return result;
}

export function snapToSlot(date: Date): Date {
  const snapped = new Date(date);
  snapped.setMinutes(Math.floor(snapped.getMinutes() / SLOT_MINUTES) * SLOT_MINUTES, 0, 0);
  return snapped;
}

export function slotId(date: Date): string {
  return `slot:${date.toISOString()}`;
}

export function parseSlotId(id: string): Date | null {
  if (!id.startsWith("slot:")) return null;
  const d = new Date(id.slice(5));
  return isNaN(d.getTime()) ? null : d;
}

export function draggableId(kind: "patient" | "appt", id: number): string {
  return `${kind}:${id}`;
}

export function parseDraggableId(id: string): { kind: "patient" | "appt"; id: number } | null {
  const [kind, raw] = id.split(":");
  if ((kind === "patient" || kind === "appt") && raw) return { kind, id: Number(raw) };
  return null;
}

export function resolveDragEnd(
  activeId: string,
  overId: string | null,
  appts: Appointment[]
): DragResolution | null {
  if (!overId) return null;
  const slot = parseSlotId(overId);
  const active = parseDraggableId(activeId);
  if (!slot || !active) return null;

  if (active.kind === "patient") {
    return { kind: "book", patientId: active.id, start: slot };
  }
  const appt = appts.find((a) => a.id === active.id);
  if (!appt) return null;
  const durationMs = new Date(appt.end_at).getTime() - new Date(appt.start_at).getTime();
  return { kind: "reschedule", appointmentId: appt.id, start: slot, end: new Date(slot.getTime() + durationMs) };
}

// ── Presentation helpers ────────────────────────────────────────────────────

export function typeColor(type: AppointmentType): { block: string; accent: string; dot: string } {
  switch (type) {
    case "consultation": return { block: "bg-chart-1/15 text-foreground", accent: "border-l-chart-1", dot: "bg-chart-1" };
    case "follow_up":    return { block: "bg-chart-2/15 text-foreground", accent: "border-l-chart-2", dot: "bg-chart-2" };
    case "therapy":      return { block: "bg-chart-4/15 text-foreground", accent: "border-l-chart-4", dot: "bg-chart-4" };
    case "panchakarma":  return { block: "bg-chart-3/15 text-foreground", accent: "border-l-chart-3", dot: "bg-chart-3" };
  }
}

export function statusBlockClass(status: AppointmentStatus): string {
  switch (status) {
    case "cancelled": return "opacity-50 line-through";
    case "no_show":   return "opacity-60 border-dashed";
    case "completed": return "opacity-75";
    default:          return "";
  }
}

export function typeLabel(type: AppointmentType): string {
  return { consultation: "Consultation", follow_up: "Follow-up", therapy: "Therapy", panchakarma: "Panchakarma" }[type];
}

export function statusLabel(status: AppointmentStatus): string {
  return { scheduled: "Scheduled", confirmed: "Confirmed", completed: "Completed", cancelled: "Cancelled", no_show: "No-show" }[status];
}

export function formatTimeRange(start: Date, end: Date): string {
  const fmt = (d: Date) => d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return `${fmt(start)} – ${fmt(end)}`;
}
