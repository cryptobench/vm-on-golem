"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { fetchProviders, computeEstimate, providerInfo } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { Spinner } from "../../components/ui/Spinner";
import { TableSkeleton } from "../../components/ui/Skeleton";

export default function ProvidersPage() {
  const displayCurrency = ((typeof window !== 'undefined' && (JSON.parse(localStorage.getItem('requestor_settings_v1') || '{}')?.display_currency === 'token')) ? 'token' : 'fiat');
  const [cpu, setCpu] = React.useState<number | undefined>();
  const [memory, setMemory] = React.useState<number | undefined>();
  const [storage, setStorage] = React.useState<number | undefined>();
  const [country, setCountry] = React.useState<string>("");
  const [platform, setPlatform] = React.useState<string>("");
  const [countries, setCountries] = React.useState<string[] | undefined>(undefined);
  const [maxUsd, setMaxUsd] = React.useState<number | undefined>(undefined);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [rows, setRows] = React.useState<any[]>([]);

  const { ads } = useAds();

  const search = async () => {
    setLoading(true); setError(null);
    try {
      let data = await fetchProviders({ cpu, memory, storage, country: (countries && countries.length && !country) ? undefined : (country || undefined), platform: platform || undefined }, ads);
      // Apply multi-country filter client-side if provided
      if (countries && countries.length) {
        const setC = new Set(countries.map(c => c.trim().toUpperCase()));
        data = data.filter(p => (p.country ? setC.has(p.country.toUpperCase()) : false));
      }
      // Apply price cap if specified and we have full spec
      if (maxUsd != null && cpu != null && memory != null && storage != null) {
        data = data.filter(p => {
          const est = computeEstimate(p, cpu, memory, storage);
          return est && est.usd_per_month <= maxUsd;
        });
      }
      setRows(data);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally { setLoading(false); }
  };

  React.useEffect(() => {
    // Pre-fill from quick create wizard if present
    try {
      const raw = localStorage.getItem('requestor_pending_create');
      if (raw) {
        const data = JSON.parse(raw);
        if (data.cpu != null) setCpu(Number(data.cpu));
        if (data.memory != null) setMemory(Number(data.memory));
        if (data.storage != null) setStorage(Number(data.storage));
        if (Array.isArray(data.countries) && data.countries.length) { setCountries(data.countries); setCountry(""); }
        else if (data.country) setCountry(String(data.country));
        if (data.platform) setPlatform(String(data.platform));
        if (data.max_usd_per_month != null) setMaxUsd(Number(data.max_usd_per_month));
        localStorage.removeItem('requestor_pending_create');
        // trigger search after state applied
        setTimeout(() => search(), 0);
        return;
      }
    } catch {}
    search();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2>Providers</h2>
      </div>
      <div className="card">
        <div className="card-body">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label">CPU</label>
              <input className="input w-24" type="number" min={1} value={cpu ?? ''} onChange={e => setCpu(e.target.value ? Number(e.target.value) : undefined)} />
            </div>
            <div>
              <label className="label">Memory (GB)</label>
              <input className="input w-24" type="number" min={1} value={memory ?? ''} onChange={e => setMemory(e.target.value ? Number(e.target.value) : undefined)} />
            </div>
            <div>
              <label className="label">Disk (GB)</label>
              <input className="input w-24" type="number" min={1} value={storage ?? ''} onChange={e => setStorage(e.target.value ? Number(e.target.value) : undefined)} />
            </div>
            <div>
              <label className="label">Country</label>
              <input className="input" value={country} onChange={e => setCountry(e.target.value)} placeholder="US, PL, ..." />
            </div>
            <div>
              <label className="label">Platform</label>
              <select className="input" value={platform} onChange={e => setPlatform(e.target.value)}>
                <option value="">Any</option>
                <option value="x86_64">x86_64</option>
                <option value="arm64">arm64</option>
              </select>
            </div>
            <div>
              <label className="label">Max $/mo</label>
              <input className="input w-28" type="number" min={0} value={maxUsd ?? ''} onChange={e => setMaxUsd(e.target.value ? Number(e.target.value) : undefined)} placeholder="cap" />
            </div>
            <div className="ml-auto flex items-center gap-3">
              {loading && <Spinner />}
              <button className="btn btn-primary" onClick={search} disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
            </div>
          </div>
          {countries && countries.length > 0 && (
            <div className="mt-2 text-xs text-gray-500">Countries: {countries.join(', ')}</div>
          )}
          {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        </div>
      </div>
      <div className="card">
        <div className="card-body overflow-x-auto">
          {loading && rows.length === 0 ? (
            <TableSkeleton rows={6} cols={6} />
          ) : (
          <table className="table">
            <thead className="bg-gray-50">
              <tr>
                <th className="th">Provider</th>
                <th className="th">IP</th>
                <th className="th">Country</th>
                <th className="th">Platform</th>
                <th className="th text-right">CPU</th>
                <th className="th text-right">RAM</th>
                <th className="th text-right">Disk</th>
                <th className="th">Pricing</th>
                <th className="th">Estimate</th>
                <th className="th">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {rows.map((p) => {
                const est = cpu && memory && storage ? computeEstimate(p, cpu, memory, storage) : null;
                const pr = p.pricing || {} as any;
                const fmt = (n: any) => (n == null || Number.isNaN(Number(n))) ? null : Number(n);
                const coreM = fmt(pr.usd_per_core_month);
                const ramM = fmt(pr.usd_per_gb_ram_month);
                const stoM = fmt(pr.usd_per_gb_storage_month);
                const coreH = coreM != null ? +(coreM / 730).toFixed(6) : null;
                const ramH = ramM != null ? +(ramM / 730).toFixed(6) : null;
                const stoH = stoM != null ? +(stoM / 730).toFixed(6) : null;
                return (
                  <tr key={p.provider_id} className="hover:bg-gray-50/50">
                    <td className="td font-mono text-xs sm:text-sm">{p.provider_id}</td>
                    <td className="td">{p.ip_address || '—'}</td>
                    <td className="td">{p.country || '—'}</td>
                    <td className="td">{p.platform || '—'}</td>
                    <td className="td text-right">{p.resources?.cpu}</td>
                    <td className="td text-right">{p.resources?.memory}</td>
                    <td className="td text-right">{p.resources?.storage}</td>
                    <td className="td">
                      {(() => {
                        const pr = p.pricing || {} as any;
                        if (displayCurrency === 'token') {
                          const gCoreM = pr.glm_per_core_month != null ? Number(pr.glm_per_core_month).toFixed(6) : null;
                          const gRamM = pr.glm_per_gb_ram_month != null ? Number(pr.glm_per_gb_ram_month).toFixed(6) : null;
                          const gStoM = pr.glm_per_gb_storage_month != null ? Number(pr.glm_per_gb_storage_month).toFixed(6) : null;
                          const gCoreH = gCoreM != null ? (Number(gCoreM) / 730).toFixed(8) : null;
                          const gRamH = gRamM != null ? (Number(gRamM) / 730).toFixed(8) : null;
                          const gStoH = gStoM != null ? (Number(gStoM) / 730).toFixed(8) : null;
                          if (gCoreM == null && gRamM == null && gStoM == null) return '—';
                          return (
                            <div className="text-xs text-gray-700 space-y-0.5">
                              {gCoreM != null && (<div>Core: {gCoreM} GLM/mo <span className="text-gray-500">({gCoreH} GLM/hr)</span></div>)}
                              {gRamM != null && (<div>RAM: {gRamM} GLM/GB·mo <span className="text-gray-500">({gRamH} GLM/GB·hr)</span></div>)}
                              {gStoM != null && (<div>Storage: {gStoM} GLM/GB·mo <span className="text-gray-500">({gStoH} GLM/GB·hr)</span></div>)}
                            </div>
                          );
                        } else {
                          const uCoreM = pr.usd_per_core_month != null ? Number(pr.usd_per_core_month).toFixed(4) : null;
                          const uRamM = pr.usd_per_gb_ram_month != null ? Number(pr.usd_per_gb_ram_month).toFixed(4) : null;
                          const uStoM = pr.usd_per_gb_storage_month != null ? Number(pr.usd_per_gb_storage_month).toFixed(4) : null;
                          const uCoreH = uCoreM != null ? (Number(uCoreM) / 730).toFixed(6) : null;
                          const uRamH = uRamM != null ? (Number(uRamM) / 730).toFixed(6) : null;
                          const uStoH = uStoM != null ? (Number(uStoM) / 730).toFixed(6) : null;
                          if (uCoreM == null && uRamM == null && uStoM == null) return '—';
                          return (
                            <div className="text-xs text-gray-700 space-y-0.5">
                              {uCoreM != null && (<div>Core: ${uCoreM}/mo <span className="text-gray-500">({uCoreH}/hr)</span></div>)}
                              {uRamM != null && (<div>RAM: ${uRamM}/GB·mo <span className="text-gray-500">({uRamH}/GB·hr)</span></div>)}
                              {uStoM != null && (<div>Storage: ${uStoM}/GB·mo <span className="text-gray-500">({uStoH}/GB·hr)</span></div>)}
                            </div>
                          );
                        }
                      })()}
                    </td>
                    <td className="td">
                      {est ? (
                        <div className="text-xs sm:text-sm">
                          {displayCurrency === 'token' && est.glm_per_month != null ? (
                            <div>~{est.glm_per_month} GLM/mo <span className="text-gray-500">({(est.glm_per_month/730).toFixed(8)} GLM/hr)</span></div>
                          ) : (
                            <div>~${est.usd_per_month} <span className="text-gray-500">({est.usd_per_hour}/hr)</span></div>
                          )}
                        </div>
                      ) : '—'}
                    </td>
                    <td className="td">
                      <RentInline provider={p} defaultSpec={{ cpu, memory, storage }} adsMode={ads} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          )}
        </div>
      </div>
    </div>
  );
}

function RentInline({ provider, defaultSpec, adsMode }: { provider: any; defaultSpec: { cpu?: number; memory?: number; storage?: number }; adsMode: AdsConfig }) {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    try {
      const pending = localStorage.getItem('requestor_pending_rent');
      if (pending && pending === provider.provider_id) {
        localStorage.removeItem('requestor_pending_rent');
        setOpen(true);
      }
    } catch {}
  }, [provider.provider_id]);
  return (
    <>
      <button
        className="btn btn-secondary"
        onClick={() => setOpen(true)}
        disabled={open}
      >
        {open ? (<span className="inline-flex items-center gap-2"><Spinner className="h-4 w-4" /> Rent</span>) : 'Rent'}
      </button>
      {open && <RentDialog provider={provider} defaultSpec={defaultSpec} onClose={() => setOpen(false)} adsMode={adsMode} />}
    </>
  );
}

import { BrowserProvider, Contract, parseEther } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import erc20 from "../../public/abi/ERC20.json";
import { createVm, loadSettings, saveRentals, loadRentals, saveSettings, vmAccess, vmJobStatus, type AdsConfig, type SSHKey } from "../../lib/api";
import { Modal } from "../../components/ui/Modal";
import { useWallet } from "../../context/WalletContext";
import { useProjects } from "../../context/ProjectsContext";
import { ensureNetwork, getPaymentsChain } from "../../lib/chain";

function RentDialog({ provider, defaultSpec, onClose, adsMode }: { provider: any; defaultSpec: { cpu?: number; memory?: number; storage?: number }; onClose: () => void; adsMode: AdsConfig; }) {
  const router = useRouter();
  const displayCurrency = ((typeof window !== 'undefined' && (JSON.parse(localStorage.getItem('requestor_settings_v1') || '{}')?.display_currency === 'token')) ? 'token' : 'fiat');
  const { isInstalled, isConnected, connect, account } = useWallet();
  const { activeId: activeProjectId } = useProjects();
  const [name, setName] = React.useState("");
  const [cpu, setCpu] = React.useState<number>(defaultSpec.cpu || 1);
  const [memory, setMemory] = React.useState<number>(defaultSpec.memory || 2);
  const [storage, setStorage] = React.useState<number>(defaultSpec.storage || 20);
  const settings = loadSettings();
  const initialKeys: SSHKey[] = settings.ssh_keys || (settings.ssh_public_key ? [{ id: 'default', name: 'Default', value: settings.ssh_public_key }] : []);
  const defaultKeyId = settings.default_ssh_key_id || initialKeys[0]?.id || '';
  const [sshKeys, setSshKeys] = React.useState<SSHKey[]>(initialKeys);
  const [selectedKeyId, setSelectedKeyId] = React.useState<string>(defaultKeyId);
  const [sshKey, setSshKey] = React.useState<string>(() => {
    const found = initialKeys.find(k => k.id === defaultKeyId);
    return found?.value || settings.ssh_public_key || "";
  });
  const [showAddKey, setShowAddKey] = React.useState(false);
  const [newKeyName, setNewKeyName] = React.useState("");
  const [newKeyValue, setNewKeyValue] = React.useState("");
  const [addError, setAddError] = React.useState<string | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [streamId, setStreamId] = React.useState<string | null>(null);
  const [usingNative, setUsingNative] = React.useState<boolean>(true);
  const [connecting, setConnecting] = React.useState<boolean>(false);

  const est = computeEstimate(provider, cpu, memory, storage);

  const openStream = async () => {
    setError(null);
    const { ethereum } = window as any;
    if (!ethereum) throw new Error("MetaMask not detected");
    // Ensure wallet is on the expected payments chain (align with CLI defaults)
    await ensureNetwork(ethereum, getPaymentsChain());
    const providerInfoJson = await providerInfo(provider.provider_id, adsMode).catch(() => null);
    const cfg = loadSettings();
    const spAddr = (providerInfoJson?.stream_payment_address || cfg.stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();
    const glmAddr = (providerInfoJson?.glm_token_address || cfg.glm_token_address || process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || '').trim();
    if (!spAddr) throw new Error("StreamPayment address missing (set in Settings or provided by provider)");
    if (!est || est.glm_per_month == null) throw new Error("Provider does not advertise GLM pricing; cannot compute streaming rate");
    // Compute ratePerSecond (GLM per second -> wei)
    const glmPerSecond = est.glm_per_month / (730.0 * 3600.0);
    const ratePerSecondWei = BigInt(Math.floor(glmPerSecond * 1e18));
    // Simple default: deposit 1 hour
    const depositWei = ratePerSecondWei * BigInt(3600);

    const web3 = new BrowserProvider(ethereum);
    // Use the currently selected wallet account, not index 0
    const signer = await web3.getSigner(account ?? undefined);
    const sender = await signer.getAddress();
    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const recipient = provider.provider_id;
    const token = glmAddr;
    const ZERO = '0x0000000000000000000000000000000000000000';
    const isNative = token === ZERO;
    setUsingNative(isNative);

    // If using ERC20, ensure allowance covers the intended deposit
    if (!isNative) {
      const erc20c = new Contract(token, (erc20 as any).abi, signer);
      const current: bigint = await erc20c.allowance(sender, spAddr);
      if (current < depositWei) {
        const txApprove = await erc20c.approve(spAddr, depositWei);
        await txApprove.wait();
      }
    }

    const tx = await contract.createStream(token, recipient, depositWei, ratePerSecondWei, {
      value: isNative ? depositWei : 0n,
      gasLimit: 350000n,
    });
    const receipt = await tx.wait();
    let newStreamId: string | null = null;
    try {
      const evt = receipt?.logs?.map((l: any) => contract.interface.parseLog(l)).find((e: any) => e?.name === 'StreamCreated');
      if (evt) newStreamId = (evt.args?.streamId || evt.args?.[0])?.toString?.() || null;
    } catch {}
    if (!newStreamId) {
      // fallback: try callStatic
      try {
        const sim = await contract.createStream.staticCall(token, recipient, depositWei, ratePerSecondWei, {});
        newStreamId = sim?.toString?.() || null;
      } catch {}
    }
    if (!newStreamId) throw new Error("Could not determine streamId from tx receipt");
    setStreamId(newStreamId);
    return newStreamId;
  };

  const create = async () => {
    setCreating(true); setError(null);
    try {
      if (!sshKey) throw new Error("Provide your SSH public key in the form");
      const sid = streamId || await openStream();
      const payload = { name: name || `vm-${Math.random().toString(36).slice(2, 7)}`, resources: { cpu, memory, storage }, ssh_key: sshKey, stream_id: Number(sid) };
      const vm = await createVm(provider.provider_id, payload, adsMode);
      const rentals = loadRentals();
      const vmId = vm.id || vm.vm_id || payload.name;
      const jobId: string | undefined = vm.job_id;
      rentals.push({ name: payload.name, provider_id: provider.provider_id, provider_ip: provider.ip_address, vm_id: vmId, ssh_port: vm?.config?.ssh_port || null, stream_id: String(sid), project_id: activeProjectId || 'default', status: 'creating' });
      saveRentals(rentals);
      onClose();
      // Redirect to dashboard so the new VM is visible
      router.push('/');

      // Lightweight background poll: wait until access becomes available, then update rentals
      (async () => {
        const sleep = (ms: number) => new Promise(res => setTimeout(res, ms));
        const maxAttempts = 300; // ~10 minutes at 2s
        for (let i = 0; i < maxAttempts; i++) {
          try {
            // If we have a job id, optionally check it (non-fatal if it 404s on old providers)
            if (jobId) {
              try {
                const js = await vmJobStatus(provider.provider_id, jobId, adsMode);
                if (js.status === 'failed') break; // stop polling; user can retry
              } catch {}
            }
            const acc = await vmAccess(provider.provider_id, vmId, adsMode);
            if (acc && acc.ssh_port) {
              const list = loadRentals();
              const idx = list.findIndex(r => r.vm_id === vmId && r.provider_id === provider.provider_id);
              if (idx >= 0) {
                list[idx] = { ...list[idx], ssh_port: acc.ssh_port, status: 'running' };
                saveRentals(list);
              }
              break;
            }
          } catch {}
          await sleep(2000);
        }
        // If a job exists and fails, record an error state
        if (jobId) {
          try {
            const js = await vmJobStatus(provider.provider_id, jobId, adsMode);
            if (js.status === 'failed') {
              const list = loadRentals();
              const idx = list.findIndex(r => r.vm_id === vmId && r.provider_id === provider.provider_id);
              if (idx >= 0) { list[idx] = { ...list[idx], status: 'error' }; saveRentals(list); }
            }
          } catch {}
        }
      })();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally { setCreating(false); }
  };

  const goToSettings = () => {
    try { localStorage.setItem('requestor_pending_rent', provider.provider_id); } catch {}
    router.push('/settings');
  };

  return (
    <>
    <Modal open={true} onClose={onClose}>
      <div className="w-full max-w-lg">
        <div className="border-b px-5 py-4">
          <h3>Rent from <span className="font-mono text-sm">{provider.provider_id}</span></h3>
          {est && (
            displayCurrency === 'token' && est.glm_per_month != null ? (
              <div className="mt-1 text-sm text-gray-600">Estimated: ~{est.glm_per_month} GLM / mo (~{(est.glm_per_month/730).toFixed(8)} GLM/hr)</div>
            ) : (
              <div className="mt-1 text-sm text-gray-600">Estimated: ~${est.usd_per_month} / mo (~{est.usd_per_hour}/hr)</div>
            )
          )}
        </div>
        <div className="px-5 py-4">
          {!isInstalled && (
            <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              MetaMask not detected. You can browse, but to rent you must install and connect MetaMask.
            </div>
          )}
          {isInstalled && !isConnected && (
            <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 flex items-center justify-between">
              <div>Connect MetaMask to continue with renting.</div>
              <button
                className="btn btn-secondary"
                onClick={async () => { try { setConnecting(true); await connect(); } finally { setConnecting(false); } }}
                disabled={connecting}
              >
                {connecting ? (<span className="inline-flex items-center gap-2"><Spinner className="h-4 w-4" /> Connecting…</span>) : 'Connect'}
              </button>
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="my-vm"/>
            </div>
            <div>
              <label className="label">CPU</label>
              <input className="input" type="number" min={1} value={cpu} onChange={e => setCpu(Number(e.target.value))}/>
            </div>
            <div>
              <label className="label">Memory (GB)</label>
              <input className="input" type="number" min={1} value={memory} onChange={e => setMemory(Number(e.target.value))}/>
            </div>
            <div>
              <label className="label">Disk (GB)</label>
              <input className="input" type="number" min={1} value={storage} onChange={e => setStorage(Number(e.target.value))}/>
            </div>
          </div>
          <div className="mt-3 space-y-2">
            <div className="text-sm text-gray-700">SSH key</div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {/* Add new key tile */}
              <button
                className="relative flex h-32 items-center justify-center rounded-xl border-2 border-dashed border-gray-300 bg-white text-gray-600 hover:border-brand-400 hover:text-brand-700"
                onClick={() => { setNewKeyName(""); setNewKeyValue(""); setAddError(null); setShowAddKey(true); }}
              >
                <div className="text-center">
                  <div className="text-2xl">＋</div>
                  <div className="mt-1 text-sm font-medium">Add SSH Key</div>
                </div>
              </button>

              {/* Existing keys */}
              {sshKeys.map((k) => {
                const sel = selectedKeyId === k.id;
                const parts = (k.value || '').split(' ');
                const type = parts[0] || '';
                const short = parts[1] ? `${parts[1].slice(0, 12)}…${parts[1].slice(-8)}` : '';
                return (
                  <button
                    key={k.id}
                    className={
                      "relative h-32 rounded-xl border bg-white p-3 text-left shadow-sm transition-colors " +
                      (sel ? 'border-brand-500 ring-1 ring-brand-300' : 'hover:border-gray-300')
                    }
                    onClick={() => { setSelectedKeyId(k.id); setSshKey(k.value); }}
                    title={sel ? 'Selected SSH key' : 'Select this key'}
                  >
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
                          if (selectedKeyId === k.id) {
                            setSelectedKeyId(next[0]?.id || '');
                            setSshKey(next[0]?.value || '');
                          }
                          const prev = loadSettings();
                          saveSettings({
                            ssh_keys: next,
                            default_ssh_key_id: (prev.default_ssh_key_id && next.some(x => x.id === prev.default_ssh_key_id)) ? prev.default_ssh_key_id : next[0]?.id,
                            stream_payment_address: prev.stream_payment_address,
                            glm_token_address: prev.glm_token_address,
                          });
                        }}
                      >Delete</button>
                    </div>
                  </button>
                );
              })}
              {!sshKeys.length && (
                <div className="col-span-full text-sm text-gray-500">No SSH keys yet. Add one to continue.</div>
              )}
            </div>
          </div>
          <div className="mt-4">
            <div className="text-sm font-medium">Estimated costs</div>
            {(() => {
              const p = provider?.pricing || {} as any;
              if (displayCurrency === 'token') {
                const gCore = p.glm_per_core_month, gRam = p.glm_per_gb_ram_month, gSto = p.glm_per_gb_storage_month;
                if (gCore == null || gRam == null || gSto == null) return <div className="text-sm text-gray-600">Token pricing not available for this provider.</div>;
                const core = Number(gCore) * cpu;
                const memC = Number(gRam) * memory;
                const stoC = Number(gSto) * storage;
                const total = core + memC + stoC;
                const perHour = total / 730.0;
                return (
                  <div className="mt-2 rounded-lg border bg-gray-50 p-3 text-sm">
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div className="text-gray-700">
                        <div>CPU: {cpu} × {Number(gCore).toFixed(6)} GLM/mo = <span className="font-medium">{core.toFixed(6)}</span> GLM/mo</div>
                        <div>RAM: {memory} GB × {Number(gRam).toFixed(6)} GLM/GB·mo = <span className="font-medium">{memC.toFixed(6)}</span> GLM/mo</div>
                        <div>Storage: {storage} GB × {Number(gSto).toFixed(6)} GLM/GB·mo = <span className="font-medium">{stoC.toFixed(6)}</span> GLM/mo</div>
                      </div>
                      <div className="text-gray-700">
                        <div>Total: <span className="font-semibold">{total.toFixed(6)}</span> GLM per month</div>
                        <div>Hourly: <span className="font-semibold">{perHour.toFixed(8)}</span> GLM per hour</div>
                      </div>
                    </div>
                  </div>
                );
              } else {
                const usdCore = p.usd_per_core_month, usdRam = p.usd_per_gb_ram_month, usdSto = p.usd_per_gb_storage_month;
                if (usdCore == null || usdRam == null || usdSto == null) return <div className="text-sm text-gray-600">Pricing not available for this provider.</div>;
                const core = Number(usdCore) * cpu;
                const memC = Number(usdRam) * memory;
                const stoC = Number(usdSto) * storage;
                const total = core + memC + stoC;
                const perHour = total / 730.0;
                return (
                  <div className="mt-2 rounded-lg border bg-gray-50 p-3 text-sm">
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div className="text-gray-700">
                        <div>CPU: {cpu} × ${usdCore}/mo = <span className="font-medium">${core.toFixed(4)}</span>/mo</div>
                        <div>RAM: {memory} GB × ${usdRam}/GB·mo = <span className="font-medium">${memC.toFixed(4)}</span>/mo</div>
                        <div>Storage: {storage} GB × ${usdSto}/GB·mo = <span className="font-medium">${stoC.toFixed(4)}</span>/mo</div>
                      </div>
                      <div className="text-gray-700">
                        <div>Total: <span className="font-semibold">${total.toFixed(4)}</span> per month</div>
                        <div>Hourly: <span className="font-semibold">${perHour.toFixed(6)}</span> per hour</div>
                      </div>
                    </div>
                  </div>
                );
              }
            })()}
          </div>
          {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        </div>
        <div className="flex items-center justify-end gap-2 border-t px-5 py-4">
          <button className="btn btn-secondary" onClick={onClose} disabled={creating}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={create}
            disabled={!isConnected || creating || sshKeys.length === 0 || !sshKey.trim()}
          >
            {creating ? (
              <span className="inline-flex items-center gap-2"><Spinner className="h-4 w-4 text-white" /> Creating…</span>
            ) : (
              (streamId ? 'Create VM' : 'Open Stream + Create VM')
            )}
          </button>
        </div>
      </div>
    </Modal>

    {/* Add SSH Key Modal */}
    <Modal open={showAddKey} onClose={() => setShowAddKey(false)}>
      <div className="p-4">
        <h3 className="text-lg font-medium">Add SSH Key</h3>
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
              const validType = /^(ssh-(ed25519|rsa)|ecdsa-sha2-nistp(256|384|521))\s+/.test(value);
              if (!name) { setAddError('Enter a name'); return; }
              if (!value || !validType || value.split(' ').length < 2) { setAddError('Enter a valid SSH public key'); return; }
              const id = Math.random().toString(36).slice(2, 10);
              const next = [...sshKeys, { id, name, value }];
              setSshKeys(next);
              setSelectedKeyId(id);
              setSshKey(value);
              const prev = loadSettings();
              saveSettings({
                ssh_keys: next,
                default_ssh_key_id: prev.default_ssh_key_id || id,
                stream_payment_address: prev.stream_payment_address,
                glm_token_address: prev.glm_token_address,
              });
              setShowAddKey(false);
            }}
          >Add</button>
        </div>
      </div>
    </Modal>
    </>
  );
}
