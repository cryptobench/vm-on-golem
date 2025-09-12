"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { fetchProviders, computeEstimate, providerInfo } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { Spinner } from "../../components/ui/Spinner";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { ProviderRow } from "../../components/providers/ProviderRow";
import { RiArrowRightLine } from "@remixicon/react";

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
  const [selectedProviderId, setSelectedProviderId] = React.useState<string | null>(null);
  const [rentOpen, setRentOpen] = React.useState(false);

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
      <div>
        {loading && rows.length === 0 ? (
          <TableSkeleton rows={6} cols={5} />
        ) : (
          <div className="space-y-3">
            {rows.map((p) => {
              const est = cpu && memory && storage ? computeEstimate(p, cpu, memory, storage) : null;
              return (
                <ProviderRow
                  key={p.provider_id}
                  provider={p}
                  estimate={est}
                  displayCurrency={displayCurrency as any}
                  selected={selectedProviderId === p.provider_id}
                  onToggle={() => setSelectedProviderId(prev => prev === p.provider_id ? null : p.provider_id)}
                />
              );
            })}
          </div>
        )}
      </div>
      {/* Bottom checkout banner */}
      {selectedProviderId && (() => {
        const sel = rows.find(r => r.provider_id === selectedProviderId);
        if (!sel) return null;
        const est = (cpu && memory && storage) ? computeEstimate(sel, cpu, memory, storage) : null;
        const priceStr = est ? (
          displayCurrency === 'token' && est.glm_per_month != null ? `~${est.glm_per_month} GLM/mo (~${(est.glm_per_month/730).toFixed(8)} GLM/hr)` : `~$${est.usd_per_month} / mo (~${est.usd_per_hour}/hr)`
        ) : '—';
        return (
          <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-white">
            <div className="mx-auto max-w-6xl px-4 py-3">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm text-gray-700">Selected provider</div>
                  <div className="text-sm font-medium text-gray-900 truncate">{sel.provider_name || sel.provider_id}</div>
                </div>
                <div className="ml-auto flex items-center gap-6">
                  <div className="text-right">
                    <div className="text-xs text-gray-600">Total price</div>
                    <div className="text-base text-gray-900">{priceStr}</div>
                  </div>
                  <button
                    className="btn btn-primary"
                    onClick={() => setRentOpen(true)}
                    disabled={loading}
                  >
                    Rent
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}
      {/* Rent dialog from banner */}
      {rentOpen && selectedProviderId && (() => {
        const sel = rows.find(r => r.provider_id === selectedProviderId);
        if (!sel) return null;
        return (
          <RentDialog
            provider={sel}
            defaultSpec={{ cpu: cpu || 1, memory: memory || 2, storage: storage || 20 }}
            onClose={() => setRentOpen(false)}
            adsMode={ads}
          />
        );
      })()}
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
        onClick={() => setOpen(true)}
        disabled={open}
        className="relative inline-flex h-8 w-[78px] items-center justify-center rounded-md text-sm font-medium tracking-tight text-[#60646C] disabled:opacity-70"
        style={{ background: 'transparent' }}
      >
        <span className="z-[1] inline-flex h-8 w-[78px] items-center justify-center gap-2 rounded-md px-3 bg-[rgba(0,0,51,0.06)]">
          {open && <Spinner className="h-4 w-4" />}
          <span>Rent</span>
          <RiArrowRightLine className="h-4 w-4" />
        </span>
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
  const [nameTouched, setNameTouched] = React.useState<boolean>(false);

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
    if (!est) throw new Error("Cannot compute streaming rate: pricing unavailable");
    // Determine token mode and compute ratePerSecond accordingly
    const ZERO = '0x0000000000000000000000000000000000000000';
    const token = glmAddr;
    const isNative = token === ZERO;

    // Compute ratePerSecond in 18-decimals (wei-like), deposit = 1 hour by default
    let ratePerSecondWei: bigint;
    let depositWei: bigint;
    if (isNative) {
      // Native ETH mode: derive ETH rate from USD price (or eth_per_month if advertised)
      let ethPerMonth: number | null = (est as any).eth_per_month ?? null;
      if (ethPerMonth == null) {
        // Convert USD → ETH using CoinGecko
        const usdPerMonth = est.usd_per_month;
        try {
          const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd');
          const js = await r.json().catch(() => ({} as any));
          const ethUsd = js?.ethereum?.usd;
          if (!ethUsd || !Number.isFinite(ethUsd)) throw new Error('bad price');
          ethPerMonth = usdPerMonth / Number(ethUsd);
        } catch {
          throw new Error("Cannot fetch ETH/USD price to compute streaming rate");
        }
      }
      const ethPerSecond = (ethPerMonth as number) / (730.0 * 3600.0);
      // Use parseEther on a fixed-precision string to avoid float drift
      ratePerSecondWei = parseEther(ethPerSecond.toFixed(18));
      depositWei = ratePerSecondWei * BigInt(3600);
    } else {
      // ERC20 GLM mode: require GLM pricing and compute GLM/sec
      if (est.glm_per_month == null) {
        throw new Error("Provider does not advertise GLM pricing; cannot compute streaming rate for ERC20 mode");
      }
      const glmPerSecond = est.glm_per_month / (730.0 * 3600.0);
      ratePerSecondWei = parseEther(glmPerSecond.toFixed(18));
      depositWei = ratePerSecondWei * BigInt(3600);
    }

    const web3 = new BrowserProvider(ethereum);
    // Use the currently selected wallet account, not index 0
    const signer = await web3.getSigner(account ?? undefined);
    const sender = await signer.getAddress();
    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const recipient = provider.provider_id;
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
      const nm = name.trim();
      if (!nm) { setError('Enter a VM name'); return; }
      if (!sshKey) throw new Error("Provide your SSH public key in the form");
      const sid = streamId || await openStream();
      const payload = { name: nm, resources: { cpu, memory, storage }, ssh_key: sshKey, stream_id: Number(sid) };
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
    <Modal open={true} onClose={onClose} size="3xl">
      <div className="w-full">
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
              <input className="input" value={name} onChange={e => setName(e.target.value)} onBlur={() => setNameTouched(true)} placeholder="my-vm" />
              {(!name.trim() && nameTouched) && (
                <div className="mt-1 text-xs text-red-600">Name is required.</div>
              )}
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
            disabled={!isConnected || creating || sshKeys.length === 0 || !sshKey.trim() || !name.trim()}
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
