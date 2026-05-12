"use client";

import React from "react";

const toneClass: Record<string, string> = {
  running: "bg-success text-success",
  active: "bg-success text-success",
  starting: "bg-primary text-primary",
  creating: "bg-primary text-primary",
  stopped: "bg-text-muted text-text-secondary",
  halted: "bg-warning text-warning",
  terminated: "bg-danger text-danger",
  deleted: "bg-danger text-danger",
  error: "bg-danger text-danger",
  failed: "bg-danger text-danger",
};

export function DashboardStatus({ status }: { status?: string | null }) {
  const normalized = String(status || "unknown").toLowerCase();
  const label = normalized.charAt(0).toUpperCase() + normalized.slice(1);
  const classes = toneClass[normalized] || "bg-text-muted text-text-secondary";

  return (
    <span className={`inline-flex items-center gap-2 text-sm ${classes.split(" ")[1]}`}>
      <span className={`h-2 w-2 rounded-full ${classes.split(" ")[0]}`} aria-hidden />
      {label}
    </span>
  );
}
