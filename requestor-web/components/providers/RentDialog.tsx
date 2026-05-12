"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { BrowserProvider, Contract, parseUnits } from "ethers";
import { RiCloseLine } from "@remixicon/react";
import streamPayment from "../../public/abi/StreamPayment.json";
import erc20 from "../../public/abi/ERC20.json";
import {
  computeEstimate,
  createVm,
  loadRentals,
  loadSettings,
  saveRentals,
  vmAccess,
  vmJobStatus,
  type AdsConfig,
  type CreateVMRequest,
  type ProviderAd,
  type SSHKey,
} from "../../lib/api";
import { getPaymentNetworkErrorMessage } from "../../lib/chain";
import { parseHumanDuration } from "../../lib/time";
import { useSettings } from "../../hooks/useSettings";
import { useWallet } from "../../context/WalletContext";
import { useProjects } from "../../context/ProjectsContext";
import { PAYMENT_PRICE_MAX_AGE_MS, usdToTokenAsync } from "../../lib/prices";
import { Modal } from "../ui/Modal";
import {
  DurationSelector,
  DURATION_OPTIONS,
} from "./rent-dialog/DurationSelector";
import { PaymentSettingsPanel } from "./rent-dialog/PaymentSettingsPanel";
import { PricingEstimatePanel } from "./rent-dialog/PricingEstimatePanel";
import { ProviderSummaryCard } from "./rent-dialog/ProviderSummaryCard";
import { RentDialogFooter } from "./rent-dialog/RentDialogFooter";
import { SectionCard } from "./rent-dialog/SectionCard";
import { VmConfigPanel } from "./rent-dialog/VmConfigPanel";
import { VmDetailsPanel } from "./rent-dialog/VmDetailsPanel";
import {
  clampSpec,
  durationTotal,
  hourlyGlm,
  priceLine,
} from "./rent-dialog/formatting";
import type { DurationPreset, RentSpec } from "./rent-dialog/types";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

export function RentDialog({
  provider,
  defaultSpec,
  onClose,
  adsMode,
}: {
  provider: ProviderAd;
  defaultSpec: { cpu?: number; memory?: number; storage?: number };
  onClose: () => void;
  adsMode: AdsConfig;
}) {
  const router = useRouter();
  const { displayCurrency } = useSettings();
  const {
    isConnected,
    account,
    expectedChain,
    paymentReady,
    paymentMessage,
    networkStatus,
    connect,
    switchToPaymentsNetwork,
    ensurePaymentsNetwork,
  } = useWallet();
  const { activeId: activeProjectId } = useProjects();
  const settings = React.useMemo(() => loadSettings(), []);
  const initialKeys: SSHKey[] =
    settings.ssh_keys ||
    (settings.ssh_public_key
      ? [{ id: "default", name: "Default", value: settings.ssh_public_key }]
      : []);
  const defaultKeyId = settings.default_ssh_key_id || initialKeys[0]?.id || "";
  const defaultKey = initialKeys.find((key) => key.id === defaultKeyId);

  const [spec, setSpec] = React.useState<RentSpec>(() =>
    clampSpec(defaultSpec, provider),
  );
  const [name, setName] = React.useState(
    () => `vm-${provider.provider_id.slice(-4).toLowerCase()}`,
  );
  const [sshKey, setSshKey] = React.useState(
    defaultKey?.value || settings.ssh_public_key || "",
  );
  const [selectedKeyId, setSelectedKeyId] = React.useState(defaultKeyId);
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [streamId, setStreamId] = React.useState<string | null>(null);
  const [connecting, setConnecting] = React.useState(false);
  const [preset, setPreset] = React.useState<DurationPreset>("30d");
  const [customInput, setCustomInput] = React.useState("");

  React.useEffect(() => {
    setSpec(clampSpec(defaultSpec, provider));
    setName(`vm-${provider.provider_id.slice(-4).toLowerCase()}`);
    setStreamId(null);
    setError(null);
  }, [defaultSpec.cpu, defaultSpec.memory, defaultSpec.storage, provider]);

  const customSeconds = React.useMemo(() => {
    const seconds = parseHumanDuration(customInput || "");
    return seconds && seconds > 0 ? seconds : 0;
  }, [customInput]);

  const durationSeconds = React.useMemo(() => {
    if (preset === "custom") return customSeconds;
    return (
      DURATION_OPTIONS.find((option) => option.preset === preset)?.seconds || 0
    );
  }, [customSeconds, preset]);

  const estimate = React.useMemo(
    () => computeEstimate(provider, spec.cpu, spec.memory, spec.storage),
    [provider, spec.cpu, spec.memory, spec.storage],
  );
  const preferToken = displayCurrency === "token";
  const hourlyLine = priceLine(
    estimate.usd_per_hour,
    hourlyGlm(estimate.glm_per_month),
    preferToken,
  );
  const monthlyLine = priceLine(
    estimate.usd_per_month,
    estimate.glm_per_month,
    preferToken,
  );
  const depositLine = priceLine(
    durationTotal(estimate.usd_per_month, durationSeconds),
    durationTotal(estimate.glm_per_month, durationSeconds),
    preferToken,
  );
  const disabledReason = getDisabledReason({
    name,
    sshKey,
    durationSeconds,
    paymentReady,
  });
  const submitDisabled = Boolean(disabledReason);

  const openStream = async (): Promise<string> => {
    setError(null);
    await ensurePaymentsNetwork();
    const { ethereum } = window as any;
    if (!ethereum) throw new Error("MetaMask not detected");

    let providerInfoJson = null;
    try {
      providerInfoJson = await (
        await import("../../lib/api")
      ).providerInfo(provider.provider_id, adsMode);
    } catch (providerInfoError) {
      console.warn(
        "Provider payment metadata unavailable, using local payment settings",
        providerInfoError,
      );
    }

    const cfg = loadSettings();
    const spAddr = (
      providerInfoJson?.stream_payment_address ||
      cfg.stream_payment_address ||
      process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS ||
      ""
    ).trim();
    if (!spAddr)
      throw new Error(
        "StreamPayment address missing (set in Settings or provided by provider)",
      );
    const token = [
      providerInfoJson?.glm_token_address,
      cfg.glm_token_address,
      process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS,
    ]
      .map((value) => String(value || "").trim())
      .find((value) => value && value.toLowerCase() !== ZERO_ADDRESS);
    if (!token) {
      throw new Error(
        "GLM token address missing (set in Settings or provided by provider)",
      );
    }

    const browserProvider = new BrowserProvider(ethereum);
    const signer = await browserProvider.getSigner(account ?? undefined);
    const glm = new Contract(token, (erc20 as any).abi, signer);
    const decimals = Number(await glm.decimals().catch(() => 18));

    let glmPerMonth: number | null = estimate.glm_per_month ?? null;
    if (glmPerMonth == null) {
      glmPerMonth = await usdToTokenAsync("GLM", estimate.usd_per_month, {
        maxAgeMs: PAYMENT_PRICE_MAX_AGE_MS,
      });
      if (glmPerMonth == null) {
        throw new Error("GLM/USD price unavailable to compute rate");
      }
    }
    const glmPerSecond = glmPerMonth / (30.4167 * 24 * 3600);
    const ratePerSecondWei = parseUnits(
      glmPerSecond.toFixed(decimals),
      decimals,
    );
    if (ratePerSecondWei <= 0n)
      throw new Error("Computed GLM rate is too small");
    const depositWei = ratePerSecondWei * BigInt(Math.max(1, durationSeconds));

    const owner = await signer.getAddress();
    const allowance = await glm.allowance(owner, spAddr);
    if (allowance < depositWei) {
      const approveTx = await glm.approve(spAddr, depositWei);
      await approveTx.wait();
    }

    const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
    const recipient = provider.provider_id;
    const tx = await contract.createStream(
      token,
      recipient,
      depositWei,
      ratePerSecondWei,
      {
        gasLimit: 350000n,
      },
    );
    const receipt = await tx.wait();
    const event = receipt?.logs?.find?.(
      (log: any) => String(log?.fragment?.name) === "StreamCreated",
    );
    const sid = event?.args?.[0] ?? null;
    if (!sid) throw new Error("Stream id not found");
    const newId = String(sid);
    setStreamId(newId);
    return newId;
  };

  const create = async () => {
    try {
      setCreating(true);
      setError(null);
      const sid = streamId || (await openStream());
      const payload: CreateVMRequest = {
        name: name.trim(),
        resources: spec,
        ssh_key: sshKey,
        stream_id: Number(sid),
      };
      const vm = await createVm(provider.provider_id, payload, adsMode);
      const jobId = (vm as any)?.job_id || null;
      let vmId = (vm as any)?.vm_id || (vm as any)?.id || null;
      if (!vmId && jobId) {
        for (let attempt = 0; attempt < 40; attempt += 1) {
          await new Promise((resolve) => setTimeout(resolve, 2000));
          try {
            const status = await vmJobStatus(
              provider.provider_id,
              jobId,
              adsMode,
            );
            vmId = status?.vm_id || null;
            if (vmId) break;
          } catch (pollError) {
            console.warn("VM creation status poll failed", pollError);
          }
        }
      }
      if (!vmId) throw new Error("VM id not available");

      const entry = {
        name: payload.name,
        provider_id: provider.provider_id,
        provider_ip: provider.ip_address || null,
        platform: provider.platform || null,
        resources: spec,
        vm_id: vmId,
        creation_job_id: jobId,
        ssh_port: null,
        ssh_user: null,
        stream_id: String(sid),
        project_id: activeProjectId || "default",
        status: String((vm as any)?.status || "creating"),
        lifecycle_stage: (vm as any)?.lifecycle_stage || "queued",
        status_message: (vm as any)?.status_message || "Queued VM creation",
        progress: Number((vm as any)?.progress ?? 0),
        transitioning: Boolean((vm as any)?.transitioning ?? true),
        next_poll_seconds: Number((vm as any)?.next_poll_seconds ?? 2),
        created_at: Math.floor(Date.now() / 1000),
      };
      saveRentals([entry as any, ...loadRentals()]);
      try {
        const access = await vmAccess(provider.provider_id, vmId, adsMode);
        if (access?.ssh_port) {
          const current = loadRentals();
          const index = current.findIndex(
            (rental) =>
              rental.vm_id === vmId &&
              rental.provider_id === provider.provider_id,
          );
          if (index >= 0) {
            current[index] = {
              ...current[index],
              ssh_port: access.ssh_port,
              ssh_user: access.ssh_user,
              status: "running",
            };
            saveRentals(current);
          }
        }
      } catch (accessError) {
        console.warn(
          "VM access details unavailable after creation",
          accessError,
        );
      }
      onClose();
      router.push(`/vm?id=${encodeURIComponent(vmId)}`);
    } catch (createError: any) {
      setError(getPaymentNetworkErrorMessage(createError, expectedChain));
    } finally {
      setCreating(false);
    }
  };

  const paymentAction = async () => {
    setConnecting(true);
    setError(null);
    try {
      if (!isConnected) await connect();
      else await switchToPaymentsNetwork();
    } catch (paymentError) {
      setError(getPaymentNetworkErrorMessage(paymentError, expectedChain));
    } finally {
      setConnecting(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="6xl"
      className="flex max-h-[90vh] flex-col overflow-hidden"
    >
      <div className="min-h-0 flex-1 overflow-y-auto px-6 pt-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-text-primary">
              Rent a VM
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              Configure your virtual machine and open a payment stream.
            </p>
          </div>
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-md text-text-secondary hover:bg-surface-muted hover:text-text-primary"
            aria-label="Close rent VM dialog"
            onClick={onClose}
            disabled={creating}
          >
            <RiCloseLine className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-5">
            <ProviderSummaryCard provider={provider} />
            <VmConfigPanel
              provider={provider}
              spec={spec}
              onSpecChange={setSpec}
            />
            <VmDetailsPanel
              name={name}
              selectedKeyId={selectedKeyId}
              onNameChange={setName}
              onSshKeyChange={(id, key) => {
                setSelectedKeyId(id);
                setSshKey(key.value || key.public_key || "");
              }}
            />
          </div>

          <div className="space-y-4 lg:col-span-4">
            <SectionCard title="4. Initial deposit duration">
              <DurationSelector
                preset={preset}
                customInput={customInput}
                customSeconds={customSeconds}
                onPresetChange={setPreset}
                onCustomInputChange={setCustomInput}
              />
              <div className="mt-5 rounded-md bg-primary-soft px-4 py-3 text-center text-sm text-text-secondary">
                The payment stream will be created for the selected duration.
              </div>
            </SectionCard>
            <PaymentSettingsPanel
              walletConnected={isConnected}
              paymentReady={paymentReady}
              paymentMessage={paymentMessage}
              connecting={connecting}
              networkStatus={networkStatus}
              chainName={expectedChain.chainName}
              error={error}
              onPaymentAction={paymentAction}
            />
          </div>

          <div className="lg:col-span-3">
            <PricingEstimatePanel
              hourly={hourlyLine}
              monthly={monthlyLine}
              deposit={depositLine}
              durationSeconds={durationSeconds}
            />
          </div>
        </div>
      </div>

      <div className="shrink-0">
        <RentDialogFooter
          disabled={submitDisabled}
          creating={creating}
          streamReady={Boolean(streamId)}
          disabledReason={disabledReason || ""}
          onCancel={onClose}
          onCreate={create}
        />
      </div>
    </Modal>
  );
}

function getDisabledReason({
  name,
  sshKey,
  durationSeconds,
  paymentReady,
}: {
  name: string;
  sshKey: string;
  durationSeconds: number;
  paymentReady: boolean;
}) {
  if (!name.trim()) return "Enter a VM name to continue.";
  if (!sshKey.trim()) return "Select or add an SSH key to continue.";
  if (!durationSeconds) return "Select a valid deposit duration to continue.";
  if (!paymentReady) return "Complete all required fields to continue.";
  return "";
}
