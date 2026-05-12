import React, { Suspense } from "react";
import VmDetailsClient from "./VmDetailsClient";
import { VmDetailsSkeleton } from "../../components/vm/details/VmDetailsSkeleton";

export default function Page() {
  return (
    <Suspense
      fallback={<VmDetailsSkeleton />}
    >
      <VmDetailsClient />
    </Suspense>
  );
}
