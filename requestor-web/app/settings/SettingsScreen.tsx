"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { loadSettings, saveSettings, type SSHKey } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { getRequestorRuntimeConfig } from "../../lib/runtimeConfig";
import { KeyPicker } from "../../components/ssh/KeyPicker";
import { Button } from "@golem/ui";
import { FormField, SelectInput, TextInput } from "@golem/ui";
import { PageHeader } from "@golem/ui";
import { Skeleton } from "@golem/ui";
import { Tabs, type TabItem } from "@golem/ui";

type SettingsTab = "connections" | "payments" | "ssh";

const SETTINGS_TABS: Array<TabItem<SettingsTab>> = [
  { id: "connections", label: "Connections" },
  { id: "payments", label: "Payments" },
  { id: "ssh", label: "SSH Keys" },
];

export default function SettingsPage() {
  const router = useRouter();
  const { ads, setAds, profiles, activeId, setActive, addProfile, removeProfile, renameProfile } = useAds();
  // Mount gate to avoid hydration mismatches from localStorage/env reads
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => { setMounted(true); }, []);

  // Initialize settings state after mount
  const runtimeConfig = getRequestorRuntimeConfig();
  const [sp, setSp] = React.useState<string>(runtimeConfig.streamPaymentAddress || "");
  const [glm, setGlm] = React.useState<string>(runtimeConfig.glmTokenAddress || "");
  const [sshKeys, setSshKeys] = React.useState<SSHKey[]>([]);
  const [defaultKeyId, setDefaultKeyId] = React.useState<string | undefined>(undefined);
  const [saved, setSaved] = React.useState(false);
  const [displayCurrency, setDisplayCurrency] = React.useState<'fiat'|'token'>('fiat');
  const [mode, setMode] = React.useState<"arkiv"|"central">(ads.mode);
  const [disc, setDisc] = React.useState<string>(ads.discovery_url);
  const [rpc, setRpc] = React.useState<string>(ads.arkiv_rpc_url);
  const [ws, setWs] = React.useState<string>(ads.arkiv_ws_url);
  const [evmChainIdText, setEvmChainIdText] = React.useState<string>(runtimeConfig.evmChainId || "0x88bb0");
  const [evmChainName, setEvmChainName] = React.useState<string>(runtimeConfig.evmChainName || "Ethereum Hoodi");
  const [evmRpcUrl, setEvmRpcUrl] = React.useState<string>(runtimeConfig.evmRpcUrl || "https://rpc.hoodi.ethpandaops.io");
  const [evmExplorerUrl, setEvmExplorerUrl] = React.useState<string>(runtimeConfig.evmExplorerUrl || "https://hoodi.etherscan.io");
  const [profileName, setProfileName] = React.useState<string>(profiles.find(p => p.id === activeId)?.name || "");
  const [pendingProvider, setPendingProvider] = React.useState<string | null>(null);
  // SSH key add handled by KeyPicker
  const [tab, setTab] = React.useState<SettingsTab>('connections');

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
    const runtimeConfig = getRequestorRuntimeConfig();
    setSp(initial.stream_payment_address || (runtimeConfig.streamPaymentAddress || ""));
    setGlm(initial.glm_token_address || (runtimeConfig.glmTokenAddress || ""));
    const keys: SSHKey[] = initial.ssh_keys || (initial.ssh_public_key ? [{ id: 'default', name: 'Default', value: initial.ssh_public_key }] : []);
    setSshKeys(keys);
    setDefaultKeyId(initial.default_ssh_key_id || (keys[0]?.id) || (initial.ssh_public_key ? 'default' : undefined));
    setDisplayCurrency(initial.display_currency === 'token' ? 'token' : 'fiat');
    setEvmChainIdText(initial.evm_chain_id || (runtimeConfig.evmChainId || "0x88bb0"));
    setEvmChainName(initial.evm_chain_name || (runtimeConfig.evmChainName || "Ethereum Hoodi"));
    setEvmRpcUrl(initial.evm_rpc_url || (runtimeConfig.evmRpcUrl || "https://rpc.hoodi.ethpandaops.io"));
    setEvmExplorerUrl(initial.evm_explorer_url || (runtimeConfig.evmExplorerUrl || "https://hoodi.etherscan.io"));
    // Sync ads-derived fields (profiles/context already mounted)
    setMode(ads.mode);
    setDisc(ads.discovery_url);
    setRpc(ads.arkiv_rpc_url);
    setWs(ads.arkiv_ws_url);
    setProfileName(profiles.find(p => p.id === activeId)?.name || "");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted]);

  const save = () => {
    saveSettings({
      ssh_keys: sshKeys,
      default_ssh_key_id: defaultKeyId,
      stream_payment_address: sp,
      glm_token_address: glm,
      evm_chain_id: evmChainIdText.trim(),
      evm_chain_name: evmChainName.trim(),
      evm_rpc_url: evmRpcUrl.trim(),
      evm_explorer_url: evmExplorerUrl.trim(),
      display_currency: displayCurrency,
    });
    setAds({
      mode,
      discovery_url: disc,
      arkiv_rpc_url: rpc,
      arkiv_ws_url: ws,
      chain_id: ads.chain_id,
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
        <PageHeader title="Settings" />
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
      <PageHeader title="Settings" />
      {pendingProvider && (
        <div className="card">
          <div className="card-body flex items-center justify-between gap-3">
            <div className="text-sm text-text-secondary">Continue renting from <span className="font-mono">{pendingProvider}</span>?</div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => { try { localStorage.removeItem('requestor_pending_rent'); } catch {}; setPendingProvider(null); }}>Dismiss</Button>
              <Button onClick={() => router.push('/providers')}>Return to Providers</Button>
            </div>
          </div>
        </div>
      )}
      <Tabs tabs={SETTINGS_TABS} active={tab} onChange={setTab} />

      {tab === 'connections' && (
        <div className="grid max-w-3xl gap-4">
          <div className="card">
            <div className="card-body grid gap-3">
              <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end">
                <FormField label="Active profile">
                  <SelectInput value={activeId} onChange={(e) => { const id = e.target.value; setActive(id); const p = profiles.find(x => x.id === id); if (p) { setProfileName(p.name); setMode(p.config.mode); setDisc(p.config.discovery_url); setRpc(p.config.arkiv_rpc_url); setWs(p.config.arkiv_ws_url); } }}>
                    {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </SelectInput>
                </FormField>
                <Button variant="secondary" onClick={() => addProfile(`Profile ${profiles.length + 1}`)}>New profile</Button>
                <Button variant="danger" onClick={() => removeProfile(activeId)} disabled={profiles.length <= 1}>Delete</Button>
              </div>
              <FormField label="Profile name">
                <TextInput value={profileName} onChange={(e) => setProfileName(e.target.value)} placeholder="Default" />
              </FormField>
            </div>
          </div>
          <div className="card">
            <div className="card-body">
              <div className="text-sm font-medium">Discovery & Network</div>
              <div className="mt-3 grid gap-3">
                <FormField label="Mode">
                  <SelectInput value={mode} onChange={e => setMode(e.target.value as "arkiv" | "central")}>
                    <option value="arkiv">Arkiv</option>
                    <option value="central">Central Discovery</option>
                  </SelectInput>
                </FormField>
                {mode === 'central' ? (
                  <FormField label="Central discovery URL">
                    <TextInput value={disc} onChange={e => setDisc(e.target.value)} placeholder="http://host:9001/api/v1" />
                  </FormField>
                ) : (
                  <>
                    <FormField label="Arkiv RPC URL">
                      <TextInput value={rpc} onChange={e => setRpc(e.target.value)} placeholder="https://.../rpc" />
                    </FormField>
                    <FormField label="Arkiv WS URL">
                      <TextInput value={ws} onChange={e => setWs(e.target.value)} placeholder="wss://.../rpc/ws" />
                    </FormField>
                  </>
                )}
                <div className="text-sm text-text-secondary">
                  Listing and provider resolution use the selected server configuration.
                </div>
                <div className="flex items-center gap-3 pt-2">
                  <Button onClick={save}>Save</Button>
                  {saved && <span className="text-sm text-success">Saved</span>}
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
              <FormField label="Price unit">
                <SelectInput className="w-48" value={displayCurrency} onChange={(e) => { const v = (e.target.value as 'fiat'|'token'); setDisplayCurrency(v); saveSettings({ display_currency: v }); }}>
                  <option value="fiat">Fiat (USD)</option>
                  <option value="token">Token (GLM)</option>
                </SelectInput>
              </FormField>
              <FormField label="StreamPayment contract address">
                <TextInput value={sp} onChange={e => setSp(e.target.value)} placeholder="0x..." />
              </FormField>
              <FormField label="GLM token address">
                <TextInput value={glm} onChange={e => setGlm(e.target.value)} placeholder="0x..." />
              </FormField>
              <FormField label="Payments chain ID (hex or decimal)">
                <TextInput value={evmChainIdText} onChange={e => setEvmChainIdText(e.target.value)} placeholder="0x88bb0" />
              </FormField>
              <FormField label="Payments chain name">
                <TextInput value={evmChainName} onChange={e => setEvmChainName(e.target.value)} placeholder="Ethereum Hoodi" />
              </FormField>
              <FormField label="Payments RPC URL">
                <TextInput value={evmRpcUrl} onChange={e => setEvmRpcUrl(e.target.value)} placeholder="https://.../rpc" />
              </FormField>
              <FormField label="Payments explorer URL">
                <TextInput value={evmExplorerUrl} onChange={e => setEvmExplorerUrl(e.target.value)} placeholder="https://..." />
              </FormField>
              <div className="flex items-center gap-3 pt-2">
                <Button onClick={save}>Save</Button>
                {saved && <span className="text-sm text-success">Saved</span>}
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
              <div className="mt-2 text-sm text-text-secondary">Add keys, pick a default.</div>
              <div className="mt-4">
                <KeyPicker value={defaultKeyId} onChange={(id) => setDefaultKeyId(id)} />
              </div>
              <div className="mt-4 flex items-center gap-3">
                <Button onClick={save}>Save</Button>
                {saved && <span className="text-sm text-success">Saved</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SSH key add handled by KeyPicker */}
    </div>
  );
}
