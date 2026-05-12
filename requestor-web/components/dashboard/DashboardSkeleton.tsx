"use client";

import React from "react";
import { Skeleton } from "../ui/Skeleton";

export function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-lg border border-border bg-surface p-6 shadow-sm">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="mt-4 h-8 w-20" />
            <Skeleton className="mt-5 h-4 w-36" />
          </div>
        ))}
      </div>
      <Skeleton className="h-72 rounded-lg" />
      <Skeleton className="h-64 rounded-lg" />
    </div>
  );
}
