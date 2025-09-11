"use client";
import React from "react";
import { useParams, useRouter } from "next/navigation";
import { loadRentals, vmAccess, vmStop, vmDestroy, loadSettings } from "../../../lib/api";
import { useAds } from "../../../context/AdsContext";
import { useToast } from "../../../components/ui/Toast";
import { Spinner } from "../../../components/ui/Spinner";
import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../../../public/abi/StreamPayment.json";
import { ensureNetwork, getPaymentsChain } from "../../../lib/chain";
import { useWallet } from "../../../context/WalletContext";

type ChainStream = {
  token: string; sender: string; recipient: string;
  startTime: bigint; stopTime: bigint; ratePerSecond: bigint;
  deposit: bigint; withdrawn: bigint; halted: boolean;
};

function TabBar({ tab, setTab }: { tab: string; setTab: (t: string) => void }) {
  const items = [
    { k: "overview", label: "Overview" },
    { k: "stream", label: "Stream" },
    { k: "topup", label: "Top Up" },
    { k: "actions", label: "Actions" },
  ];
  return (
    <div className="border-b">
      <div className="-mb-px flex gap-2">
        {items.map(i => (
          <button key={i.k}
            className={"px-3 py-2 text-sm border-b-2 " + (tab === i.k ? "border-brand-600 text-brand-700" : "border-transparent text-gray-600 hover:text-gray-800")}
            onClick={() => setTab(i.k)}>
            {i.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function VmDetailsPage() {
  const params = useParams<{ vmId: string }>();
  const router = useRouter();
  const { ads } = useAds();
  const { show } = useToast();
  const [tab, setTab] = React.useState("overview");
  const [busy, setBusy] = React.useState(false);
  const [access, setAccess] = React.useState<{ ssh_port?: number } | null>(null);
  const [stream, setStream] = React.useState<{ chain: ChainStream; remaining: bigint } | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const { account } = useWallet();

  const rentals = loadRentals();
  const vm = rentals.find(r => r.vm_id === params.vmId);

  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();

  React.useEffect(() => {
    if (!vm) return;
    (async () => {
      try {
        setErr(null);
        const acc = await vmAccess(vm.provider_id, vm.vm_id, ads).catch(() => ({}));
        setAccess(acc);
      } catch {}
      try {
        if (vm.stream_id && spAddr) {
          const { ethereum } = window as any;
          const provider = new BrowserProvider(ethereum);
          const contract = new Contract(spAddr, (streamPayment as any).abi, provider);
          const res = (await contract.streams(BigInt(vm.stream_id))) as ChainStream;
          const now = BigInt((await provider.getBlock("latest"))!.timestamp!);
          const remaining = res.stopTime > now ? (res.stopTime - now) : 0n;
          setStream({ chain: res, remaining });
        } else {
          setStream(null);
        }
      } catch (e: any) {
        setStream(null);
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.vmId]);

  if (!vm) {
    return (
      <div className="space-y-4">
        <div className="text-red-600">VM not found in your rentals.</div>
        <button className="btn btn-secondary" onClick={() => router.push('/rentals')}>Back to Servers</button>
      </div>
    );
  }

  const sshHost = vm.provider_ip || 'PROVIDER_IP';
  const sshPort = access?.ssh_port || vm.ssh_port || null;
  const keyPath = "~/.golem/requestor/ssh/golem_id_rsa";
  const sshCmd = sshPort ? `ssh -i ${keyPath} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p ${sshPort} ubuntu@${sshHost}` : null;

  const copySSH = async () => {
    try {
      if (!sshCmd) { show("SSH port unavailable"); return; }
      await navigator.clipboard.writeText(sshCmd);
      show("SSH command copied");
    } catch { show("Could not copy SSH command"); }
  };

  const stopVm = async () => {
    try { setBusy(true); await vmStop(vm.provider_id, vm.vm_id, ads); show("Stop requested"); }
    catch (e) { show("Stop failed"); }
    finally { setBusy(false); }
  };
  const destroyVm = async () => {
    if (!confirm('Destroy VM?')) return;
    try { setBusy(true); await vmDestroy(vm.provider_id, vm.vm_id, ads); show("Destroy requested"); router.push('/rentals'); }
    catch (e) { show("Destroy failed"); setBusy(false); }
  };

  const topUp = async (seconds: number) => {
    if (!vm.stream_id || !stream || !spAddr) return;
    try {
      setBusy(true);
      const { ethereum } = window as any;
      await ensureNetwork(ethereum, getPaymentsChain());
      const provider = new BrowserProvider(ethereum);
      const signer = await provider.getSigner(account ?? undefined);
      const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
      const addWei = stream.chain.ratePerSecond * BigInt(seconds);
      const tx = await contract.topUp(BigInt(vm.stream_id), addWei, {
        value: stream.chain.token === '0x0000000000000000000000000000000000000000' ? addWei : 0n,
        gasLimit: 150000n,
      });
      await tx.wait();
      show("Top-up sent");
      // refresh stream
      const res = (await contract.streams(BigInt(vm.stream_id))) as ChainStream;
      const now = BigInt((await provider.getBlock("latest"))!.timestamp!);
      const remaining = res.stopTime > now ? (res.stopTime - now) : 0n;
      setStream({ chain: res, remaining });
      setTab("stream");
    } catch (e) {
      show("Top-up failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="truncate">VM: <span className="font-mono text-sm">{vm.vm_id}</span></h2>
        <div className="text-sm text-gray-600">Provider: <span className="font-mono">{vm.provider_id}</span></div>
      </div>
      <TabBar tab={tab} setTab={setTab} />

      {tab === 'overview' && (
        <div className="card">
          <div className="card-body">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="text-sm text-gray-700">
                <div><span className="text-gray-500">Name:</span> {vm.name}</div>
                <div><span className="text-gray-500">VM ID:</span> <span className="font-mono">{vm.vm_id}</span></div>
                <div><span className="text-gray-500">Provider:</span> <span className="font-mono">{vm.provider_id}</span></div>
              </div>
              <div className="text-sm text-gray-700">
                <div><span className="text-gray-500">SSH Host:</span> {sshHost}</div>
                <div><span className="text-gray-500">SSH Port:</span> {sshPort ?? '—'}</div>
                <div className="truncate"><span className="text-gray-500">SSH Command:</span> {sshCmd ? <span className="font-mono text-xs">{sshCmd}</span> : '—'}</div>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button className="btn btn-secondary" onClick={copySSH} disabled={!sshCmd}>Copy SSH</button>
              <button className="btn btn-secondary" onClick={() => setTab('actions')}>Actions</button>
            </div>
          </div>
        </div>
      )}

      {tab === 'stream' && (
        <div className="card">
          <div className="card-body">
            {!vm.stream_id ? (
              <div className="text-sm text-gray-600">No stream mapped for this VM.</div>
            ) : !stream ? (
              <div className="text-sm text-gray-600">Loading stream…</div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-sm text-gray-700">
                <div>
                  <div><span className="text-gray-500">Recipient:</span> {stream.chain.recipient}</div>
                  <div><span className="text-gray-500">Token:</span> {stream.chain.token}</div>
                  <div><span className="text-gray-500">Rate/s (wei):</span> {stream.chain.ratePerSecond.toString()}</div>
                </div>
                <div>
                  <div><span className="text-gray-500">Deposit:</span> {stream.chain.deposit.toString()}</div>
                  <div><span className="text-gray-500">Withdrawn:</span> {stream.chain.withdrawn.toString()}</div>
                  <div><span className="text-gray-500">Remaining:</span> {stream.remaining.toString()}s</div>
                  <div><span className="text-gray-500">Status:</span> {stream.chain.halted ? 'halted' : 'active'}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'topup' && (
        <div className="card">
          <div className="card-body space-y-3">
            {!vm.stream_id ? (
              <div className="text-sm text-gray-600">No stream mapped for this VM.</div>
            ) : (
              <>
                <div className="text-sm text-gray-700">Choose top up amount</div>
                <div className="flex flex-wrap gap-2">
                  <button className="btn btn-secondary" onClick={() => topUp(1800)} disabled={busy}>+30 min</button>
                  <button className="btn btn-secondary" onClick={() => topUp(3600)} disabled={busy}>{busy ? <><Spinner className="h-4 w-4" /> +1 h</> : '+1 h'}</button>
                  <button className="btn btn-secondary" onClick={() => topUp(7200)} disabled={busy}>+2 h</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'actions' && (
        <div className="card">
          <div className="card-body flex flex-wrap items-center gap-2">
            <button className="btn btn-secondary" onClick={stopVm} disabled={busy}>{busy ? <><Spinner className="h-4 w-4" /> Stop</> : 'Stop'}</button>
            <button className="btn btn-danger" onClick={destroyVm} disabled={busy}>Destroy</button>
          </div>
        </div>
      )}
    </div>
  );
}
