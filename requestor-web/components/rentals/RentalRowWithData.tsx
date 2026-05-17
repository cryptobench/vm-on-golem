"use client";

import React from "react";
import { useRouter } from "next/navigation";
import type { Rental, VMResources } from "../../lib/api";
import type { RequestorVmModel } from "../../lib/requestorVmModel";
import { formatUnixSecondsDateTime } from "../../lib/time";
import { vmDetailsHref } from "../../lib/routes";
import { humanDuration } from "../../lib/streams";
import { countryFlagEmoji } from "../../lib/intl";
import { CopyValue } from "./CopyValue";
import { RentalActionsMenu } from "./RentalActionsMenu";
import { RentalStatusPill } from "./RentalStatusPill";
import { VmPlatform } from "./VmPlatform";

type RentalRowWithDataProps = {
  vm: RequestorVmModel;
  busy?: boolean;
  terminated?: boolean;
  onCopySSH?: (rental: Rental) => void;
  onStart?: (rental: Rental) => void;
  onStop?: (rental: Rental) => void;
  onDestroy?: (rental: Rental) => void;
};

function terminalStatus(status: string) {
  return status === "terminated" || status === "deleted";
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

export function RentalRowWithData({
  vm,
  busy,
  terminated,
  onCopySSH,
  onStart,
  onStop,
  onDestroy,
}: RentalRowWithDataProps) {
  const router = useRouter();
  const { rental, lifecycle, resources, platform, country, sshEndpoint } = vm;
  const liveStatus = lifecycle.status;
  const isTerminated = terminalStatus(liveStatus) || !!terminated;
  const flag = countryFlagEmoji(country);
  const timeValue = isTerminated
    ? formatEndedAt(rental.ended_at)
    : rental.stream_id
      ? vm.remainingSeconds == null
        ? "Fetching"
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
        <RentalStatusPill status={liveStatus} />
      </td>
      <td className="td py-4">
        <CopyValue value={rental.vm_id} />
      </td>
      <td className="td py-4">
        <CopyValue value={rental.provider_id} />
      </td>
      <td className="td py-4">
        <span className="inline-flex items-center gap-2">
          {flag && <span className="text-base leading-none">{flag}</span>}
          <span>{country || "-"}</span>
        </span>
      </td>
      <td className="td py-4">
        <CopyValue value={sshEndpoint === "-" ? "" : sshEndpoint} />
      </td>
      <td className="td py-4">
        <VmPlatform platform={platform} />
      </td>
      <td className="td py-4">{resourceValue(resources, "cpu")}</td>
      <td className="td py-4">{resourceWithUnit(resources, "memory", "GB")}</td>
      <td className="td py-4">
        {resourceWithUnit(resources, "storage", "GB")}
      </td>
      <td className="td py-4">
        <CopyValue value={rental.stream_id} />
      </td>
      <td className="td min-w-32 py-4 text-text-secondary">{timeValue}</td>
      <td className="td py-4">
        <RentalActionsMenu
          rental={rental}
          status={liveStatus}
          busy={busy}
          onView={openDetails}
          onCopySSH={onCopySSH}
          onStart={onStart}
          onStop={onStop}
          onDestroy={onDestroy}
        />
      </td>
    </tr>
  );
}
