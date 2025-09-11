import React, { Suspense } from "react";
import VmDetailsClient from "./VmDetailsClient";

export default function Page() {
  return (
    <Suspense fallback={<div className="text-sm text-gray-600">Loading VM…</div>}>
      <VmDetailsClient />
    </Suspense>
  );
}
