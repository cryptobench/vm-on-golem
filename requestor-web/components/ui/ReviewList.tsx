"use client";

import React from "react";
import { RiArrowRightSLine } from "@remixicon/react";

export function ReviewList({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      {children}
    </div>
  );
}

export function ReviewListItem({
  label,
  value,
  onEdit,
}: {
  label: string;
  value: string;
  onEdit: () => void;
}) {
  return (
    <button
      type="button"
      className="grid min-h-14 w-full grid-cols-[8rem_minmax(0,1fr)_2rem] items-center gap-4 border-b border-border px-4 py-3 text-left text-sm last:border-b-0 hover:bg-surface-muted"
      onClick={onEdit}
    >
      <span className="text-text-secondary">{label}</span>
      <span className="truncate font-medium text-text-primary">{value}</span>
      <RiArrowRightSLine className="h-4 w-4 justify-self-end text-text-secondary" />
    </button>
  );
}
