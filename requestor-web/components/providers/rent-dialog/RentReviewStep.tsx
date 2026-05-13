"use client";

import React from "react";
import { Callout } from "../../ui/Callout";
import { ReviewList, ReviewListItem } from "../../ui/ReviewList";
import type { RentSpec } from "./types";
import { formatDate } from "./dateFormatting";
import { RentStepSection } from "./RentStepSection";

export function RentReviewStep({
  spec,
  name,
  keyName,
  keyFingerprint,
  durationLabel: displayDurationLabel,
  startsAt,
  endsAt,
  onEdit,
}: {
  spec: RentSpec;
  name: string;
  keyName: string;
  keyFingerprint: string;
  durationLabel: string;
  startsAt: Date;
  endsAt: Date;
  onEdit: (step: number) => void;
}) {
  return (
    <RentStepSection
      title="Review and confirm"
      description="Please review your configuration before creating the VM."
    >
      <div className="mt-5">
        <ReviewList>
          <ReviewListItem
            label="Specs"
            value={`${spec.cpu} vCPU - ${spec.memory} GB RAM - ${spec.storage} GB Storage`}
            onEdit={() => onEdit(0)}
          />
          <ReviewListItem
            label="Duration"
            value={`${displayDurationLabel} (${formatDate(startsAt)} - ${formatDate(endsAt)})`}
            onEdit={() => onEdit(1)}
          />
          <ReviewListItem
            label="Access (SSH key)"
            value={`${keyName} (${keyFingerprint})`}
            onEdit={() => onEdit(2)}
          />
          <ReviewListItem label="VM name" value={name} onEdit={() => onEdit(2)} />
        </ReviewList>
      </div>
      <Callout className="mt-7">
        By creating this VM, a payment stream will be opened for the selected
        duration.
      </Callout>
    </RentStepSection>
  );
}
