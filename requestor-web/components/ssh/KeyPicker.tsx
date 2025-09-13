"use client";
import React from "react";
import { loadSettings, saveSettings, type SSHKey } from "../../lib/api";
import { KeyAddModal } from "./KeyAddModal";

export function KeyPicker({ value, onChange }: { value?: string; onChange: (id: string, key: SSHKey) => void }) {
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

  const select = (id: string) => {
    setSelected(id);
    const k = keys.find(x => x.id === id);
    if (k) onChange(id, k);
    const prev = loadSettings();
    saveSettings({
      ssh_keys: keys,
      default_ssh_key_id: id,
      stream_payment_address: prev.stream_payment_address,
      glm_token_address: prev.glm_token_address,
    });
  };

  const remove = (id: string) => {
    const next = keys.filter(k => k.id !== id);
    setKeys(next);
    const newSel = selected === id ? next[0]?.id : selected;
    if (newSel && next.find(k => k.id === newSel)) select(newSel);
    const prev = loadSettings();
    saveSettings({
      ssh_keys: next,
      default_ssh_key_id: (newSel && next.some(k => k.id === newSel)) ? newSel : next[0]?.id,
      stream_payment_address: prev.stream_payment_address,
      glm_token_address: prev.glm_token_address,
    });
  };

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <button
        className="relative flex h-36 items-center justify-center rounded-xl border-2 border-dashed border-gray-300 bg-white text-gray-600 hover:border-brand-400 hover:text-brand-700"
        onClick={() => setOpenAdd(true)}
      >
        <div className="text-center">
          <div className="text-2xl">＋</div>
          <div className="mt-1 text-sm font-medium">Add SSH Key</div>
        </div>
      </button>
      {keys.map((k) => {
        const sel = selected === k.id;
        const parts = (k.value || '').split(' ');
        const type = parts[0] || '';
        const short = parts[1] ? `${parts[1].slice(0, 12)}…${parts[1].slice(-8)}` : '';
        return (
          <button
            key={k.id}
            className={"relative h-36 rounded-xl border bg-white p-3 text-left shadow-sm transition-colors " + (sel ? 'border-brand-500 ring-1 ring-brand-300' : 'hover:border-gray-300')}
            onClick={() => select(k.id)}
            title={sel ? 'Default SSH key' : 'Set as default'}
          >
            <div className={"absolute right-2 top-2 h-6 w-6 rounded-full border-2 " + (sel ? 'border-brand-500 bg-brand-500 text-white' : 'border-gray-300 bg-white text-transparent')}>
              <svg viewBox="0 0 20 20" className="h-full w-full p-0.5"><path fill="currentColor" d="M7.629 13.233L4.4 10.004l1.414-1.414l1.815 1.815l0.001-0.001L14.186 3.85l1.414 1.414l-7.971 7.971z"/></svg>
            </div>
            <div className="mt-1 text-sm font-medium truncate pr-8">{k.name || 'Unnamed key'}</div>
            <div className="mt-1 text-xs text-gray-500">{type}</div>
            <div className="mt-1 text-xs font-mono text-gray-600 truncate">{short}</div>
            <div className="absolute bottom-2 right-2 flex gap-2">
              <button className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100" onClick={(e) => { e.stopPropagation(); remove(k.id); }}>Delete</button>
            </div>
          </button>
        );
      })}
      <KeyAddModal open={openAdd} onClose={() => setOpenAdd(false)} onAdded={(key) => {
        const next = [...keys, key];
        setKeys(next);
        select(key.id);
      }} />
    </div>
  );
}

