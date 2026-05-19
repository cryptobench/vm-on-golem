"use client";

import React from "react";
import { Input } from "@golem/ui";
import { KeyPicker } from "../../ssh/KeyPicker";
import type { SSHKey } from "../../../lib/api";
import { SectionCard } from "./SectionCard";

export function VmDetailsPanel({
  name,
  selectedKeyId,
  onNameChange,
  onSshKeyChange,
}: {
  name: string;
  selectedKeyId: string;
  onNameChange: (value: string) => void;
  onSshKeyChange: (id: string, key: SSHKey) => void;
}) {
  return (
    <>
      <SectionCard title="2. VM details">
        <label className="label">VM name</label>
        <Input
          className="mt-2"
          inputClassName="h-10"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="sim-node-01"
        />
      </SectionCard>

      <SectionCard title="3. SSH public key">
        <KeyPicker layout="list" value={selectedKeyId} onChange={onSshKeyChange} />
      </SectionCard>
    </>
  );
}
