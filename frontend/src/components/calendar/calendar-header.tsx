"use client";

import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AppointmentType } from "@/lib/calendar/types";
import { typeLabel } from "@/lib/calendar/utils";

export type CalendarView = "day" | "week" | "month";
const VIEWS: CalendarView[] = ["day", "week", "month"];
const TYPES: AppointmentType[] = ["consultation", "follow_up", "therapy", "panchakarma"];

export function CalendarHeader({
  view, onView, label, onPrev, onNext, onToday, onNew, typeFilter, onTypeFilter,
}: {
  view: CalendarView;
  onView: (v: CalendarView) => void;
  label: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  onNew: () => void;
  typeFilter: AppointmentType | null;
  onTypeFilter: (t: AppointmentType | null) => void;
}) {
  return (
    <div className="space-y-3 p-6 pb-3 border-b">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Appointments</h1>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-sm" onClick={onPrev}><ChevronLeft className="size-4" /></Button>
            <Button variant="outline" size="sm" onClick={onToday}>Today</Button>
            <Button variant="ghost" size="icon-sm" onClick={onNext}><ChevronRight className="size-4" /></Button>
          </div>
          <span className="text-sm text-muted-foreground">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1 rounded-lg border p-0.5">
            {VIEWS.map((v) => (
              <button
                key={v}
                onClick={() => onView(v)}
                className={cn(
                  "text-sm px-3 py-1 rounded-md capitalize transition-colors",
                  view === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {v}
              </button>
            ))}
          </div>
          <Button size="sm" className="gap-1.5" onClick={onNew}><Plus className="size-4" /> New appointment</Button>
        </div>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        <button
          onClick={() => onTypeFilter(null)}
          className={cn("text-xs px-2.5 py-1 rounded-full border transition-colors",
            typeFilter === null ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground hover:text-foreground")}
        >
          All
        </button>
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => onTypeFilter(typeFilter === t ? null : t)}
            className={cn("text-xs px-2.5 py-1 rounded-full border transition-colors",
              typeFilter === t ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground hover:text-foreground")}
          >
            {typeLabel(t)}
          </button>
        ))}
      </div>
    </div>
  );
}
