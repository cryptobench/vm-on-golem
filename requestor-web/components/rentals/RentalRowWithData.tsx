"use client";

import React from "react";
import { Skeleton } from "@golem/ui";
import { useRouter } from "next/navigation";
import type { VMResources } from "../../lib/api";
import type { RequestorVmModel } from "../../lib/requestorVmModel";
import { formatUnixSecondsDateTime } from "../../lib/time";
import { vmDetailsHref } from "../../lib/routes";
import { humanDuration } from "../../lib/streams";
import { countryFlagEmoji } from "../../lib/intl";
import { CopyValue } from "./CopyValue";
import { RentalStatusPill } from "./RentalStatusPill";
import { VmPlatform } from "./VmPlatform";

type RentalRowWithDataProps = {
  vm: RequestorVmModel;
  terminated?: boolean;
};

function terminalStatus(status: string) {
  return (
    status === "terminated" ||
    status === "deleted" ||
    status === "payment_expired"
  );
}

function resourceValue(
  resources: VMResources | undefined,
  key: keyof VMResources,
) {
  const value = resources?.[key];
  return value == null ? "-" : String(value);
}

function resourceWithUnit(
  resources: VMResources | undefined,
  key: keyof VMResources,
  unit: string,
) {
  const value = resourceValue(resources, key);
  return value === "-" ? value : `${value} ${unit}`;
}

function formatEndedAt(value?: number) {
  return formatUnixSecondsDateTime(value) ?? "-";
}

function CellSkeleton({ className = "w-20" }: { className?: string }) {
  return <Skeleton className={`h-4 ${className}`} />;
}

export function RentalRowWithData({
  vm,
  terminated,
}: RentalRowWithDataProps) {
  const router = useRouter();
  const { rental, lifecycle, resources, platform, country } = vm;
  const liveStatus = lifecycle.status;
  const isTerminated = terminalStatus(liveStatus) || !!terminated;
  const isLiveLoading = vm.probePending && !vm.hasLiveProbe;
  const flag = countryFlagEmoji(country);
  const timeValue = isLiveLoading && rental.stream_id
    ? null
    : isTerminated
    ? formatEndedAt(rental.ended_at)
    : rental.stream_id
      ? vm.remainingSeconds == null
        ? "Unavailable"
        : humanDuration(vm.remainingSeconds)
      : "-";

  const openDetails = () => router.push(vmDetailsHref(rental.vm_id));

  return (
    <tr
      className="vm-table-row group cursor-pointer border-t border-border bg-surface"
      onClick={openDetails}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === " " || event.key === "Enter") {
          event.preventDefault();
          openDetails();
        }
      }}
    >
      <td className="td min-w-36 py-4 font-medium">{rental.name}</td>
      <td className="td py-4">
        {isLiveLoading ? (
          <CellSkeleton className="w-20" />
        ) : (
          <RentalStatusPill status={liveStatus} />
        )}
      </td>
      <td className="td py-4">
        <CopyValue value={rental.provider_id} />
      </td>
      <td className="td py-4">
        {isLiveLoading && !country ? (
          <CellSkeleton className="w-16" />
        ) : (
          <span className="inline-flex items-center gap-2">
            {flag && <span className="text-base leading-none">{flag}</span>}
            <span>{country || "-"}</span>
          </span>
        )}
      </td>
      <td className="td py-4">
        {isLiveLoading && !rental.platform ? (
          <CellSkeleton className="w-20" />
        ) : (
          <VmPlatform platform={platform} />
        )}
      </td>
      <td className="td py-4">
        {isLiveLoading && !resources ? (
          <CellSkeleton className="w-8" />
        ) : (
          resourceValue(resources, "cpu")
        )}
      </td>
      <td className="td py-4">
        {isLiveLoading && !resources ? (
          <CellSkeleton className="w-12" />
        ) : (
          resourceWithUnit(resources, "memory", "GB")
        )}
      </td>
      <td className="td py-4">
        {isLiveLoading && !resources ? (
          <CellSkeleton className="w-12" />
        ) : (
          resourceWithUnit(resources, "storage", "GB")
        )}
      </td>
      <td className="td min-w-32 py-4 text-text-secondary">
        {timeValue == null ? <CellSkeleton className="w-20" /> : timeValue}
      </td>
    </tr>
  );
}
