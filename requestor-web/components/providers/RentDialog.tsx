"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { BrowserProvider, Contract, parseEther } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import erc20 from "../../public/abi/ERC20.json";
import { createVm, loadSettings, saveRentals, loadRentals, saveSettings, vmAccess, vmJobStatus, type AdsConfig, type SSHKey } from "../../lib/api";
import { Modal } from "../ui/Modal";
import { useWallet } from "../../context/WalletContext";
import { useProjects } from "../../context/ProjectsContext";
import { ensureNetwork, getPaymentsChain } from "../../lib/chain";
import { Spinner } from "../ui/Spinner";
import { computeEstimate } from "../../lib/api";
import { parseHumanDuration } from "../../lib/time";
import { humanDuration } from "../../lib/streams";
import { useSettings } from "../../hooks/useSettings";
import { KeyPicker } from "../ssh/KeyPicker";

export function RentDialog({ provider, defaultSpec, onClose, adsMode }: { provider: any; defaultSpec: { cpu?: number; memory?: number; storage?: number }; onClose: () => void; adsMode: AdsConfig; }) {
  const router = useRouter();
  const { displayCurrency } = useSettings();
  const { isInstalled, isConnected, connect, account } = useWallet();
  const { activeId: activeProjectId } = useProjects();
  const [name, setName] = React.useState("");
  // Use spec provided from the Providers page; not editable here
  const [cpu] = React.useState<number>(defaultSpec.cpu || 1);
  const [memory] = React.useState<number>(defaultSpec.memory || 2);
  const [storage] = React.useState<number>(defaultSpec.storage || 20);
  const settings = loadSettings();
  const initialKeys: SSHKey[] = settings.ssh_keys || (settings.ssh_public_key ? [{ id: 'default', name: 'Default', value: settings.ssh_public_key }] : []);
  const defaultKeyId = settings.default_ssh_key_id || initialKeys[0]?.id || '';
  const [sshKey, setSshKey] = React.useState<string>(() => {
    const found = initialKeys.find(k => k.id === defaultKeyId);
    return found?.value || settings.ssh_public_key || "";
  });
  const [selectedKeyId, setSelectedKeyId] = React.useState<string>(defaultKeyId);
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [streamId, setStreamId] = React.useState<string | null>(null);
  const [usingNative, setUsingNative] = React.useState<boolean>(true);
  const [connecting, setConnecting] = React.useState<boolean>(false);
  const [nameTouched, setNameTouched] = React.useState<boolean>(false);

  const est = computeEstimate(provider, cpu, memory, storage);

  // Deposit duration selection (presets + human input like "30d", "1h30m")
  type Preset = '1w' | '2w' | '30d' | 'custom';
  const [preset, setPreset] = React.useState<Preset>('1w');
  const [customInput, setCustomInput] = React.useState<string>('');
  const durationSeconds = React.useMemo(() => {
    if (preset === '1w') return 7 * 24 * 3600;
    if (preset === '2w') return 14 * 24 * 3600;
    if (preset === '30d') return 30 * 24 * 3600;
    const secs = parseHumanDuration(customInput || '');
    return secs && secs > 0 ? secs : 0;
  }, [preset, customInput]);
  const durationHoursFloat = durationSeconds / 3600;

  const hourlyRate = React.useMemo(() => {
    if (!est) return null;
    if (displayCurrency === 'token' && (est as any).glm_per_month != null) return (est as any).glm_per_month / 730.0;
    if (est.usd_per_hour != null) return est.usd_per_hour;
    return null;
  }, [est, displayCurrency]);

  const totalForDuration = React.useMemo(() => {
    if (!hourlyRate || !durationSeconds) return null;
    return hourlyRate * (durationSeconds / 3600);
  }, [hourlyRate, durationSeconds]);

  const openStream = async (): Promise<string> => {
    setError(null);
    const { ethereum } = window as any;
    if (!ethereum) throw new Error("MetaMask not detected");
    await ensureNetwork(ethereum, getPaymentsChain());
    const providerInfoJson = await (await import("../../lib/api")).providerInfo(provider.provider_id, adsMode).catch(() => null);
    const cfg = loadSettings();
    const spAddr = (providerInfoJson?.stream_payment_address || cfg.stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();
    const glmAddr = (providerInfoJson?.glm_token_address || cfg.glm_token_address || process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || '').trim();
    if (!spAddr) throw new Error("StreamPayment address missing (set in Settings or provided by provider)");
    if (!est) throw new Error("Cannot compute streaming rate: pricing unavailable");
    const ZERO = '0x0000000000000000000000000000000000000000';
    const token = glmAddr;
    const isNative = token === ZERO;

    let ratePerSecondWei: bigint;
    let depositWei: bigint;
    if (isNative) {
      let ethPerMonth: number | null = (est as any).eth_per_month ?? null;
      if (ethPerMonth == null) {
        const usdPerMonth = est.usd_per_month;
        const { usdToToken, getPriceUSD } = await import("../../lib/prices");
        const price = getPriceUSD('ETH');
        if (price == null || !Number.isFinite(usdPerMonth)) throw new Error("ETH/USD price unavailable to compute rate");
        ethPerMonth = usdPerMonth / price;
      }
      const ethPerSecond = (ethPerMonth as number) / (30.4167 * 24 * 3600);
      ratePerSecondWei = parseEther(ethPerSecond.toFixed(18));
      const seconds = BigInt(Math.max(1, durationSeconds));
      // approximate by converting to wei/sec and multiply
      depositWei = BigInt(Math.floor(ethPerSecond * 1e18)) * seconds;
      setUsingNative(true);
    } else {
      let glmPerMonth: number | null = (est as any).glm_per_month ?? null;
      if (glmPerMonth == null) {
        const usdPerMonth = est.usd_per_month;
        const { usdToToken, getPriceUSD } = await import("../../lib/prices");
        const price = getPriceUSD('GLM');
        if (price == null || !Number.isFinite(usdPerMonth)) throw new Error("GLM/USD price unavailable to compute rate");
        glmPerMonth = usdPerMonth / price;
      }
      const glmPerSecond = (glmPerMonth as number) / (30.4167 * 24 * 3600);
      const provider = new BrowserProvider(ethereum);
      const erc = new Contract(glmAddr, (erc20 as any).abi, provider);
      const dec = Number(await erc.decimals().catch(() => 18));
      const scale = 10 ** dec;
      ratePerSecondWei = BigInt(Math.floor(glmPerSecond * scale));
      const seconds = Math.max(1, durationSeconds);
      depositWei = BigInt(Math.floor(glmPerSecond * seconds * scale));
      setUsingNative(false);
      // Ask wallet to watch GLM so prompts display a familiar asset
      try {
        await (ethereum as any).request?.({
          method: 'wallet_watchAsset',
          params: {
            type: 'ERC20',
            options: { address: glmAddr, symbol: 'GLM', decimals: dec },
          },
        });
      } catch {}
    }

    const providerE = new BrowserProvider(ethereum);
    const signer = await providerE.getSigner(account ?? undefined);
    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const sender = await signer.getAddress();
    const recipient = provider.provider_id;
    // If using ERC20, ensure allowance covers the intended deposit
    if (!isNative) {
      const erc = new Contract(token, (erc20 as any).abi, signer);
      const allowance: bigint = await erc.allowance(sender, spAddr);
      if (allowance < depositWei) {
        const txApprove = await erc.approve(spAddr, depositWei);
        await txApprove.wait();
      }
    }
    // createStream signature: (token, recipient, deposit, rate)
    const tx = await contract.createStream(
      token,
      recipient,
      depositWei,
      ratePerSecondWei,
      { value: isNative ? depositWei : 0n, gasLimit: 350000n }
    );
    const receipt = await tx.wait();
    const ev = receipt?.logs?.find?.((l: any) => String(l?.fragment?.name) === 'StreamCreated');
    const sid = ev?.args?.[0] ?? null;
    if (!sid) throw new Error('Stream id not found');
    const newId = String(sid);
    setStreamId(newId);
    return newId;
  };

  const create = async () => {
    try {
      setCreating(true); setError(null);
      if (!isConnected) {
        setConnecting(true);
        try { await connect(); } finally { setConnecting(false); }
        if (!isConnected) return;
      }
      const sid = streamId || await openStream();
      const payload: any = {
        name: name.trim() || provider.provider_name || provider.provider_id,
        resources: { cpu, memory, storage },
        ssh_key: sshKey,
        stream_id: Number(sid),
      };
      const vm = await createVm(provider.provider_id, payload, adsMode);
      const jobId = (vm as any)?.job_id || null;
      let vmId = (vm as any)?.vm_id || (vm as any)?.id || null;
      if (!vmId && jobId) {
        // Poll async job for vm id
        for (let i = 0; i < 40; i++) {
          await new Promise(res => setTimeout(res, 2000));
          const st = await vmJobStatus(provider.provider_id, jobId, adsMode).catch(() => null);
          vmId = st?.vm_id || null;
          if (vmId) break;
        }
      }
      if (!vmId) throw new Error('VM id not available');
      // Persist rental
      const entry = {
        name: payload.name,
        provider_id: provider.provider_id,
        provider_ip: provider.ip_address || null,
        platform: provider.platform || null,
        resources: provider.resources || { cpu, memory, storage },
        vm_id: vmId,
        ssh_port: null,
        stream_id: String(sid),
        project_id: activeProjectId || 'default',
        status: 'creating' as const,
        created_at: Math.floor(Date.now()/1000),
      };
      const list = loadRentals();
      saveRentals([entry as any, ...list]);
      try {
        const acc = await vmAccess(provider.provider_id, vmId, adsMode);
        if (acc?.ssh_port) {
          const cur = loadRentals();
          const idx = cur.findIndex(x => x.vm_id === vmId && x.provider_id === provider.provider_id);
          if (idx >= 0) { cur[idx] = { ...cur[idx], ssh_port: acc.ssh_port, status: 'running' }; saveRentals(cur); }
        }
      } catch {}
      onClose();
      router.push(`/vm?id=${encodeURIComponent(vmId)}`);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <Modal open onClose={onClose} size="2xl">
      <div className="px-5 py-4">
        <div className="text-lg font-semibold">Rent {provider?.provider_name || provider?.provider_id}</div>

        {/* Name */}
        <div className="mt-4">
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => { setName(e.target.value); setNameTouched(true); }} placeholder="My Server" />
          <div className="mt-1 text-xs text-gray-600">Spec: {cpu} CPU • {memory} GB RAM • {storage} GB Disk</div>
        </div>

        {/* SSH Key */}
        <div className="mt-4">
          <div className="text-sm font-medium">SSH Keys</div>
          <div className="mt-2">
            <KeyPicker layout="carousel" value={selectedKeyId} onChange={(id, key) => { setSelectedKeyId(id); setSshKey(key.value); }} />
          </div>
        </div>

        {/* Initial deposit */}
        <div className="mt-4">
          <div className="text-sm font-medium">Initial deposit</div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {(['1w','2w','30d'] as Preset[]).map((p) => (
              <button key={p} type="button" onClick={() => setPreset(p)} className={(preset === p ? 'btn btn-primary' : 'btn btn-secondary') + ' h-10 px-3'}>
                {p === '1w' ? '1 week' : p === '2w' ? '2 weeks' : '30 days'}
              </button>
            ))}
            <button type="button" onClick={() => setPreset('custom')} className={(preset === 'custom' ? 'btn btn-primary' : 'btn btn-secondary') + ' h-10 px-3'}>Custom</button>
            {preset === 'custom' && (
              <input
                className="input w-52 h-10"
                placeholder="Custom: 30d, 45m, 1h30m"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
              />
            )}
          </div>
          {/* Removed mid-section deposit summary to avoid redundancy with final summary */}
        </div>

        {/* Pricing summary for selected duration */}
        <div className="mt-4">
          <div className="text-sm font-medium">Total for selected deposit</div>
          <div className="mt-2 rounded-lg border bg-gray-50 p-3">
            {est && totalForDuration != null && durationSeconds > 0 ? (
              <div className="flex items-end justify-between">
                <div className="text-sm text-gray-600">Covers {humanDuration(durationSeconds)}</div>
                <div className="text-xl font-semibold text-gray-900">
                  {displayCurrency === 'token' && (est as any).glm_per_month != null
                    ? `${totalForDuration.toFixed(6)} GLM`
                    : `$${totalForDuration.toFixed(2)}`}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-600">Select a duration to see total deposit.</div>
            )}
          </div>
        </div>
        {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
      </div>
      <div className="flex items-center justify-end gap-2 border-t px-5 py-4">
        <button className="btn btn-secondary" onClick={onClose} disabled={creating}>Cancel</button>
        <button className="btn btn-primary disabled:opacity-60 disabled:cursor-not-allowed" onClick={create} disabled={!isConnected || creating || !sshKey.trim() || !name.trim() || !durationSeconds}>
          {creating ? (<span className="inline-flex items-center gap-2"><Spinner className="h-4 w-4 text-white" /> Creating…</span>) : (streamId ? 'Create VM' : 'Open Stream + Create VM')}
        </button>
      </div>
    </Modal>
  );
}
