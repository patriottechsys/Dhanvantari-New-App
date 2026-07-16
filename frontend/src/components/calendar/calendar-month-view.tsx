"use client";

import { useDroppable } from "@dnd-kit/core";
import {
  startOfMonth, endOfMonth, startOfWeek, endOfWeek, addDays, isSameMonth, isSameDay,
} from "date-fns";
import type { Appointment } from "@/lib/calendar/types";
import { slotId, typeColor, typeLabel } from "@/lib/calendar/utils";
import { cn } from "@/lib/utils";

function DayCell({
  day, anchor, appts, onOpen,
}: {
  day: Date;
  anchor: Date;
  appts: Appointment[];
  onOpen: (a: Appointment) => void;
}) {
  // Dropping on a month cell books at 9:00am that day.
  const slotDate = new Date(day);
  slotDate.setHours(9, 0, 0, 0);
  const { setNodeRef, isOver } = useDroppable({ id: slotId(slotDate) });
  const now = new Date();
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "min-h-24 border-b border-r p-1.5 space-y-1 overflow-hidden",
        !isSameMonth(day, anchor) && "bg-muted/30 text-muted-foreground",
        isOver && "bg-primary/10"
      )}
    >
      <span className={cn("text-xs font-medium", isSameDay(day, now) && "text-primary font-semibold")}>{day.getDate()}</span>
      {appts.slice(0, 3).map((a) => {
        const color = typeColor(a.appointment_type);
        return (
          <button
            key={a.id}
            onClick={() => onOpen(a)}
            className={cn("block w-full text-left rounded px-1.5 py-0.5 text-[10px] truncate border-l-2", color.block, color.accent)}
          >
            {new Date(a.start_at).toLocaleTimeString("en-US", { hour: "numeric" })} {a.patient_name ?? typeLabel(a.appointment_type)}
          </button>
        );
      })}
      {appts.length > 3 && <span className="text-[10px] text-muted-foreground">+{appts.length - 3} more</span>}
    </div>
  );
}

export function CalendarMonthView({
  anchor, appointments, onOpen,
}: {
  anchor: Date;
  appointments: Appointment[];
  onOpen: (a: Appointment) => void;
}) {
  const gridStart = startOfWeek(startOfMonth(anchor), { weekStartsOn: 1 });
  const gridEnd = endOfWeek(endOfMonth(anchor), { weekStartsOn: 1 });
  const days: Date[] = [];
  for (let d = gridStart; d <= gridEnd; d = addDays(d, 1)) days.push(d);

  return (
    <div className="flex-1 overflow-auto">
      <div className="grid grid-cols-7 border-t border-l">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="border-b border-r px-2 py-1.5 text-xs font-medium text-muted-foreground">{d}</div>
        ))}
        {days.map((day) => (
          <DayCell
            key={day.toISOString()}
            day={day}
            anchor={anchor}
            appts={appointments.filter((a) => isSameDay(new Date(a.start_at), day))}
            onOpen={onOpen}
          />
        ))}
      </div>
    </div>
  );
}
