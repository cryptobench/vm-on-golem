import React, { Suspense } from "react";
import { VmDetailsSkeleton } from "../../../components/vm/details/VmDetailsSkeleton";
import VmDetailsClient from "../VmDetailsClient";

type PageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;

  return (
    <Suspense fallback={<VmDetailsSkeleton />}>
      <VmDetailsClient vmId={id} />
    </Suspense>
  );
}
