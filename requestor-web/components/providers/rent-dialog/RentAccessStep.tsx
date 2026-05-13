"use client";

import React from "react";
import { RiAddLine, RiArrowRightSLine } from "@remixicon/react";
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
          <select
            className="input h-10 appearance-none pr-10"
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
          </select>
          <RiArrowRightSLine
            className="pointer-events-none absolute right-3 top-3 h-4 w-4 rotate-90 text-text-secondary"
            aria-hidden
          />
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
        <input
          className="input mt-2 h-10"
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
