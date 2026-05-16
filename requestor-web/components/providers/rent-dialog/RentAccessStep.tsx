"use client";

import React from "react";
import { RiAddLine } from "@remixicon/react";
import { Input, Select } from "@golem/ui";
import type { SSHKey } from "../../../lib/api";
import { KeyAddModal } from "../../ssh/KeyAddModal";
import { RentStepSection } from "./RentStepSection";

export function RentAccessStep({
  name,
  keys,
  selectedKeyId,
  defaultKeyId,
  onNameChange,
  onSshKeyChange,
  onSshKeyAdded,
}: {
  name: string;
  keys: SSHKey[];
  selectedKeyId: string;
  defaultKeyId: string;
  onNameChange: (value: string) => void;
  onSshKeyChange: (id: string, key: SSHKey) => void;
  onSshKeyAdded: (key: SSHKey) => void;
}) {
  const [openAdd, setOpenAdd] = React.useState(false);

  return (
    <RentStepSection
      title="Set up access"
      description="Choose or add an SSH key to access your VM."
      size="md"
    >
      <div className="mt-8">
        <label className="label">SSH key</label>
        <div className="relative mt-2">
          <Select
            selectClassName="h-10 pr-10"
            value={selectedKeyId}
            disabled={!keys.length}
            onChange={(event) => {
              const key = keys.find((item) => item.id === event.target.value);
              if (key) onSshKeyChange(key.id, key);
            }}
          >
            {keys.length ? (
              keys.map((key) => (
                <option key={key.id} value={key.id}>
                  {key.name || "Unnamed key"}
                  {key.id === defaultKeyId ? " (default)" : ""}
                </option>
              ))
            ) : (
              <option>No SSH keys saved</option>
            )}
          </Select>
        </div>
        <button
          type="button"
          className="mt-3 inline-flex h-10 items-center gap-2 rounded-md px-2 text-sm font-medium text-primary hover:bg-primary-soft"
          onClick={() => setOpenAdd(true)}
        >
          <RiAddLine className="h-4 w-4" aria-hidden />
          Add new SSH key
        </button>
        <KeyAddModal
          open={openAdd}
          onClose={() => setOpenAdd(false)}
          onAdded={onSshKeyAdded}
        />
      </div>

      <div className="mt-8">
        <label className="label">VM name</label>
        <Input
          className="mt-2"
          inputClassName="h-10"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="vm-ed1d"
        />
        <p className="mt-3 text-sm text-text-secondary">
          Use a descriptive name to easily identify your VM.
        </p>
      </div>
    </RentStepSection>
  );
}
