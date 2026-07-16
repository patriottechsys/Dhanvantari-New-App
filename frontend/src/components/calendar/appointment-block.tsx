"use client";

import { useRef, useState } from "react";
import { useDraggable } from "@dnd-kit/core";
import type { Appointment } from "@/lib/calendar/types";
import {
  typeColor, statusBlockClass, typeLabel, draggableId,
  SLOT_PX, SLOT_MINUTES,
} from "@/lib/calendar/utils";
import { AppointmentTooltip } from "./appointment-tooltip";
import { cn } from "@/lib/utils";

export function AppointmentBlock({
  appt, style, onOpen, onResizeEnd,
}: {
  appt: Appointment;
  style: { top: number; height: number; left: string; width: string };
  onOpen: (appt: Appointment) => void;
  onResizeEnd: (appt: Appointment, newEnd: Date) => void;
}) {
  const color = typeColor(appt.appointment_type);
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: draggableId("appt", appt.id) });
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null);
  const [resizeDelta, setResizeDelta] = useState(0);
  const resizing = useRef(false);

  function onResizePointerDown(e: React.PointerEvent) {
    e.stopPropagation();
    e.preventDefault();
    resizing.current = true;
    const startY = e.clientY;

    const move = (ev: PointerEvent) => {
      if (!resizing.current) return;
      const slots = Math.round((ev.clientY - startY) / SLOT_PX);
      setResizeDelta(slots * SLOT_PX);
    };
    const up = (ev: PointerEvent) => {
      resizing.current = false;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      const slots = Math.round((ev.clientY - startY) / SLOT_PX);
      setResizeDelta(0);
      if (slots !== 0) {
        const newEnd = new Date(new Date(appt.end_at).getTime() + slots * SLOT_MINUTES * 60_000);
        if (newEnd.getTime() > new Date(appt.start_at).getTime()) onResizeEnd(appt, newEnd);
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  return (
    <>
      <div
        ref={setNodeRef}
        {...attributes}
        {...listeners}
        onClick={() => onOpen(appt)}
        onMouseEnter={(e) => {
          const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
          setTip({ x: r.right + 8, y: r.top });
        }}
        onMouseLeave={() => setTip(null)}
        style={{
          top: style.top, height: style.height + resizeDelta, left: style.left, width: style.width,
        }}
        className={cn(
          "absolute rounded-md border border-l-4 px-1.5 py-1 text-[11px] leading-tight overflow-hidden cursor-grab active:cursor-grabbing touch-none",
          color.block, color.accent, statusBlockClass(appt.status),
          isDragging && "opacity-60 shadow-lg z-20"
        )}
      >
        <p className="font-semibold truncate">{appt.patient_name ?? "Patient"}</p>
        <p className="truncate text-muted-foreground">{typeLabel(appt.appointment_type)}</p>
        <div
          onPointerDown={onResizePointerDown}
          onClick={(e) => e.stopPropagation()}
          className="absolute inset-x-0 bottom-0 h-2 cursor-ns-resize"
        />
      </div>
      {tip && !isDragging && <AppointmentTooltip appt={appt} x={tip.x} y={tip.y} />}
    </>
  );
}
