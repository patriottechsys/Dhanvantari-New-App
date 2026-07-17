"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Users,
  CalendarCheck,
  CalendarDays,
  Leaf,
  UtensilsCrossed,
  Wind,
  PersonStanding,
  HandHeart,
  ClipboardList,
  Sparkles,
  Settings,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";

const NAV = [
  { href: "/dashboard",   label: "Dashboard",   icon: LayoutDashboard },
  { href: "/patients",    label: "Patients",     icon: Users },
  { href: "/followups",   label: "Follow-ups",   icon: CalendarCheck },
  { href: "/calendar",    label: "Appointments", icon: CalendarDays },
  { href: "/services",    label: "Services",     icon: HandHeart },
  { href: "/supplements", label: "Supplements",  icon: Leaf },
  { href: "/recipes",     label: "Recipes",      icon: UtensilsCrossed },
  { href: "/pranayama",   label: "Pranayama",    icon: Wind },
  { href: "/yoga",        label: "Yoga",         icon: PersonStanding },
  { href: "/intake",       label: "Intake Forms", icon: ClipboardList },
  { href: "/ai-assistant", label: "AI Assistant", icon: Sparkles },
  { href: "/settings",    label: "Settings",     icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { practitioner, isAuthenticated, clearAuth } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated()) {
      router.replace("/login");
    }
  }, [mounted, isAuthenticated, router]);

  if (!mounted || !isAuthenticated()) return null;

  function logout() {
    clearAuth();
    router.push("/login");
  }

  const initials = practitioner?.name
    ?.split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase() ?? "?";

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-sidebar text-sidebar-foreground transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center gap-2.5 px-5 border-b border-sidebar-border">
          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-bold text-xs shrink-0">
            ॐ
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-sm leading-tight truncate">Dhanvantari</p>
            {practitioner?.practice_name && (
              <p className="text-xs text-sidebar-foreground/50 truncate">
                {practitioner.practice_name}
              </p>
            )}
          </div>
          <button
            className="ml-auto lg:hidden text-sidebar-foreground/60 hover:text-sidebar-foreground"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                )}
              >
                <Icon className="size-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        <div className="border-t border-sidebar-border p-3">
          <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary-foreground text-xs font-semibold shrink-0">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{practitioner?.name}</p>
              <p className="text-xs text-sidebar-foreground/50 truncate capitalize">
                {practitioner?.subscription_tier?.toLowerCase()} plan
              </p>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="text-sidebar-foreground/40 hover:text-sidebar-foreground transition-colors"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Topbar (mobile only) */}
        <header className="flex h-14 items-center gap-3 border-b bg-background px-4 lg:hidden">
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)}>
            <Menu className="size-5" />
          </Button>
          <span className="font-semibold text-sm">Dhanvantari</span>
        </header>

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
