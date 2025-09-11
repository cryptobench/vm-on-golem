"use client";
import React from "react";
import { cn } from "./cn";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-gray-200/70", className)} />;
}

export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="overflow-hidden rounded-xl border">
      <div className="bg-gray-50 px-4 py-3">
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="divide-y divide-gray-200">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="grid grid-cols-12 items-center gap-3 px-4 py-3">
            {Array.from({ length: cols }).map((__, c) => (
              <Skeleton key={c} className="h-4 w-full col-span-2" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

