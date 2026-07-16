"use client";

import { useDroppable } from "@dnd-kit/core";
import { isSameDay } from "date-fns";
import type { Appointment } from "@/lib/calendar/types";
import {
  buildTimeSlots, positionForRange, layoutDay, slotId,
  SLOT_PX, SLOT_MINUTES, SLOT_MIN_MINUTES,
} from "@/lib/calendar/utils";
import { AppointmentBlock } from "./appointment-block";
import { cn } from "@/lib/utils";

function DroppableSlot({ day, minutes }: { day: Date; minutes: number }) {
  const slotDate = new Date(day);
  slotDate.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
  const { setNodeRef, isOver } = useDroppable({ id: slotId(slotDate) });
  return (
    <div
      ref={setNodeRef}
      style={{ height: SLOT_PX }}
      className={cn("border-b border-r border-border/50", isOver && "bg-primary/10")}
    />
  );
}

export function CalendarWeekView({
  days, appointments, onOpen, onResizeEnd,
}: {
  days: Date[];
  appointments: Appointment[];
  onOpen: (a: Appointment) => void;
  onResizeEnd: (a: Appointment, newEnd: Date) => void;
}) {
  const slots = buildTimeSlots();
  const now = new Date();

  return (
    <div className="flex-1 overflow-auto">
      <div className="grid" style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(120px, 1fr))` }}>
        {/* Header row */}
        <div className="sticky top-0 z-10 bg-background border-b h-12" />
        {days.map((d) => (
          <div key={d.toISOString()} className="sticky top-0 z-10 bg-background border-b border-l h-12 flex flex-col items-center justify-center">
            <span className="text-xs text-muted-foreground">{d.toLocaleDateString("en-US", { weekday: "short" })}</span>
            <span className={cn("text-sm font-semibold", isSameDay(d, now) && "text-primary")}>{d.getDate()}</span>
          </div>
        ))}

        {/* Time gutter */}
        <div>
          {slots.map((s) => (
            <div key={s.minutes} style={{ height: SLOT_PX }} className="text-[10px] text-muted-foreground text-right pr-1.5 -translate-y-1.5">
              {s.label}
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((day) => {
          const dayAppts = appointments.filter((a) => isSameDay(new Date(a.start_at), day));
          const laid = layoutDay(dayAppts);
          const isBusinessDay = day.getDay() >= 1 && day.getDay() <= 5;
          return (
            <div key={day.toISOString()} className={cn("relative", isBusinessDay && "bg-accent/20")}>
              {slots.map((s) => <DroppableSlot key={s.minutes} day={day} minutes={s.minutes} />)}

              {/* now-indicator */}
              {isSameDay(day, now) && (() => {
                const mins = now.getHours() * 60 + now.getMinutes();
                if (mins < SLOT_MIN_MINUTES) return null;
                const top = ((mins - SLOT_MIN_MINUTES) / SLOT_MINUTES) * SLOT_PX;
                return <div className="absolute inset-x-0 z-10 border-t-2 border-primary" style={{ top }} />;
              })()}

              {laid.map(({ appt, column, columns }) => {
                const pos = positionForRange(new Date(appt.start_at), new Date(appt.end_at));
                const width = 100 / columns;
                return (
                  <AppointmentBlock
                    key={appt.id}
                    appt={appt}
                    style={{ top: pos.top, height: pos.height, left: `${column * width}%`, width: `calc(${width}% - 2px)` }}
                    onOpen={onOpen}
                    onResizeEnd={onResizeEnd}
                  />
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
