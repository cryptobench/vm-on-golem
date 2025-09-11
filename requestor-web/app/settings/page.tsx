"use client";
import React from "react";
import { loadSettings, saveSettings, type SSHKey } from "../../lib/api";
import { useAds } from "../../context/AdsContext";

export default function SettingsPage() {
  const { ads, setAds, profiles, activeId, setActive, addProfile, removeProfile, renameProfile } = useAds();
  const initial = loadSettings();
  const [ssh, setSsh] = React.useState(initial.ssh_public_key || "");
  const [sp, setSp] = React.useState(loadSettings().stream_payment_address || (process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || ""));
  const [glm, setGlm] = React.useState(loadSettings().glm_token_address || (process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || ""));
  const [sshKeys, setSshKeys] = React.useState<SSHKey[]>(initial.ssh_keys || (initial.ssh_public_key ? [{ id: 'default', name: 'Default', value: initial.ssh_public_key }] : []));
  const [saved, setSaved] = React.useState(false);
  const [mode, setMode] = React.useState<"golem-base"|"central">(ads.mode);
  const [disc, setDisc] = React.useState<string>(ads.discovery_url);
  const [rpc, setRpc] = React.useState<string>(ads.golem_base_rpc_url);
  const [ws, setWs] = React.useState<string>(ads.golem_base_ws_url);
  const [profileName, setProfileName] = React.useState<string>(profiles.find(p => p.id === activeId)?.name || "");

  const save = () => {
    saveSettings({ ssh_public_key: ssh, ssh_keys: sshKeys, stream_payment_address: sp, glm_token_address: glm });
    setAds({
      mode,
      discovery_url: disc,
      golem_base_rpc_url: rpc,
      golem_base_ws_url: ws,
      chain_id: ads.chain_id,
      advertisement_interval_seconds: ads.advertisement_interval_seconds,
    });
    if (profileName.trim().length) renameProfile(activeId, profileName.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="space-y-4">
      <h2>Settings</h2>
      <div className="grid max-w-3xl gap-4">
        <div className="card">
          <div className="card-body grid gap-3">
            <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end">
              <div>
                <label className="label">Active advertisement server</label>
                <select className="input" value={activeId} onChange={(e) => { const id = e.target.value; setActive(id); const p = profiles.find(x => x.id === id); if (p) { setProfileName(p.name); setMode(p.config.mode); setDisc(p.config.discovery_url); setRpc(p.config.golem_base_rpc_url); setWs(p.config.golem_base_ws_url); } }}>
                  {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <button className="btn btn-secondary" onClick={() => addProfile(`Profile ${profiles.length + 1}`)}>{"New profile"}</button>
              <button className="btn btn-danger" onClick={() => removeProfile(activeId)} disabled={profiles.length <= 1}>Delete</button>
            </div>
            <div>
              <label className="label">Profile name</label>
              <input className="input" value={profileName} onChange={(e) => setProfileName(e.target.value)} placeholder="Default" />
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-body">
            <div className="text-sm font-medium">Advertisement Server</div>
            <div className="mt-3 grid gap-3">
              <div>
                <label className="label">Mode</label>
                <select className="input" value={mode} onChange={e => setMode(e.target.value as any)}>
                  <option value="golem-base">Golem Base (default)</option>
                  <option value="central">Central Discovery</option>
                </select>
              </div>
              {mode === 'central' ? (
                <div>
                  <label className="label">Discovery URL</label>
                  <input className="input" value={disc} onChange={e => setDisc(e.target.value)} placeholder="http://host:9001/api/v1" />
                </div>
              ) : (
                <>
                  <div>
                    <label className="label">Golem Base RPC URL</label>
                    <input className="input" value={rpc} onChange={e => setRpc(e.target.value)} placeholder="https://.../rpc" />
                  </div>
                  <div>
                    <label className="label">Golem Base WS URL</label>
                    <input className="input" value={ws} onChange={e => setWs(e.target.value)} placeholder="wss://.../rpc/ws" />
                  </div>
                </>
              )}
              <div className="text-sm text-gray-600">
                Listing and provider resolution use the selected server configuration.
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body grid gap-3">
            <div>
              <label className="label">SSH public key</label>
              <textarea className="input" value={ssh} onChange={e => setSsh(e.target.value)} rows={4} placeholder="ssh-ed25519 AAAA... user@host"/>
            </div>
            <div className="pt-2">
              <div className="text-sm font-medium">SSH Keys</div>
              <div className="mt-2 text-sm text-gray-600">Store multiple named keys for quick selection when provisioning.</div>
              <div className="mt-3 grid gap-3">
                {sshKeys.map((k, idx) => (
                  <div key={k.id} className="rounded-lg border p-3">
                    <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-start">
                      <div>
                        <label className="label">Name</label>
                        <input className="input" value={k.name} onChange={(e) => { const copy=[...sshKeys]; copy[idx] = { ...k, name: e.target.value }; setSshKeys(copy); }} />
                      </div>
                      <button className="btn btn-danger mt-6 sm:mt-0" onClick={() => setSshKeys(sshKeys.filter(x => x.id !== k.id))}>Delete</button>
                    </div>
                    <div className="mt-2">
                      <label className="label">Public key</label>
                      <textarea className="input" rows={3} value={k.value} onChange={(e) => { const copy=[...sshKeys]; copy[idx] = { ...k, value: e.target.value }; setSshKeys(copy); }} placeholder="ssh-ed25519 AAAA... user@host"/>
                    </div>
                  </div>
                ))}
                <div>
                  <button className="btn btn-secondary" onClick={() => setSshKeys([...sshKeys, { id: Math.random().toString(36).slice(2, 10), name: `Key ${sshKeys.length + 1}`, value: '' }])}>Add key</button>
                </div>
              </div>
            </div>
            <div>
              <label className="label">StreamPayment address</label>
              <input className="input" value={sp} onChange={e => setSp(e.target.value)} placeholder="0x..." />
            </div>
            <div>
              <label className="label">GLM token address (0x0.. for native)</label>
              <input className="input" value={glm} onChange={e => setGlm(e.target.value)} placeholder="0x..." />
            </div>
            <div className="flex items-center gap-3 pt-2">
              <button className="btn btn-primary" onClick={save}>Save</button>
              {saved && <span className="text-sm text-green-600">Saved</span>}
            </div>
            <div className="text-sm text-gray-600">
              Discovery: {process.env.NEXT_PUBLIC_DISCOVERY_API_URL} | Proxy: {process.env.NEXT_PUBLIC_PORT_CHECKER_URL}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
