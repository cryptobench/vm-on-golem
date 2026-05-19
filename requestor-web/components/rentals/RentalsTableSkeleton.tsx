"use client";

import React from "react";
import { Skeleton } from "@golem/ui";

export function RentalsTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-soft">
      <div className="border-b border-border px-5 py-4">
        <Skeleton className="h-5 w-36" />
        <Skeleton className="mt-2 h-4 w-64" />
      </div>
      <div className="space-y-0">
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            className="grid grid-cols-6 gap-4 border-b border-border px-5 py-4 last:border-b-0"
            key={index}
          >
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-8 w-10 justify-self-end" />
          </div>
        ))}
      </div>
    </div>
  );
}
