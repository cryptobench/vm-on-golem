"use client";

import React from "react";
import { cn } from "./cn";

export function SidebarLayout({
  sidebar,
  children,
  className,
}: {
  sidebar: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid min-h-screen grid-cols-[var(--sidebar-width)_minmax(0,1fr)] bg-background", className)}>
      <aside className="border-r border-border bg-surface">{sidebar}</aside>
      <main className="min-w-0">{children}</main>
    </div>
  );
}
