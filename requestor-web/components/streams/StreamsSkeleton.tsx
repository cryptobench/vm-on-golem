"use client";

import React from "react";
import { Skeleton } from "@golem/ui";

export function StreamsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-lg border border-border bg-surface p-5 shadow-soft">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="mt-4 h-7 w-20" />
            <Skeleton className="mt-4 h-4 w-32" />
          </div>
        ))}
      </div>
      <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-soft">
        <div className="flex h-16 items-center gap-5 border-b border-border px-5">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-5 w-32" />
        </div>
        <div className="divide-y divide-border">
          {Array.from({ length: 3 }).map((_, row) => (
            <div key={row} className="grid grid-cols-12 items-center gap-4 px-5 py-5">
              <Skeleton className="col-span-2 h-5 w-full" />
              <Skeleton className="col-span-2 h-5 w-full" />
              <Skeleton className="col-span-2 h-5 w-full" />
              <Skeleton className="col-span-1 h-5 w-full" />
              <Skeleton className="col-span-2 h-5 w-full" />
              <Skeleton className="col-span-2 h-5 w-full" />
              <Skeleton className="col-span-1 h-9 w-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
