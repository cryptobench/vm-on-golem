"use client";
import React from "react";
import { Modal } from "../ui/Modal";
import { loadSettings, saveSettings, type SSHKey } from "../../lib/api";

export function KeyAddModal({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded?: (key: SSHKey) => void }) {
  const [name, setName] = React.useState("");
  const [value, setValue] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const add = () => {
    const trimmedName = name.trim();
    const trimmedValue = value.trim();
    const validType = /^(ssh-(ed25519|rsa)|ecdsa-sha2-nistp(256|384|521))\s+/.test(trimmedValue);
    if (!trimmedName) { setError('Enter a name'); return; }
    if (!trimmedValue || !validType || trimmedValue.split(' ').length < 2) { setError('Enter a valid SSH public key'); return; }
    const id = Math.random().toString(36).slice(2, 10);
    const key: SSHKey = { id, name: trimmedName, value: trimmedValue };
    try {
      const prev = loadSettings();
      const list = [...(prev.ssh_keys || []), key];
      saveSettings({
        ssh_keys: list,
        default_ssh_key_id: prev.default_ssh_key_id || id,
        stream_payment_address: prev.stream_payment_address,
        glm_token_address: prev.glm_token_address,
      });
      onAdded?.(key);
      onClose();
    } catch {}
  };

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-4">
        <h3 className="text-lg font-medium">Add SSH Key</h3>
        <div className="mt-3">
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Work Laptop" />
        </div>
        <div className="mt-3">
          <label className="label">Public key</label>
          <textarea className="input" rows={3} value={value} onChange={(e) => setValue(e.target.value)} placeholder="ssh-ed25519 AAAA... user@host" />
        </div>
        {error && <div className="mt-2 text-sm text-red-600">{error}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={add}>Add</button>
        </div>
      </div>
    </Modal>
  );
}

