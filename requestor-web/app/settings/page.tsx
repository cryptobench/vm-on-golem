"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { loadSettings, saveSettings, type SSHKey } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { Modal } from "../../components/ui/Modal";

export default function SettingsPage() {
  const router = useRouter();
  const { ads, setAds, profiles, activeId, setActive, addProfile, removeProfile, renameProfile } = useAds();
  const initial = loadSettings();
  const [sp, setSp] = React.useState(loadSettings().stream_payment_address || (process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || ""));
  const [glm, setGlm] = React.useState(loadSettings().glm_token_address || (process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || ""));
  const [sshKeys, setSshKeys] = React.useState<SSHKey[]>(initial.ssh_keys || (initial.ssh_public_key ? [{ id: 'default', name: 'Default', value: initial.ssh_public_key }] : []));
  const [defaultKeyId, setDefaultKeyId] = React.useState<string | undefined>(initial.default_ssh_key_id || (initial.ssh_keys && initial.ssh_keys[0]?.id) || (initial.ssh_public_key ? 'default' : undefined));
  const [saved, setSaved] = React.useState(false);
  const [displayCurrency, setDisplayCurrency] = React.useState<'fiat'|'token'>(initial.display_currency === 'token' ? 'token' : 'fiat');
  const [mode, setMode] = React.useState<"golem-base"|"central">(ads.mode);
  const [disc, setDisc] = React.useState<string>(ads.discovery_url);
  const [rpc, setRpc] = React.useState<string>(ads.golem_base_rpc_url);
  const [chainIdText, setChainIdText] = React.useState<string>(() => {
    try { return '0x' + ads.chain_id.toString(16); } catch { return String(ads.chain_id || ''); }
  });
  const [ws, setWs] = React.useState<string>(ads.golem_base_ws_url);
  const [profileName, setProfileName] = React.useState<string>(profiles.find(p => p.id === activeId)?.name || "");
  const [pendingProvider, setPendingProvider] = React.useState<string | null>(null);
  const [showAddKey, setShowAddKey] = React.useState(false);
  const [newKeyName, setNewKeyName] = React.useState("");
  const [newKeyValue, setNewKeyValue] = React.useState("");
  const [addError, setAddError] = React.useState<string | null>(null);

  React.useEffect(() => {
    try {
      const p = localStorage.getItem('requestor_pending_rent');
      if (p) setPendingProvider(p);
    } catch {}
  }, []);

  const save = () => {
    saveSettings({ ssh_keys: sshKeys, default_ssh_key_id: defaultKeyId, stream_payment_address: sp, glm_token_address: glm, display_currency: displayCurrency });
    // Parse chain id from text (accept hex 0x.. or decimal)
    let cid = ads.chain_id;
    const t = (chainIdText || '').trim();
    if (t) {
      try { cid = t.startsWith('0x') ? parseInt(t, 16) : parseInt(t, 10); } catch {}
    }
    setAds({
      mode,
      discovery_url: disc,
      golem_base_rpc_url: rpc,
      golem_base_ws_url: ws,
      chain_id: Number.isFinite(cid) && cid > 0 ? cid : ads.chain_id,
      advertisement_interval_seconds: ads.advertisement_interval_seconds,
    });
    if (profileName.trim().length) renameProfile(activeId, profileName.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="space-y-4">
      <h2>Settings</h2>
      {pendingProvider && (
        <div className="card">
          <div className="card-body flex items-center justify-between gap-3">
            <div className="text-sm text-gray-700">Continue renting from <span className="font-mono">{pendingProvider}</span>?</div>
            <div className="flex gap-2">
              <button className="btn btn-secondary" onClick={() => { try { localStorage.removeItem('requestor_pending_rent'); } catch {}; setPendingProvider(null); }}>Dismiss</button>
              <button className="btn btn-primary" onClick={() => router.push('/providers')}>Return to Providers</button>
            </div>
          </div>
        </div>
      )}
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
                    <label className="label">Payments Chain ID (hex or decimal)</label>
                    <input className="input" value={chainIdText} onChange={e => setChainIdText(e.target.value)} placeholder="0x6013a" />
                  </div>
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
              <label className="label">Price display</label>
              <select
                className="input w-48"
                value={displayCurrency}
                onChange={(e) => {
                  const v = (e.target.value as 'fiat'|'token');
                  setDisplayCurrency(v);
                  // Persist immediately so other views react without needing full Save
                  saveSettings({ display_currency: v });
                }}
              >
                <option value="fiat">Fiat (USD)</option>
                <option value="token">Token (native / GLM)</option>
              </select>
            </div>
            <div>
              <div className="text-sm font-medium">SSH Keys</div>
              <div className="mt-2 text-sm text-gray-600">Add keys, pick a default, Hetzner-style tiles.</div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {/* Add new key tile (opens modal) */}
                <button
                  className="relative flex h-36 items-center justify-center rounded-xl border-2 border-dashed border-gray-300 bg-white text-gray-600 hover:border-brand-400 hover:text-brand-700"
                  onClick={() => { setNewKeyName(""); setNewKeyValue(""); setAddError(null); setShowAddKey(true); }}
                >
                  <div className="text-center">
                    <div className="text-2xl">＋</div>
                    <div className="mt-1 text-sm font-medium">Add SSH Key</div>
                  </div>
                </button>

                {/* Existing keys as tiles */}
                {sshKeys.map((k) => {
                  const sel = defaultKeyId === k.id;
                  const parts = (k.value || '').split(' ');
                  const type = parts[0] || '';
                  const short = parts[1] ? `${parts[1].slice(0, 12)}…${parts[1].slice(-8)}` : '';
                  return (
                    <button
                      key={k.id}
                      className={
                        "relative h-36 rounded-xl border bg-white p-3 text-left shadow-sm transition-colors " +
                        (sel ? 'border-brand-500 ring-1 ring-brand-300' : 'hover:border-gray-300')
                      }
                      onClick={() => setDefaultKeyId(k.id)}
                      title={sel ? 'Default SSH key' : 'Set as default'}
                    >
                      {/* Checkmark */}
                      <div className={"absolute right-2 top-2 h-6 w-6 rounded-full border-2 " + (sel ? 'border-brand-500 bg-brand-500 text-white' : 'border-gray-300 bg-white text-transparent')}>
                        <svg viewBox="0 0 20 20" className="h-full w-full p-0.5"><path fill="currentColor" d="M7.629 13.233L4.4 10.004l1.414-1.414l1.815 1.815l0.001-0.001L14.186 3.85l1.414 1.414l-7.971 7.971z"/></svg>
                      </div>
                      <div className="mt-1 text-sm font-medium truncate pr-8">{k.name || 'Unnamed key'}</div>
                      <div className="mt-1 text-xs text-gray-500">{type}</div>
                      <div className="mt-1 text-xs font-mono text-gray-600 truncate">{short}</div>
                      <div className="absolute bottom-2 right-2 flex gap-2">
                        <button
                          className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
                          onClick={(e) => {
                            e.stopPropagation();
                            const next = sshKeys.filter(x => x.id !== k.id);
                            setSshKeys(next);
                            if (defaultKeyId === k.id) setDefaultKeyId(next[0]?.id);
                          }}
                        >Delete</button>
                      </div>
                    </button>
                  );
                })}
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
      {/* Add SSH Key Modal */}
      <Modal open={showAddKey} onClose={() => setShowAddKey(false)}>
        <div className="p-4">
          <h3 id="add-ssh-key-title" className="text-lg font-medium">Add SSH Key</h3>
          <div className="mt-3">
            <label className="label">Name</label>
            <input className="input" value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="Work Laptop" />
          </div>
          <div className="mt-3">
            <label className="label">Public key</label>
            <textarea className="input" rows={3} value={newKeyValue} onChange={(e) => setNewKeyValue(e.target.value)} placeholder="ssh-ed25519 AAAA... user@host" />
          </div>
          {addError && <div className="mt-2 text-sm text-red-600">{addError}</div>}
          <div className="mt-4 flex justify-end gap-2">
            <button className="btn btn-secondary" onClick={() => setShowAddKey(false)}>Cancel</button>
            <button
              className="btn btn-primary"
              onClick={() => {
                const name = newKeyName.trim();
                const value = newKeyValue.trim();
                // Basic validation: type and base64 part present
                const validType = /^(ssh-(ed25519|rsa)|ecdsa-sha2-nistp(256|384|521))\s+/.test(value);
                if (!name) { setAddError('Enter a name'); return; }
                if (!value || !validType || value.split(' ').length < 2) { setAddError('Enter a valid SSH public key'); return; }
                const id = Math.random().toString(36).slice(2, 10);
                const next = [...sshKeys, { id, name, value }];
                const newDefault = defaultKeyId || id;
                setSshKeys(next);
                if (!defaultKeyId) setDefaultKeyId(id);
                // Auto-save settings after adding (preserve currency)
                saveSettings({ ssh_keys: next, default_ssh_key_id: newDefault, stream_payment_address: sp, glm_token_address: glm, display_currency: displayCurrency });
                setSaved(true);
                setTimeout(() => setSaved(false), 1500);
                setShowAddKey(false);
              }}
            >Add</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
