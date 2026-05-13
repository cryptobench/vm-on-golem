import React, { Suspense } from "react";
import { VmDetailsSkeleton } from "../../../components/vm/details/VmDetailsSkeleton";
import VmDetailsClient from "../VmDetailsClient";

type PageProps = {
  params: {
    id: string;
  };
};

export default function Page({ params }: PageProps) {
  return (
    <Suspense fallback={<VmDetailsSkeleton />}>
      <VmDetailsClient vmId={params.id} />
    </Suspense>
  );
}
