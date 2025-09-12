import React, { Suspense } from "react";
import VmDetailsClient from "./VmDetailsClient";
import { Skeleton } from "../../components/ui/Skeleton";

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <div className="card"><div className="card-body">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-5 w-24" />
                  <Skeleton className="h-7 w-40" />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-24" />
                </div>
              </div>
              <div className="flex flex-col items-start gap-2 sm:items-end">
                <Skeleton className="h-4 w-40" />
                <div className="flex gap-2">
                  <Skeleton className="h-9 w-24" />
                  <Skeleton className="h-9 w-24" />
                  <Skeleton className="h-9 w-24" />
                </div>
              </div>
            </div>
          </div></div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="card"><div className="card-body"><Skeleton className="h-6 w-24" /></div></div>
            <div className="card"><div className="card-body"><Skeleton className="h-6 w-24" /></div></div>
            <div className="card"><div className="card-body"><Skeleton className="h-6 w-24" /></div></div>
          </div>
          <div className="card"><div className="card-body">
            <div className="grid gap-6 sm:grid-cols-2">
              <div className="grid gap-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-20" />
              </div>
              <div className="grid gap-3 content-start">
                <Skeleton className="h-4 w-32" />
                <div className="flex gap-2">
                  <Skeleton className="h-9 w-20" />
                  <Skeleton className="h-9 w-20" />
                  <Skeleton className="h-9 w-20" />
                </div>
                <div className="flex items-center gap-2">
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-16" />
                </div>
              </div>
            </div>
          </div></div>
        </div>
      }
    >
      <VmDetailsClient />
    </Suspense>
  );
}
