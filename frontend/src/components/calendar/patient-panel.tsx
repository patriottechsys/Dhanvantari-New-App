"use client";

import { useDraggable } from "@dnd-kit/core";
import { GripVertical, Search } from "lucide-react";
import type { Patient } from "@/lib/calendar/types";
import { draggableId } from "@/lib/calendar/utils";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

function PatientCard({ patient }: { patient: Patient }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: draggableId("patient", patient.id),
  });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={cn(
        "flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm cursor-grab active:cursor-grabbing touch-none select-none",
        isDragging && "opacity-40 ring-2 ring-primary/20"
      )}
    >
      <GripVertical className="size-3.5 text-muted-foreground shrink-0" />
      <span className="truncate">{patient.full_name}</span>
    </div>
  );
}

export function PatientPanel({
  patients,
  search,
  onSearch,
}: {
  patients: Patient[];
  search: string;
  onSearch: (v: string) => void;
}) {
  const filtered = patients.filter((p) => p.full_name.toLowerCase().includes(search.toLowerCase()));
  return (
    <div className="w-56 shrink-0 border-r flex flex-col">
      <div className="p-3 border-b">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Patients</p>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none" />
          <Input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search…"
            className="pl-8 h-8"
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        <p className="text-[11px] text-muted-foreground mb-1">Drag a patient onto a time slot →</p>
        {filtered.map((p) => <PatientCard key={p.id} patient={p} />)}
        {filtered.length === 0 && <p className="text-xs text-muted-foreground py-4 text-center">No patients.</p>}
      </div>
    </div>
  );
}
