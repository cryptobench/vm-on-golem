"use client";

import React from "react";
import { Spinner } from "@golem/ui";
import { deriveVmLifecycle } from "../../lib/vmLifecycle";

export function DashboardStatus({ status }: { status?: string | null }) {
  const lifecycle = deriveVmLifecycle({ status });
  const classes = {
    success: "bg-success text-success",
    warning: "bg-warning text-warning",
    danger: "bg-danger text-danger",
    neutral: "bg-text-muted text-text-secondary",
    primary: "bg-primary text-primary",
  }[lifecycle.tone];

  return (
    <span
      className={`inline-flex items-center gap-2 text-sm ${classes.split(" ")[1]}`}
    >
      {lifecycle.transitioning ? (
        <Spinner className="h-3.5 w-3.5" />
      ) : (
        <span
          className={`h-2 w-2 rounded-full ${classes.split(" ")[0]}`}
          aria-hidden
        />
      )}
      {lifecycle.label}
    </span>
  );
}
