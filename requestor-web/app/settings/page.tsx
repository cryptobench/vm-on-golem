"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { loadSettings, saveSettings, type SSHKey } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { Modal } from "../../components/ui/Modal";
import { KeyPicker } from "../../components/ssh/KeyPicker";
import { Skeleton } from "../../components/ui/Skeleton";

export default function SettingsPage() {
  const router = useRouter();
  const { ads, setAds, profiles, activeId, setActive, addProfile, removeProfile, renameProfile } = useAds();
  // Mount gate to avoid hydration mismatches from localStorage/env reads
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => { setMounted(true); }, []);

  // Initialize settings state after mount
  const [sp, setSp] = React.useState<string>(process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || "");
  const [glm, setGlm] = React.useState<string>(process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || "");
  const [sshKeys, setSshKeys] = React.useState<SSHKey[]>([]);
  const [defaultKeyId, setDefaultKeyId] = React.useState<string | undefined>(undefined);
  const [saved, setSaved] = React.useState(false);
  const [displayCurrency, setDisplayCurrency] = React.useState<'fiat'|'token'>('fiat');
  const [mode, setMode] = React.useState<"golem-base"|"central">(ads.mode);
  const [disc, setDisc] = React.useState<string>(ads.discovery_url);
  const [rpc, setRpc] = React.useState<string>(ads.golem_base_rpc_url);
  const [chainIdText, setChainIdText] = React.useState<string>(() => {
    try { return '0x' + ads.chain_id.toString(16); } catch { return String(ads.chain_id || ''); }
  });
  const [ws, setWs] = React.useState<string>(ads.golem_base_ws_url);
  const [profileName, setProfileName] = React.useState<string>(profiles.find(p => p.id === activeId)?.name || "");
  const [pendingProvider, setPendingProvider] = React.useState<string | null>(null);
  // SSH key add handled by KeyPicker
  const [tab, setTab] = React.useState<'connections'|'payments'|'ssh'>('connections');

  React.useEffect(() => {
    try {
      const p = localStorage.getItem('requestor_pending_rent');
      if (p) setPendingProvider(p);
    } catch {}
  }, []);

  // Load persisted requestor settings on mount
  React.useEffect(() => {
    if (!mounted) return;
    const initial = loadSettings();
    setSp(initial.stream_payment_address || (process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || ""));
    setGlm(initial.glm_token_address || (process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || ""));
    const keys: SSHKey[] = initial.ssh_keys || (initial.ssh_public_key ? [{ id: 'default', name: 'Default', value: initial.ssh_public_key }] : []);
    setSshKeys(keys);
    setDefaultKeyId(initial.default_ssh_key_id || (keys[0]?.id) || (initial.ssh_public_key ? 'default' : undefined));
    setDisplayCurrency(initial.display_currency === 'token' ? 'token' : 'fiat');
    // Sync ads-derived fields (profiles/context already mounted)
    setMode(ads.mode);
    setDisc(ads.discovery_url);
    setRpc(ads.golem_base_rpc_url);
    setWs(ads.golem_base_ws_url);
    try { setChainIdText('0x' + ads.chain_id.toString(16)); } catch { setChainIdText(String(ads.chain_id || '')); }
    setProfileName(profiles.find(p => p.id === activeId)?.name || "");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted]);

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

  // Render skeletons until mounted to avoid hydration mismatch
  if (!mounted) {
    return (
      <div className="space-y-4">
        <h2>Settings</h2>
        <div className="grid max-w-3xl gap-4">
          <div className="card">
            <div className="card-body grid gap-3">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-5 w-64" />
              <Skeleton className="h-10 w-full" />
              <div className="flex items-center gap-3 pt-2">
                <Skeleton className="h-10 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

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
      {/* Tabs header */}
      <div className="border-b">
        <nav className="-mb-px flex flex-wrap gap-3 text-sm">
          <button className={(tab === 'connections' ? 'border-brand-600 text-brand-700' : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300') + ' whitespace-nowrap border-b-2 px-3 py-2'} onClick={() => setTab('connections')}>Connections</button>
          <button className={(tab === 'payments' ? 'border-brand-600 text-brand-700' : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300') + ' whitespace-nowrap border-b-2 px-3 py-2'} onClick={() => setTab('payments')}>Payments</button>
          <button className={(tab === 'ssh' ? 'border-brand-600 text-brand-700' : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300') + ' whitespace-nowrap border-b-2 px-3 py-2'} onClick={() => setTab('ssh')}>SSH Keys</button>
        </nav>
      </div>

      {tab === 'connections' && (
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
                <div className="flex items-center gap-3 pt-2">
                  <button className="btn btn-primary" onClick={save}>Save</button>
                  {saved && <span className="text-sm text-green-600">Saved</span>}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'payments' && (
        <div className="grid max-w-3xl gap-4">
          <div className="card">
            <div className="card-body grid gap-3">
              <div>
                <label className="label">Price display</label>
                <select className="input w-48" value={displayCurrency} onChange={(e) => { const v = (e.target.value as 'fiat'|'token'); setDisplayCurrency(v); saveSettings({ display_currency: v }); }}>
                  <option value="fiat">Fiat (USD)</option>
                  <option value="token">Token (native / GLM)</option>
                </select>
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
            </div>
          </div>
        </div>
      )}

      {tab === 'ssh' && (
        <div className="grid max-w-4xl gap-4">
          <div className="card">
            <div className="card-body">
              <div className="text-sm font-medium">SSH Keys</div>
              <div className="mt-2 text-sm text-gray-600">Add keys, pick a default.</div>
              <div className="mt-4">
                <KeyPicker value={defaultKeyId} onChange={(id) => setDefaultKeyId(id)} />
              </div>
              <div className="mt-4 flex items-center gap-3">
                <button className="btn btn-primary" onClick={save}>Save</button>
                {saved && <span className="text-sm text-green-600">Saved</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SSH key add handled by KeyPicker */}
    </div>
  );
}
