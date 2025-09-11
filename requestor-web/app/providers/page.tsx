"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { fetchProviders, computeEstimate, providerInfo } from "../../lib/api";
import { useAds } from "../../context/AdsContext";

export default function ProvidersPage() {
  const [cpu, setCpu] = React.useState<number | undefined>();
  const [memory, setMemory] = React.useState<number | undefined>();
  const [storage, setStorage] = React.useState<number | undefined>();
  const [country, setCountry] = React.useState<string>("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [rows, setRows] = React.useState<any[]>([]);

  const { ads } = useAds();

  const search = async () => {
    setLoading(true); setError(null);
    try {
      const data = await fetchProviders({ cpu, memory, storage, country: country || undefined }, ads);
      setRows(data);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally { setLoading(false); }
  };

  React.useEffect(() => { search(); }, []);

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
            <div className="ml-auto">
              <button className="btn btn-primary" onClick={search} disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
            </div>
          </div>
          {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        </div>
      </div>
      <div className="card">
        <div className="card-body overflow-x-auto">
          <table className="table">
            <thead className="bg-gray-50">
              <tr>
                <th className="th">Provider</th>
                <th className="th">IP</th>
                <th className="th">Country</th>
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
                    <td className="td text-right">{p.resources?.cpu}</td>
                    <td className="td text-right">{p.resources?.memory}</td>
                    <td className="td text-right">{p.resources?.storage}</td>
                    <td className="td">
                      {(coreM == null && ramM == null && stoM == null) ? '—' : (
                        <div className="text-xs text-gray-700 space-y-0.5">
                          {coreM != null && (
                            <div>Core: ${coreM}/mo <span className="text-gray-500">({coreH}/hr)</span></div>
                          )}
                          {ramM != null && (
                            <div>RAM: ${ramM}/GB·mo <span className="text-gray-500">({ramH}/GB·hr)</span></div>
                          )}
                          {stoM != null && (
                            <div>Storage: ${stoM}/GB·mo <span className="text-gray-500">({stoH}/GB·hr)</span></div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="td">
                      {est ? (
                        <div className="text-xs sm:text-sm">
                          <div>~${est.usd_per_month} <span className="text-gray-500">({est.usd_per_hour}/hr)</span></div>
                          {est.glm_per_month != null && (<div className="text-gray-600">~{est.glm_per_month} GLM/mo</div>)}
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
      <button className="btn btn-secondary" onClick={() => setOpen(true)}>Rent</button>
      {open && <RentDialog provider={provider} defaultSpec={defaultSpec} onClose={() => setOpen(false)} adsMode={adsMode} />}
    </>
  );
}

import { BrowserProvider, Contract, parseEther } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import { createVm, loadSettings, saveRentals, loadRentals, type AdsConfig, type SSHKey } from "../../lib/api";

function RentDialog({ provider, defaultSpec, onClose, adsMode }: { provider: any; defaultSpec: { cpu?: number; memory?: number; storage?: number }; onClose: () => void; adsMode: AdsConfig; }) {
  const router = useRouter();
  const [name, setName] = React.useState("");
  const [cpu, setCpu] = React.useState<number>(defaultSpec.cpu || 1);
  const [memory, setMemory] = React.useState<number>(defaultSpec.memory || 2);
  const [storage, setStorage] = React.useState<number>(defaultSpec.storage || 20);
  const settings = loadSettings();
  const initialKeys: SSHKey[] = settings.ssh_keys || (settings.ssh_public_key ? [{ id: 'default', name: 'Default', value: settings.ssh_public_key }] : []);
  const [sshKeys] = React.useState<SSHKey[]>(initialKeys);
  const [selectedKeyId, setSelectedKeyId] = React.useState<string>(initialKeys[0]?.id || "");
  const [sshKey, setSshKey] = React.useState<string>(initialKeys[0]?.value || settings.ssh_public_key || "");
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [streamId, setStreamId] = React.useState<string | null>(null);
  const [usingNative, setUsingNative] = React.useState<boolean>(true);

  const est = computeEstimate(provider, cpu, memory, storage);

  const openStream = async () => {
    setError(null);
    const { ethereum } = window as any;
    if (!ethereum) throw new Error("MetaMask not detected");
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
    const signer = await web3.getSigner();
    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const recipient = provider.provider_id;
    const token = glmAddr;
    setUsingNative(token === '0x0000000000000000000000000000000000000000');

    // If using ERC20, in a full app we would check allowance and approve. Out of scope for minimal MVP.
    const tx = await contract.createStream(token, recipient, depositWei, ratePerSecondWei, {
      value: token === '0x0000000000000000000000000000000000000000' ? depositWei : 0n,
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
      rentals.push({ name: payload.name, provider_id: provider.provider_id, provider_ip: provider.ip_address, vm_id: vm.id || vm.vm_id || payload.name, ssh_port: vm?.config?.ssh_port || null, stream_id: String(sid) });
      saveRentals(rentals);
      onClose();
      alert(`VM created. VM ID: ${vm.id || vm.vm_id}`);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally { setCreating(false); }
  };

  const goToSettings = () => {
    try { localStorage.setItem('requestor_pending_rent', provider.provider_id); } catch {}
    router.push('/settings');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-lg ring-1 ring-gray-200">
        <div className="border-b px-5 py-4">
          <h3>Rent from <span className="font-mono text-sm">{provider.provider_id}</span></h3>
          {est && <div className="mt-1 text-sm text-gray-600">Estimated: ~${est.usd_per_month} / mo (~{est.usd_per_hour}/hr)</div>}
        </div>
        <div className="px-5 py-4">
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
            {sshKeys.length === 0 ? (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                No SSH keys found. Go to Settings to add one.
                <div className="mt-2 flex gap-2">
                  <button className="btn btn-primary" onClick={goToSettings}>Go to Settings</button>
                </div>
              </div>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <label className="label">SSH key</label>
                  <select className="input" value={selectedKeyId} onChange={(e) => {
                    const id = e.target.value;
                    setSelectedKeyId(id);
                    const k = sshKeys.find(x => x.id === id);
                    if (k) setSshKey(k.value);
                  }}>
                    {sshKeys.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
                  </select>
                </div>
                <div className="flex items-end justify-end gap-2">
                  <button className="btn btn-secondary" onClick={goToSettings}>Manage in Settings</button>
                </div>
              </div>
            )}
          </div>
          <div className="mt-4">
            <div className="text-sm font-medium">Estimated costs</div>
            {(() => {
              const p = provider?.pricing || {} as any;
              const usdCore = p.usd_per_core_month, usdRam = p.usd_per_gb_ram_month, usdSto = p.usd_per_gb_storage_month;
              if (usdCore == null || usdRam == null || usdSto == null) return <div className="text-sm text-gray-600">Pricing not available for this provider.</div>;
              const core = Number(usdCore) * cpu;
              const memC = Number(usdRam) * memory;
              const stoC = Number(usdSto) * storage;
              const total = core + memC + stoC;
              const perHour = total / 730.0;
              const glmCore = p.glm_per_core_month, glmRam = p.glm_per_gb_ram_month, glmSto = p.glm_per_gb_storage_month;
              const glm = (glmCore != null && glmRam != null && glmSto != null) ? (Number(glmCore) * cpu + Number(glmRam) * memory + Number(glmSto) * storage) : null;
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
                      {glm != null && (
                        <div>GLM: <span className="font-semibold">{glm.toFixed(8)} GLM/mo</span></div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>
          {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        </div>
        <div className="flex items-center justify-end gap-2 border-t px-5 py-4">
          <button className="btn btn-secondary" onClick={onClose} disabled={creating}>Cancel</button>
          <button className="btn btn-primary" onClick={create} disabled={creating || sshKeys.length === 0 || !sshKey.trim()}>{creating ? 'Creating…' : (streamId ? 'Create VM' : 'Open Stream + Create VM')}</button>
        </div>
      </div>
    </div>
  );
}
