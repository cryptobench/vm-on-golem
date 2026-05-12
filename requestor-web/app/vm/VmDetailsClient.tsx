"use client";
import React from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  loadRentals,
  saveRentals,
  createSnapshot,
  deleteSnapshot,
  listSnapshots,
  restoreSnapshot,
  vmDestroy,
  vmRestart,
  vmResume,
  vmResize,
  vmStart,
  vmStop,
  vmSuspend,
  loadSettings,
  type Rental,
} from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../../components/ui/Toast";
import { useStreamActions } from "../../hooks/useStreamActions";
import { useWallet } from "../../context/WalletContext";
import { getPaymentNetworkErrorMessage } from "../../lib/chain";
import { buildSshCommand, copyText } from "../../lib/ssh";
import {
  humanDuration,
  type ChainStream,
  fetchStreamWithMeta,
} from "../../lib/streams";
import { getPriceUSD, onPricesUpdated } from "../../lib/prices";
import {
  useProviderInfo,
  useVmAccess,
  useVmCreateJobStatus,
  useVmStatusSafe,
  useVmStatus,
  useVmMetricsLatest,
  useVmMetricsHistory,
} from "../../hooks/useApiSWR";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { VmMetricsCharts } from "../../components/vm/VmMetricsCharts";
import {
  VmDetailsHeader,
  type VmAction,
} from "../../components/vm/details/VmDetailsHeader";
import { VmOverviewPanel } from "../../components/vm/details/VmOverviewPanel";
import { VmMetricsSummary } from "../../components/vm/details/VmMetricsSummary";
import { VmSnapshotsPanel } from "../../components/vm/details/VmSnapshotsPanel";
import { VmResizePanel } from "../../components/vm/details/VmResizePanel";
import { VmPaymentStreamPanel } from "../../components/vm/details/VmPaymentStreamPanel";
import { VmDetailsSkeleton } from "../../components/vm/details/VmDetailsSkeleton";
import { VmStopNotice } from "../../components/vm/details/VmStopNotice";
import { deriveVmLifecycle } from "../../lib/vmLifecycle";

export default function VmDetailsClient() {
  const search = useSearchParams();
  const router = useRouter();
  const { ads } = useAds();
  const { show } = useToast();
  const [mounted, setMounted] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [access, setAccess] = React.useState<{
    ssh_host?: string;
    ssh_port?: number | null;
    ssh_user?: string | null;
  } | null>(null);
  const [stream, setStream] = React.useState<{
    chain: ChainStream;
    remaining: bigint;
  } | null>(null);
  const [remaining, setRemaining] = React.useState<number>(0);
  const [err, setErr] = React.useState<string | null>(null);
  const { paymentReady, paymentMessage } = useWallet();
  const [provider, setProvider] = React.useState<{
    country?: string | null;
    platform?: string | null;
    ip_address?: string | null;
  } | null>(null);
  const [tokenSymbol, setTokenSymbol] = React.useState<string>("");
  const [tokenDecimals, setTokenDecimals] = React.useState<number>(18);
  const [usdPrice, setUsdPrice] = React.useState<number | null>(null);
  const [displayCurrency, setDisplayCurrency] = React.useState<
    "fiat" | "token"
  >(loadSettings().display_currency === "token" ? "token" : "fiat");
  const [snapshots, setSnapshots] = React.useState<
    Array<{ name: string; comment?: string | null; created_at?: string | null }>
  >([]);
  const [snapshotBusy, setSnapshotBusy] = React.useState<string | null>(null);
  const [resizeCpu, setResizeCpu] = React.useState<number>(1);
  const [resizeMemory, setResizeMemory] = React.useState<number>(1);
  const [resizeStorage, setResizeStorage] = React.useState<number>(10);
  const [resizeInitializedKey, setResizeInitializedKey] = React.useState<
    string | null
  >(null);
  const [metricsRange, setMetricsRange] = React.useState<
    "1h" | "6h" | "24h" | "7d"
  >("1h");

  const vmId = search.get("id") || "";
  const [vm, setVm] = React.useState<
    ReturnType<typeof loadRentals>[number] | null
  >(null);

  const spAddr = (
    loadSettings().stream_payment_address ||
    process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS ||
    ""
  ).trim();

  // Destroy confirmation state (must be before any early returns)
  const [confirmDestroyOpen, setConfirmDestroyOpen] = React.useState(false);
  const openDestroy = () => setConfirmDestroyOpen(true);
  const closeDestroy = () => setConfirmDestroyOpen(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);
  // React to Settings changes (currency toggle) live
  React.useEffect(() => {
    const onSettings = (e: any) => {
      try {
        setDisplayCurrency(
          e?.detail?.display_currency === "token" ? "token" : "fiat",
        );
      } catch {}
    };
    const onStorage = () =>
      setDisplayCurrency(
        loadSettings().display_currency === "token" ? "token" : "fiat",
      );
    window.addEventListener("requestor_settings_changed", onSettings as any);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(
        "requestor_settings_changed",
        onSettings as any,
      );
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  // Resolve VM from local storage after mount to avoid SSR hydration mismatches
  React.useEffect(() => {
    try {
      const list = loadRentals();
      const rec = list.find((r) => r.vm_id === vmId) || null;
      setVm(rec as any);
    } catch {
      setVm(null);
    }
  }, [vmId]);

  // SWR-backed provider info, access, and VM existence polling
  const { data: swrProvider } = useProviderInfo(vm?.provider_id, {
    refreshInterval: 30000,
  });
  const { data: swrAccess } = useVmAccess(vm?.provider_id, vm?.vm_id, {
    refreshInterval: 2000,
  });
  const { data: swrJob } = useVmCreateJobStatus(
    vm?.provider_id,
    vm?.creation_job_id,
    { refreshInterval: 2000 },
  );
  const { data: swrStatus } = useVmStatusSafe(vm?.provider_id, vm?.vm_id, {
    refreshInterval: 2000,
  });
  const { data: swrVm } = useVmStatus(vm?.provider_id, vm?.vm_id, {
    refreshInterval: 2000,
  });
  const { data: swrMetrics, isLoading: metricsLoading } = useVmMetricsLatest(
    vm?.provider_id,
    vm?.vm_id,
    { refreshInterval: 10000 },
  );
  const { data: swrMetricsHistory, isLoading: metricsHistoryLoading } =
    useVmMetricsHistory(vm?.provider_id, vm?.vm_id, metricsRange, {
      refreshInterval: 30000,
    });

  React.useEffect(() => {
    if (swrProvider)
      setProvider({
        country: (swrProvider as any).country,
        platform: (swrProvider as any).platform,
        ip_address: (swrProvider as any).ip_address,
      });
  }, [swrProvider]);

  React.useEffect(() => {
    if (swrAccess) setAccess(swrAccess as any);
  }, [swrAccess]);

  // Reconcile local VM record with provider's authoritative status (full status endpoint)
  React.useEffect(() => {
    if (!vm || !swrVm) return;
    const next = mergeVmStatus(vm, swrVm);
    if (next) {
      try {
        const list = loadRentals();
        const idx = list.findIndex(
          (x) => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id,
        );
        if (idx >= 0) {
          const out = [...list];
          out[idx] = next as any;
          saveRentals(out);
        }
        setVm(next);
      } catch {
        setVm(next);
      }
    }
  }, [swrVm, vm?.vm_id, vm?.provider_id]);

  // Safe status endpoint: handle 404 termination and enrich provider resources.
  // Also reconcile status when full endpoint data is unavailable.
  React.useEffect(() => {
    if (!vm || !swrStatus) return;
    const safe = swrStatus as any;
    if (!safe.exists && safe.code === 404) {
      setAccess(null);
      setProvider((prev) => (prev ? { ...prev } : prev));
      const createdAt = (vm as any).created_at
        ? Number((vm as any).created_at)
        : 0;
      const ageSec = createdAt
        ? Math.floor(Date.now() / 1000) - createdAt
        : Infinity;
      const isCreating = (vm.status || "").toLowerCase() === "creating";
      const withinGrace = isCreating && ageSec < 180; // 3 minutes
      if (!withinGrace) {
        try {
          const list = loadRentals();
          const idx = list.findIndex(
            (x) => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id,
          );
          if (idx >= 0) {
            const next: Rental = {
              ...list[idx],
              status: "terminated",
              ssh_port: null,
              ended_at: Math.floor(Date.now() / 1000),
            };
            const out = [...list];
            out[idx] = next;
            saveRentals(out);
            setVm(next);
          }
        } catch {}
      }
    } else {
      const s = (safe as any).data || {};
      // Update provider resources if present
      if (s?.resources) {
        setProvider(
          (prev) => ({ ...(prev || {}), resources: s.resources }) as any,
        );
      }
      // If we have status in the safe payload and it differs locally, reconcile.
      if (s && s.status) {
        const next = mergeVmStatus(vm, s);
        if (next) {
          try {
            const list = loadRentals();
            const idx = list.findIndex(
              (x) => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id,
            );
            if (idx >= 0) {
              const out = [...list];
              out[idx] = next as any;
              saveRentals(out);
            }
            setVm(next);
          } catch {
            setVm(next);
          }
        }
      }
    }
  }, [swrStatus, vm?.vm_id, vm?.provider_id]);

  // Stream details via lightweight polling + local 1s countdown
  React.useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!vm?.stream_id || !spAddr) {
        if (!cancelled) setStream(null);
        return;
      }
      try {
        setErr(null);
        const res = await fetchStreamWithMeta(spAddr, BigInt(vm.stream_id));
        if (cancelled) return;
        setStream({
          chain: res.chain as any,
          remaining: BigInt(res.remaining),
        });
        setRemaining(Number(res.remaining));
        setTokenSymbol(String(res.tokenSymbol || "GLM"));
        setTokenDecimals(Number(res.tokenDecimals || 18));
        setUsdPrice(res.usdPrice ?? null);
      } catch (e) {
        if (!cancelled) {
          setStream(null);
          setErr(getPaymentNetworkErrorMessage(e));
        }
      }
    };
    run();
    const iv = setInterval(run, 15000);
    return () => {
      cancelled = true;
      clearInterval(iv);
    };
  }, [vm?.stream_id, spAddr]);

  // Keep USD price in sync with global cache
  React.useEffect(() => {
    const addr = (stream?.chain?.token || "").toLowerCase();
    if (!addr && !tokenSymbol) return;
    const glm = (
      loadSettings().glm_token_address ||
      process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS ||
      ""
    ).toLowerCase();
    const symUpper = (
      typeof tokenSymbol === "string" ? tokenSymbol : ""
    ).toUpperCase();
    const isEthLike =
      addr === "0x0000000000000000000000000000000000000000" ||
      symUpper === "ETH" ||
      symUpper === "WETH";
    const isGlmLike = (glm && addr === glm) || symUpper === "GLM";
    const pick = () =>
      isEthLike ? getPriceUSD("ETH") : isGlmLike ? getPriceUSD("GLM") : null;
    setUsdPrice(pick());
    const off = onPricesUpdated(() => setUsdPrice(pick()));
    return () => {
      try {
        off && off();
      } catch {}
    };
  }, [stream?.chain?.token, tokenSymbol]);

  // Countdown ticker for remaining seconds
  React.useEffect(() => {
    if (!stream) return;
    let t: any;
    t = setInterval(() => {
      setRemaining((x) => (x > 0 ? x - 1 : 0));
    }, 1000);
    return () => clearInterval(t);
  }, [stream?.chain?.stopTime]);

  React.useEffect(() => {
    if (!vm) return;
    listSnapshots(vm.provider_id, vm.vm_id, ads)
      .then((rows) => setSnapshots(Array.isArray(rows) ? rows : []))
      .catch(() => setSnapshots([]));
  }, [vm?.provider_id, vm?.vm_id, vm?.status, ads]);

  React.useEffect(() => {
    const resources = getEffectiveResources(swrVm, vm);
    if (!vm || !resources) return;
    const key = `${vm.provider_id}:${vm.vm_id}:${resources.cpu}:${resources.memory}:${resources.storage}`;
    if (resizeInitializedKey === key) return;
    setResizeCpu(resources.cpu);
    setResizeMemory(resources.memory);
    setResizeStorage(resources.storage);
    setResizeInitializedKey(key);
  }, [swrVm, vm, resizeInitializedKey]);

  if (!mounted) {
    return <VmDetailsSkeleton />;
  }

  if (!vm) {
    return (
      <div className="space-y-4">
        <div className="text-red-600">VM not found in your rentals.</div>
        <button
          className="btn btn-secondary"
          onClick={() => router.push("/rentals")}
        >
          Back to VMs
        </button>
      </div>
    );
  }

  const sshHost = access?.ssh_host || null;
  const sshPort = access?.ssh_port != null ? Number(access.ssh_port) : null;
  const sshUser = access?.ssh_user || null;
  const sshCmd =
    sshHost && sshPort && sshUser
      ? buildSshCommand(sshHost, Number(sshPort), sshUser)
      : null;
  const rawProviderLifecycle =
    (swrVm as any) || (swrStatus as any)?.data || null;
  const accessLifecycle = (swrAccess as any)?.status
    ? (swrAccess as any)
    : null;
  const jobLifecycle = (swrJob as any)?.status ? (swrJob as any) : null;
  const jobActive =
    jobLifecycle &&
    !["running", "failed", "error"].includes(
      String(jobLifecycle.status || "").toLowerCase(),
    );
  const providerStatus = String(
    rawProviderLifecycle?.status || "",
  ).toLowerCase();
  const lifecycleSource = jobActive
    ? jobLifecycle
    : providerStatus === "unknown" && accessLifecycle
      ? accessLifecycle
      : rawProviderLifecycle || jobLifecycle || accessLifecycle || {};
  const lifecycle = deriveVmLifecycle(lifecycleSource, {
    status: vm.status || "creating",
    lifecycle_stage:
      vm.lifecycle_stage ||
      (vm.status === "creating" ? "provisioning" : vm.status),
    status_message:
      vm.status_message ||
      (vm.status === "creating" ? "VM is being provisioned" : undefined),
    progress: vm.progress ?? (vm.status === "creating" ? 15 : undefined),
    transitioning: vm.transitioning,
    next_poll_seconds: vm.next_poll_seconds,
  });
  const effectiveStatus = lifecycle.status;
  const isStopped = effectiveStatus === "stopped";
  const isSuspended =
    effectiveStatus === "suspended" || effectiveStatus === "suspending";
  const isRunning = effectiveStatus === "running";
  const isTerminated =
    effectiveStatus === "terminated" || effectiveStatus === "deleted";
  const isTransitioning = lifecycle.transitioning;

  const copyValue = async (value: string) => {
    try {
      const copied = await copyText(value);
      show(copied ? "Copied" : "Could not copy");
    } catch {
      show("Could not copy");
    }
  };

  const copySSH = async () => {
    try {
      if (vm?.status === "terminated") {
        show("VM has been terminated by provider");
        return;
      }
      if (!sshCmd) {
        show("SSH port unavailable");
        return;
      }
      const copied = await copyText(sshCmd);
      show(copied ? "SSH command copied" : "Could not copy SSH command");
    } catch {
      show("Could not copy SSH command");
    }
  };

  const stopVm = async () => {
    if (vm.status === "terminated") {
      show("VM already terminated");
      return;
    }
    try {
      setBusy(true);
      updateVmStatus("stopping");
      await vmStop(vm.provider_id, vm.vm_id, ads);
      show("Stop requested");
    } catch (e) {
      show("Stop failed");
    } finally {
      setBusy(false);
    }
  };
  const startVm = async () => {
    if (vm.status === "terminated") {
      show("VM already terminated");
      return;
    }
    try {
      setBusy(true);
      updateVmStatus("starting");
      await vmStart(vm.provider_id, vm.vm_id, ads);
      show("Start requested");
    } catch (e) {
      show("Start failed");
    } finally {
      setBusy(false);
    }
  };
  const restartVm = async () => {
    if (vm.status === "terminated") {
      show("VM already terminated");
      return;
    }
    try {
      setBusy(true);
      updateVmStatus("restarting");
      await vmRestart(vm.provider_id, vm.vm_id, ads);
      show("Restart requested");
    } catch (e) {
      show("Restart failed");
    } finally {
      setBusy(false);
    }
  };
  const suspendVm = async () => {
    if (vm.status === "terminated") {
      show("VM already terminated");
      return;
    }
    try {
      setBusy(true);
      updateVmStatus("suspending");
      await vmSuspend(vm.provider_id, vm.vm_id, ads);
      show("Suspend requested");
    } catch (e) {
      show("Suspend failed");
    } finally {
      setBusy(false);
    }
  };
  const resumeVm = async () => {
    if (vm.status === "terminated") {
      show("VM already terminated");
      return;
    }
    try {
      setBusy(true);
      updateVmStatus("starting");
      await vmResume(vm.provider_id, vm.vm_id, ads);
      show("Resume requested");
    } catch (e) {
      show("Resume failed");
    } finally {
      setBusy(false);
    }
  };
  const updateVmStatus = (status: string) => {
    const next = { ...vm, status } as Rental;
    try {
      const list = loadRentals();
      const idx = list.findIndex(
        (x) => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id,
      );
      if (idx >= 0) {
        const out = [...list];
        out[idx] = next;
        saveRentals(out);
      }
    } catch {}
    setVm(next as any);
  };
  const refreshSnapshots = async () => {
    const rows = await listSnapshots(vm.provider_id, vm.vm_id, ads);
    setSnapshots(Array.isArray(rows) ? rows : []);
  };
  const createVmSnapshot = async () => {
    try {
      setSnapshotBusy("create");
      await createSnapshot(vm.provider_id, vm.vm_id, {}, ads);
      await refreshSnapshots();
      show("Snapshot created");
    } catch {
      show("Snapshot failed. Stop the VM first and try again.");
    } finally {
      setSnapshotBusy(null);
    }
  };
  const restoreVmSnapshot = async (name: string) => {
    try {
      setSnapshotBusy(`restore:${name}`);
      await restoreSnapshot(vm.provider_id, vm.vm_id, name, ads);
      await refreshSnapshots();
      show("Snapshot restored");
    } catch {
      show("Restore failed. Stop the VM first and try again.");
    } finally {
      setSnapshotBusy(null);
    }
  };
  const deleteVmSnapshot = async (name: string) => {
    try {
      setSnapshotBusy(`delete:${name}`);
      await deleteSnapshot(vm.provider_id, vm.vm_id, name, ads);
      await refreshSnapshots();
      show("Snapshot deleted");
    } catch {
      show("Delete snapshot failed");
    } finally {
      setSnapshotBusy(null);
    }
  };
  const resizeVm = async () => {
    try {
      setBusy(true);
      await vmResize(
        vm.provider_id,
        vm.vm_id,
        { cpu: resizeCpu, memory: resizeMemory, storage: resizeStorage },
        ads,
      );
      const next = {
        ...vm,
        resources: {
          cpu: resizeCpu,
          memory: resizeMemory,
          storage: resizeStorage,
        },
      } as Rental;
      const list = loadRentals();
      const idx = list.findIndex(
        (x) => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id,
      );
      if (idx >= 0) {
        const out = [...list];
        out[idx] = next;
        saveRentals(out);
      }
      setVm(next as any);
      show("Resize applied");
    } catch {
      show("Resize failed. Stop the VM first and check capacity.");
    } finally {
      setBusy(false);
    }
  };
  const confirmDestroy = async () => {
    try {
      setBusy(true);
      try {
        await vmDestroy(vm.provider_id, vm.vm_id, ads);
      } catch (e) {
        // Treat 404 as already deleted on provider; proceed to remove locally
      }
      // Remove locally
      try {
        const list = loadRentals();
        const left = list.filter(
          (x) => !(x.vm_id === vm.vm_id && x.provider_id === vm.provider_id),
        );
        saveRentals(left);
      } catch {}
      show("Terminated");
      closeDestroy();
      router.push("/rentals");
    } catch (e) {
      show("Terminate failed");
    } finally {
      setBusy(false);
    }
  };

  const { topUp: topUpAction } = useStreamActions(spAddr);
  const topUp = async (seconds: number) => {
    if (!vm.stream_id || !stream || !spAddr) return;
    try {
      setBusy(true);
      await topUpAction(
        BigInt(vm.stream_id),
        stream.chain.token,
        stream.chain.ratePerSecond,
        seconds,
      );
      show("Top-up sent");
      const res = await fetchStreamWithMeta(spAddr, BigInt(vm.stream_id));
      setStream({ chain: res.chain as any, remaining: BigInt(res.remaining) });
      setRemaining(Number(res.remaining));
    } catch (e) {
      show(getPaymentNetworkErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // Pick VM spec from provider status if exposed, else from saved rental (no hook to avoid order issues)
  const effectiveResources = getEffectiveResources(swrVm, vm);

  const guestMetrics = (() => {
    const byVm = (swrMetrics as any)?.vms || {};
    return byVm[vm.vm_id]?.guest_agent || null;
  })();
  const metricsUpdatedAt = guestMetrics?.agent_heartbeat?.timestamp
    ? new Date(guestMetrics.agent_heartbeat.timestamp).toLocaleTimeString()
    : null;
  const lastUpdated = metricsUpdatedAt || "just now";
  const explorerUrl = buildExplorerUrl(
    loadSettings().evm_explorer_url ||
      process.env.NEXT_PUBLIC_EVM_EXPLORER_URL ||
      null,
    spAddr,
  );
  const actionItems: VmAction[] = [
    {
      label: isSuspended ? "Resume VM" : "Start VM",
      onClick: isSuspended ? resumeVm : startVm,
      disabled:
        busy || isTransitioning || isTerminated || (!isStopped && !isSuspended),
    },
    {
      label: "Stop VM",
      onClick: stopVm,
      disabled: busy || isTransitioning || isTerminated || !isRunning,
    },
    {
      label: "Restart VM",
      onClick: restartVm,
      disabled: busy || isTransitioning || isTerminated || !isRunning,
    },
    {
      label: "Suspend VM",
      onClick: suspendVm,
      disabled: busy || isTransitioning || isTerminated || !isRunning,
    },
    {
      label: "Terminate VM",
      onClick: openDestroy,
      disabled: busy,
      danger: true,
    },
  ];

  return (
    <div className="space-y-5">
      <VmDetailsHeader
        name={vm.name}
        status={lifecycle.status}
        statusMessage={lifecycle.message}
        lifecycleStage={lifecycle.stage}
        progress={lifecycle.progress}
        transitioning={lifecycle.transitioning}
        lastUpdated={lastUpdated}
        copySshDisabled={!sshCmd || isTerminated}
        busy={busy}
        actions={actionItems}
        onCopySsh={copySSH}
      />

      <VmOverviewPanel
        providerId={vm.provider_id}
        vmId={vm.vm_id}
        country={provider?.country}
        platform={provider?.platform || vm.platform}
        providerIp={provider?.ip_address || vm.provider_ip}
        sshPort={sshPort}
        resources={effectiveResources}
        onCopy={copyValue}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_23rem]">
        <div className="space-y-5">
          <VmMetricsSummary
            guestMetrics={guestMetrics}
            history={swrMetricsHistory}
            loading={metricsLoading}
          />
          <VmMetricsCharts
            history={swrMetricsHistory}
            loading={metricsHistoryLoading}
            range={metricsRange}
            onRangeChange={setMetricsRange}
          />
          <VmSnapshotsPanel
            snapshots={snapshots}
            stopped={isStopped}
            busy={snapshotBusy}
            onCreate={createVmSnapshot}
            onRestore={restoreVmSnapshot}
            onDelete={deleteVmSnapshot}
            onRefresh={refreshSnapshots}
          />
        </div>

        <aside className="space-y-5">
          {vm.stream_id && stream ? (
            <VmPaymentStreamPanel
              streamId={vm.stream_id}
              stream={stream.chain}
              remaining={remaining}
              tokenSymbol={tokenSymbol}
              tokenDecimals={tokenDecimals}
              usdPrice={usdPrice}
              displayCurrency={displayCurrency}
              busy={busy}
              actionsDisabled={!paymentReady}
              actionsDisabledReason={!paymentReady ? paymentMessage : null}
              explorerUrl={explorerUrl}
              onCopy={copyValue}
              onTopUp={topUp}
            />
          ) : (
            <div className="card vm-page-enter">
              <div className="card-body">
                <h3 className="text-base font-semibold text-text-primary">
                  Payment stream
                </h3>
                <div className="mt-3 text-sm text-text-secondary">
                  {err || "No stream mapped for this VM."}
                </div>
              </div>
            </div>
          )}
          <VmResizePanel
            cpu={resizeCpu}
            memory={resizeMemory}
            storage={resizeStorage}
            minStorage={effectiveResources?.storage || 10}
            stopped={isStopped}
            busy={busy}
            onCpuChange={setResizeCpu}
            onMemoryChange={setResizeMemory}
            onStorageChange={setResizeStorage}
            onResize={resizeVm}
          />
        </aside>
      </div>

      <VmStopNotice running={isRunning} busy={busy} onStop={stopVm} />
      {/* Terminate confirmation modal */}
      <ConfirmDialog
        open={confirmDestroyOpen}
        onCancel={closeDestroy}
        onConfirm={confirmDestroy}
        title="Terminate VM"
        description="Are you sure you want to permanently terminate this VM? This action cannot be undone."
        confirmLabel="Terminate"
        danger
        busy={busy}
      />
    </div>
  );
}

function getEffectiveResources(swrVm: unknown, vm: Rental | null) {
  const status = (swrVm as any) || {};
  const source =
    status?.resources && typeof status.resources === "object"
      ? status.resources
      : status;
  const cpu = Number(source?.cpu);
  const memory = Number(source?.memory);
  const storage = Number(source?.storage);

  if (
    [cpu, memory, storage].every((value) => Number.isFinite(value) && value > 0)
  ) {
    return { cpu, memory, storage };
  }

  return vm?.resources || null;
}

function mergeVmStatus(vm: Rental, payload: unknown): Rental | null {
  const data = (payload as any) || {};
  const status = String(data.status || "").toLowerCase();
  if (!status || status === "unknown") return null;

  const terminal = status === "terminated" || status === "deleted";
  const sshPort =
    terminal || data.ssh_port == null ? null : Number(data.ssh_port);
  const providerIp = data.ip_address || vm.provider_ip || null;
  const resources = getEffectiveResources(data, vm) || vm.resources;
  const next: Rental = {
    ...vm,
    status: terminal ? "terminated" : status,
    lifecycle_stage: data.lifecycle_stage ?? vm.lifecycle_stage,
    status_message: data.status_message ?? vm.status_message,
    progress: data.progress ?? vm.progress,
    transitioning: data.transitioning ?? vm.transitioning,
    next_poll_seconds: data.next_poll_seconds ?? vm.next_poll_seconds,
    ssh_port: sshPort,
    provider_ip: providerIp,
    resources,
    ...(terminal ? { ended_at: Math.floor(Date.now() / 1000) } : {}),
  };

  if (
    next.status === vm.status &&
    next.ssh_port === vm.ssh_port &&
    next.provider_ip === vm.provider_ip &&
    next.lifecycle_stage === vm.lifecycle_stage &&
    next.status_message === vm.status_message &&
    next.progress === vm.progress &&
    next.transitioning === vm.transitioning &&
    next.next_poll_seconds === vm.next_poll_seconds &&
    JSON.stringify(next.resources || null) ===
      JSON.stringify(vm.resources || null)
  ) {
    return null;
  }

  return next;
}

function buildExplorerUrl(baseUrl: string | null | undefined, address: string) {
  if (!baseUrl || !address) return null;
  const trimmed = baseUrl.replace(/\/$/, "");
  if (trimmed.includes("{address}")) {
    return trimmed.replace("{address}", address);
  }
  return `${trimmed}/address/${address}`;
}
