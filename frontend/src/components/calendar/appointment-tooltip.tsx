"use client";

import { User, Stethoscope, MapPin, ArrowUpRight } from "lucide-react";
import type { Appointment } from "@/lib/calendar/types";
import { typeLabel, statusLabel, formatTimeRange } from "@/lib/calendar/utils";

export function AppointmentTooltip({ appt, x, y }: { appt: Appointment; x: number; y: number }) {
  return (
    <div
      className="fixed z-[9999] max-w-[280px] rounded-lg border bg-card p-3 text-xs shadow-xl pointer-events-none"
      style={{ top: y, left: x }}
    >
      <p className="font-semibold text-sm mb-1.5">
        {formatTimeRange(new Date(appt.start_at), new Date(appt.end_at))}
      </p>
      <p className="flex items-center gap-1.5 text-foreground">
        <User className="size-3 text-muted-foreground" /> {appt.patient_name ?? "Patient"}
      </p>
      <p className="flex items-center gap-1.5 text-muted-foreground mt-0.5">
        <Stethoscope className="size-3" /> {typeLabel(appt.appointment_type)} · {statusLabel(appt.status)}
      </p>
      {appt.location && (
        <p className="flex items-center gap-1.5 text-muted-foreground mt-0.5">
          <MapPin className="size-3" /> {appt.location}
        </p>
      )}
      {appt.reason && <p className="text-muted-foreground mt-1 italic">{appt.reason}</p>}
      <span className="mt-2 inline-flex items-center gap-1 text-primary">
        Open details <ArrowUpRight className="size-3" />
      </span>
    </div>
  );
}
