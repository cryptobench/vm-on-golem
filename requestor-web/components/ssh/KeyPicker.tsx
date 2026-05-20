"use client";
import React from "react";
import { RiAddLine, RiCheckboxCircleLine, RiKey2Line } from "@remixicon/react";
import { loadSettings, saveSettings, type SSHKey } from "../../lib/api";
import { KeyAddModal } from "./KeyAddModal";
import { cn } from "@golem/ui";

type KeyPickerLayout = "grid" | "carousel" | "list";

function keyParts(key: SSHKey) {
  const parts = (key.value || key.public_key || "").split(" ");
  return {
    type: parts[0] || "",
    fingerprint: parts[1] ? `${parts[1].slice(0, 8)}...${parts[1].slice(-5)}` : "",
  };
}

export function KeyPicker({ value, onChange, layout = 'grid' }: { value?: string; onChange: (id: string, key: SSHKey) => void; layout?: KeyPickerLayout }) {
  const [keys, setKeys] = React.useState<SSHKey[]>([]);
  const [selected, setSelected] = React.useState<string | undefined>(value);
  const [openAdd, setOpenAdd] = React.useState(false);

  React.useEffect(() => {
    const s = loadSettings();
    const list: SSHKey[] = s.ssh_keys || (s.ssh_public_key ? [{ id: 'default', name: 'Default', value: s.ssh_public_key }] : []);
    setKeys(list);
    if (!selected) setSelected(s.default_ssh_key_id || list[0]?.id);
  }, []);

  React.useEffect(() => { if (value !== undefined) setSelected(value); }, [value]);

  const select = (id: string, sourceKeys = keys) => {
    setSelected(id);
    const k = sourceKeys.find(x => x.id === id);
    if (k) onChange(id, k);
    const prev = loadSettings();
    saveSettings({
      ssh_keys: sourceKeys,
      default_ssh_key_id: id,
      stream_payment_address: prev.stream_payment_address,
      glm_token_address: prev.glm_token_address,
    });
  };

  const remove = (id: string) => {
    const next = keys.filter(k => k.id !== id);
    setKeys(next);
    const newSel = selected === id ? next[0]?.id : selected;
    if (newSel && next.find(k => k.id === newSel)) select(newSel, next);
    const prev = loadSettings();
    saveSettings({
      ssh_keys: next,
      default_ssh_key_id: (newSel && next.some(k => k.id === newSel)) ? newSel : next[0]?.id,
      stream_payment_address: prev.stream_payment_address,
      glm_token_address: prev.glm_token_address,
    });
  };

  const addKey = (key: SSHKey) => {
    const next = [...keys, key];
    setKeys(next);
    select(key.id, next);
  };

  const Tile = ({ k }: { k?: SSHKey }) => {
    if (!k) {
      return (
        <button
          className="relative flex h-36 w-64 shrink-0 items-center justify-center rounded-xl border-2 border-dashed border-gray-300 bg-white text-gray-600 hover:border-brand-400 hover:text-brand-700"
          onClick={() => setOpenAdd(true)}
        >
          <div className="text-center">
            <div className="text-2xl">＋</div>
            <div className="mt-1 text-sm font-medium">Add SSH Key</div>
          </div>
        </button>
      );
    }
    const sel = selected === k.id;
    const parts = (k.value || '').split(' ');
    const type = parts[0] || '';
    const short = parts[1] ? `${parts[1].slice(0, 12)}…${parts[1].slice(-8)}` : '';
    return (
      <div
        key={k.id}
        className={"relative h-36 w-64 shrink-0 rounded-xl border bg-white p-3 text-left shadow-sm transition-colors " + (sel ? 'border-brand-500 ring-1 ring-brand-300' : 'hover:border-gray-300')}
        title={sel ? 'Default SSH key' : 'Set as default'}
      >
        <button
          type="button"
          className="absolute inset-0 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-300"
          onClick={() => select(k.id)}
          aria-pressed={sel}
          aria-label={sel ? `${k.name || "Unnamed key"} is the default SSH key` : `Set ${k.name || "Unnamed key"} as the default SSH key`}
        />
        <div className={"pointer-events-none absolute right-2 top-2 h-6 w-6 rounded-full border-2 " + (sel ? 'border-brand-500 bg-brand-500 text-white' : 'border-gray-300 bg-white text-transparent')}>
          <svg viewBox="0 0 20 20" className="h-full w-full p-0.5"><path fill="currentColor" d="M7.629 13.233L4.4 10.004l1.414-1.414l1.815 1.815l0.001-0.001L14.186 3.85l1.414 1.414l-7.971 7.971z"/></svg>
        </div>
        <div className="pointer-events-none mt-1 truncate pr-8 text-sm font-medium">{k.name || 'Unnamed key'}</div>
        <div className="pointer-events-none mt-1 text-xs text-gray-500">{type}</div>
        <div className="pointer-events-none mt-1 truncate font-mono text-xs text-gray-600">{short}</div>
        <div className="absolute bottom-2 right-2 flex gap-2">
          <button
            type="button"
            className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-300"
            onClick={(event) => {
              event.stopPropagation();
              remove(k.id);
            }}
          >
            Delete
          </button>
        </div>
      </div>
    );
  };

  if (layout === 'carousel') {
    return (
      <div className="overflow-x-auto pb-2">
        <div className="flex flex-nowrap items-stretch gap-3 pr-2">
          <Tile />
          {keys.map((k) => (<Tile key={k.id} k={k} />))}
        </div>
        <KeyAddModal open={openAdd} onClose={() => setOpenAdd(false)} onAdded={addKey} />
      </div>
    );
  }

  if (layout === "list") {
    const selectedKey = keys.find((key) => key.id === selected);
    const selectedParts = selectedKey ? keyParts(selectedKey) : null;

    return (
      <div>
        <div className="rounded-md border border-border bg-surface">
          <div className="flex min-h-10 items-center gap-3 border-b border-border px-3 py-2">
            <span className="flex h-2 w-2 rounded-full bg-success" aria-hidden />
            {selectedKey ? (
              <>
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">
                  {selectedKey.name || "Unnamed key"}
                </span>
                <span className="hidden text-xs text-text-secondary sm:inline">{selectedParts?.type}</span>
                <span className="hidden max-w-36 truncate font-mono text-xs text-text-secondary sm:inline">
                  {selectedParts?.fingerprint}
                </span>
              </>
            ) : (
              <span className="text-sm text-text-secondary">No SSH key selected</span>
            )}
          </div>
          <div className="divide-y divide-border">
            {keys.map((key) => {
              const parts = keyParts(key);
              const isSelected = selected === key.id;
              return (
                <button
                  key={key.id}
                  type="button"
                  className={cn(
                    "flex min-h-10 w-full items-center gap-3 px-3 py-2 text-left text-sm transition hover:bg-surface-muted",
                    isSelected && "bg-primary-soft",
                  )}
                  onClick={() => select(key.id)}
                >
                  <RiKey2Line className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden />
                  <span className="min-w-0 flex-1 truncate font-medium text-text-primary">
                    {key.name || "Unnamed key"}
                  </span>
                  <span className="hidden text-xs text-text-secondary sm:inline">{parts.type}</span>
                  <span className="hidden max-w-36 truncate font-mono text-xs text-text-secondary sm:inline">
                    {parts.fingerprint}
                  </span>
                  {isSelected ? (
                    <RiCheckboxCircleLine className="h-4 w-4 shrink-0 text-primary" aria-label="Selected" />
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
        <button
          type="button"
          className="mt-3 inline-flex h-10 items-center gap-2 rounded-md px-2 text-sm font-medium text-primary hover:bg-primary-soft"
          onClick={() => setOpenAdd(true)}
        >
          <RiAddLine className="h-4 w-4" aria-hidden />
          Add new SSH key
        </button>
        <KeyAddModal open={openAdd} onClose={() => setOpenAdd(false)} onAdded={addKey} />
      </div>
    );
  }

  // Default grid layout
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Tile />
      {keys.map((k) => (<Tile key={k.id} k={k} />))}
      <KeyAddModal open={openAdd} onClose={() => setOpenAdd(false)} onAdded={addKey} />
    </div>
  );
}
