"use client";

import React from "react";
import { RiBroadcastLine, RiInboxArchiveLine } from "@remixicon/react";

type EmptyIcon = "vms" | "streams";

function EmptyVisual({ icon }: { icon: EmptyIcon }) {
  const Icon = icon === "vms" ? RiInboxArchiveLine : RiBroadcastLine;
  return (
    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-lg border border-dashed border-border-strong text-primary opacity-40">
      <Icon className="h-8 w-8" aria-hidden />
    </div>
  );
}

export function DashboardEmptyState({
  icon,
  title,
  description,
}: {
  icon: EmptyIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center px-4 py-7 text-center">
      <EmptyVisual icon={icon} />
      <h3 className="mt-4 text-lg font-semibold text-text-primary">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-5 text-text-secondary">{description}</p>
    </div>
  );
}
