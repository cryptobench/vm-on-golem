"use client";

import React from "react";
import { useRouter } from "next/navigation";
import {
  computeEstimate,
  createVm,
  loadRentals,
  loadSettings,
  providerEndpointUrl,
  saveRentals,
  saveSettings,
  type AdsConfig,
  type CreateVMRequest,
  type Rental,
  type ProviderAd,
  type SSHKey,
} from "../../lib/api";
import { getPaymentNetworkErrorMessage } from "../../lib/chain";
import { markCreateFailedSettled } from "../../lib/rentalLifecycle";
import {
  openPaymentStream,
  type OpenedPaymentStream,
} from "../../lib/paymentStreams";
import { vmDetailsHref } from "../../lib/routes";
import { getRequestorRuntimeConfig } from "../../lib/runtimeConfig";
import { terminateStreamWithWallet } from "../../lib/streams";
import { parseHumanDuration } from "../../lib/time";
import { generateVmName } from "../../lib/vmNames";
import { walletDebug, walletWarn } from "../../lib/walletDebug";
import { useWallet } from "../../context/WalletContext";
import { useProjects } from "../../context/ProjectsContext";
import { Alert } from "@golem/ui";
import { DialogScaffold } from "@golem/ui";
import { StepProgress } from "@golem/ui";
import {
  clampSpec,
  durationTotal,
  formatUsd,
  hourlyGlm,
} from "./rent-dialog/formatting";
import {
  DURATION_OPTIONS,
  RENT_STEPS,
  type RentDurationPreset,
} from "./rent-dialog/constants";
import {
  fingerprintForKey,
  formatDurationLabel,
  formatGlm,
} from "./rent-dialog/dateFormatting";
import { RentAccessStep } from "./rent-dialog/RentAccessStep";
import { RentDurationStep } from "./rent-dialog/RentDurationStep";
import { RentReviewStep } from "./rent-dialog/RentReviewStep";
import { RentSpecsStep } from "./rent-dialog/RentSpecsStep";
import { RentSummaryBar } from "./rent-dialog/RentSummaryBar";
import { getStepDisabledReason } from "./rent-dialog/validation";
import type { RentSpec } from "./rent-dialog/types";

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
  const { account, expectedChain, paymentReady, ensurePaymentsNetwork } =
    useWallet();
  const { activeId: activeProjectId } = useProjects();
  const settings = React.useMemo(() => loadSettings(), []);
  const initialKeys: SSHKey[] =
    settings.ssh_keys ||
    (settings.ssh_public_key
      ? [{ id: "default", name: "Default", value: settings.ssh_public_key }]
      : []);
  const initialDefaultKeyId =
    settings.default_ssh_key_id || initialKeys[0]?.id || "";
  const defaultKey = initialKeys.find((key) => key.id === initialDefaultKeyId);

  const [spec, setSpec] = React.useState<RentSpec>(() =>
    clampSpec(defaultSpec, provider),
  );
  const [name, setName] = React.useState(
    () => generateVmName(provider.provider_id),
  );
  const [sshKey, setSshKey] = React.useState(
    defaultKey?.value || settings.ssh_public_key || "",
  );
  const [sshKeys, setSshKeys] = React.useState<SSHKey[]>(initialKeys);
  const [defaultKeyId, setDefaultKeyId] = React.useState(initialDefaultKeyId);
  const [selectedKeyId, setSelectedKeyId] = React.useState(initialDefaultKeyId);
  const [selectedSshKey, setSelectedSshKey] = React.useState<SSHKey | null>(
    defaultKey || initialKeys[0] || null,
  );
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [phase, setPhase] = React.useState("");
  const [streamId, setStreamId] = React.useState<string | null>(null);
  const [openedStreamPaymentAddress, setOpenedStreamPaymentAddress] =
    React.useState<string>("");
  const [openedPayment, setOpenedPayment] = React.useState<any>(null);
  const [openedImage, setOpenedImage] = React.useState<string | null>(null);
  const [step, setStep] = React.useState(0);
  const [preset, setPreset] = React.useState<RentDurationPreset>("30d");
  const [customInput, setCustomInput] = React.useState("");

  React.useEffect(() => {
    setSpec(clampSpec(defaultSpec, provider));
    setName(generateVmName(provider.provider_id));
    setStreamId(null);
    setOpenedStreamPaymentAddress("");
    setOpenedPayment(null);
    setOpenedImage(null);
    setError(null);
    setPhase("");
    setStep(0);
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
  const hourlyUsd = formatUsd(estimate.usd_per_hour || 0);
  const hourlyGlmLine = `${formatGlm(hourlyGlm(estimate.glm_per_month))} GLM`;
  const depositUsd = formatUsd(
    durationTotal(estimate.usd_per_month, durationSeconds) || 0,
  );
  const depositGlmLine = `${formatGlm(
    durationTotal(estimate.glm_per_month, durationSeconds),
  )} GLM`;
  const durationLabel = formatDurationLabel(durationSeconds);
  const selectedDurationOption = DURATION_OPTIONS.find(
    (option) => option.preset === preset,
  );
  const displayDurationLabel = selectedDurationOption?.label || durationLabel;
  const startsAt = React.useMemo(() => new Date(), []);
  const endsAt = React.useMemo(() => {
    const end = new Date(startsAt);
    end.setSeconds(end.getSeconds() + durationSeconds);
    return end;
  }, [durationSeconds, startsAt]);
  const selectedKeyName =
    selectedSshKey?.name || (selectedKeyId ? selectedKeyId : "default-key");
  const selectedKeyFingerprint = fingerprintForKey(selectedSshKey, sshKey);
  const currentStepDisabledReason = getStepDisabledReason({
    step,
    name,
    sshKey,
    durationSeconds,
    preset,
    customInput,
  });
  const actionDisabled = Boolean(currentStepDisabledReason) || creating;

  const openStream = async (): Promise<OpenedPaymentStream> => {
    setError(null);
    walletDebug("rent-dialog:open-stream:start", {
      providerId: provider.provider_id,
      durationSeconds,
      spec,
    });
    const opened = await openPaymentStream({
      provider,
      resources: spec,
      durationSeconds,
      ads: adsMode,
      account,
      vmName: name.trim(),
      ensurePaymentsNetwork,
      onPhase: setPhase,
    });
    setStreamId(opened.id);
    setOpenedStreamPaymentAddress(opened.contractAddress);
    setOpenedPayment(opened.payment);
    setOpenedImage(opened.image || null);
    walletDebug("rent-dialog:open-stream:done", {
      providerId: provider.provider_id,
      streamId: opened.id,
      hasPayment: Boolean(opened.payment),
    });
    return opened;
  };

  const create = async () => {
    let pendingEntry: Rental | null = null;
    let activeStreamPaymentAddress = "";
    try {
      const endpointUrl = providerEndpointUrl(provider);
      walletDebug("rent-dialog:create:start", {
        providerId: provider.provider_id,
        endpointUrl,
        paymentReady,
        hasExistingStream: Boolean(streamId),
      });
      setCreating(true);
      setError(null);
      setPhase(paymentReady ? "Preparing VM rental" : "Preparing wallet");
      const opened = streamId
        ? {
            id: String(streamId),
            contractAddress: (
              openedStreamPaymentAddress ||
              loadSettings().stream_payment_address ||
              getRequestorRuntimeConfig().streamPaymentAddress ||
              ""
            ).trim(),
            payment: openedPayment,
            image: openedImage,
          }
        : await openStream();
      const activeStreamId = opened.id;
      activeStreamPaymentAddress = opened.contractAddress;
      setPhase("Creating VM on provider");
      const payload: CreateVMRequest = {
        name: name.trim(),
        resources: spec,
        ssh_key: sshKey,
        payment: opened.payment,
        ...(opened.image ? { image: opened.image } : {}),
      } as CreateVMRequest;
      pendingEntry = {
        name: payload.name,
        provider_id: provider.provider_id,
        provider_endpoint_url: endpointUrl,
        provider_ip: provider.ip_address || null,
        platform: provider.platform || null,
        provider_pricing: provider.pricing || null,
        provider_available_resources: provider.resources || null,
        resources: spec,
        vm_id: payload.name,
        creation_job_id: null,
        ssh_port: null,
        ssh_user: null,
        stream_id: String(activeStreamId),
        project_id: activeProjectId || "default",
        status: "creating",
        lifecycle_stage: "queued",
        status_message: "Queued VM creation",
        progress: 0,
        transitioning: true,
        next_poll_seconds: 2,
        created_at: Math.floor(Date.now() / 1000),
        settlement_status: "pending",
      };
      upsertRental(pendingEntry);
      walletDebug("rent-dialog:create-vm:start", {
        providerId: provider.provider_id,
        endpointUrl,
        streamId: String(activeStreamId),
      });
      const vm = await createVm(endpointUrl, payload);
      walletDebug("rent-dialog:create-vm:done", {
        providerId: provider.provider_id,
        hasJobId: Boolean((vm as any)?.job_id),
        vmId: (vm as any)?.vm_id || (vm as any)?.id || null,
      });
      const jobId = (vm as any)?.job_id || null;
      const vmId = (vm as any)?.vm_id || (vm as any)?.id || null;
      if (!vmId) throw new Error("VM id not available");

      const entry = {
        name: payload.name,
        provider_id: provider.provider_id,
        provider_endpoint_url: endpointUrl,
        provider_ip: provider.ip_address || null,
        platform: provider.platform || null,
        provider_pricing: provider.pricing || null,
        provider_available_resources: provider.resources || null,
        resources: spec,
        vm_id: vmId,
        creation_job_id: jobId,
        ssh_port: null,
        ssh_user: null,
        stream_id: String(activeStreamId),
        project_id: activeProjectId || "default",
        status: String((vm as any)?.status || "creating"),
        lifecycle_stage: (vm as any)?.lifecycle_stage || "queued",
        status_message: (vm as any)?.status_message || "Queued VM creation",
        progress: Number((vm as any)?.progress ?? 0),
        transitioning: Boolean((vm as any)?.transitioning ?? true),
        next_poll_seconds: Number((vm as any)?.next_poll_seconds ?? 2),
        created_at: Math.floor(Date.now() / 1000),
        settlement_status: undefined,
      };
      upsertRental(entry as Rental);
      onClose();
      router.push(vmDetailsHref(vmId));
    } catch (createError: any) {
      walletWarn("rent-dialog:create:failed", createError, {
        providerId: provider.provider_id,
        hasPendingEntry: Boolean(pendingEntry),
        hasActiveStreamPaymentAddress: Boolean(activeStreamPaymentAddress),
      });
      if (pendingEntry && activeStreamPaymentAddress) {
        try {
          await settleFailedCreate(pendingEntry, activeStreamPaymentAddress);
        } catch (settlementError) {
          upsertRental({
            ...pendingEntry,
            status: "terminated",
            create_failed_at: Math.floor(Date.now() / 1000),
            settlement_status: "failed",
            status_message: getPaymentNetworkErrorMessage(settlementError),
          });
          setError(
            getPaymentNetworkErrorMessage(settlementError, expectedChain),
          );
          return;
        }
      } else if (pendingEntry) {
        upsertRental({
          ...pendingEntry,
          status: "terminated",
          create_failed_at: Math.floor(Date.now() / 1000),
          settlement_status: "failed",
          status_message:
            "VM creation failed; stream settlement address missing",
        });
      }
      const message = getPaymentNetworkErrorMessage(createError, expectedChain);
      setError(message && message !== "[object Object]" ? message : "VM creation failed. Check the browser console for wallet details.");
    } finally {
      setCreating(false);
      setPhase("");
    }
  };

  const upsertRental = (entry: Rental) => {
    const current = loadRentals();
    const index = current.findIndex(
      (rental) =>
        (entry.stream_id != null &&
          String(rental.stream_id || "") === String(entry.stream_id)) ||
        (rental.name === entry.name &&
          rental.provider_id === entry.provider_id &&
          rental.project_id === entry.project_id),
    );
    if (index >= 0) {
      const next = [...current];
      next[index] = { ...next[index], ...entry };
      saveRentals(next);
      return;
    }
    saveRentals([entry, ...current]);
  };

  const settleFailedCreate = async (
    pending: Rental,
    streamPaymentAddress: string,
  ) => {
    if (!pending.stream_id) return;
    const txHash = await terminateStreamWithWallet(
      streamPaymentAddress,
      BigInt(pending.stream_id),
    );
    upsertRental(markCreateFailedSettled(pending, { txHash }));
  };

  const selectSshKey = (
    id: string,
    key: SSHKey,
    sourceKeys: SSHKey[] = sshKeys,
  ) => {
    setSelectedKeyId(id);
    setDefaultKeyId(id);
    setSelectedSshKey(key);
    setSshKey(key.value || key.public_key || "");
    saveSettings({
      ssh_keys: sourceKeys,
      default_ssh_key_id: id,
    });
  };

  const continueFlow = () => {
    setError(null);
    if (step < RENT_STEPS.length - 1) {
      setStep((current) => current + 1);
      return;
    }
    create();
  };

  return (
    <DialogScaffold
      title="Rent a VM"
      description="Configure your virtual machine and choose a rental duration."
      closeLabel="Close rent VM dialog"
      closeDisabled={creating}
      onClose={onClose}
      sidebar={
        <StepProgress
          steps={RENT_STEPS}
          currentStep={step}
          label="Rent VM progress"
          onStepChange={setStep}
        />
      }
      footer={
        <RentSummaryBar
          step={step}
          spec={spec}
          durationLabel={displayDurationLabel}
          estimateLabel={step === 0 ? "Est. hourly" : "Est. total"}
          estimatePrimary={step === 0 ? hourlyUsd : depositUsd}
          estimateSecondary={step === 0 ? hourlyGlmLine : depositGlmLine}
          creating={creating}
          phase={phase}
          disabledReason={currentStepDisabledReason}
          onCancel={onClose}
          onBack={() => setStep((current) => Math.max(0, current - 1))}
          onContinue={continueFlow}
          actionDisabled={actionDisabled}
        />
      }
    >
      <div key={step} className="rent-vm-step">
          {step === 0 ? (
            <RentSpecsStep
              provider={provider}
              spec={spec}
              onSpecChange={setSpec}
            />
          ) : null}
          {step === 1 ? (
            <RentDurationStep
              preset={preset}
              customInput={customInput}
              customSeconds={customSeconds}
              monthlyUsd={estimate.usd_per_month}
              onPresetChange={setPreset}
              onCustomInputChange={setCustomInput}
            />
          ) : null}
          {step === 2 ? (
            <RentAccessStep
              name={name}
              keys={sshKeys}
              selectedKeyId={selectedKeyId}
              defaultKeyId={defaultKeyId}
              onNameChange={setName}
              onSshKeyChange={selectSshKey}
              onSshKeyAdded={(key) => {
                const next = [...sshKeys, key];
                setSshKeys(next);
                selectSshKey(key.id, key, next);
              }}
            />
          ) : null}
          {step === 3 ? (
            <RentReviewStep
              spec={spec}
              name={name}
              keyName={selectedKeyName}
              keyFingerprint={selectedKeyFingerprint}
              durationLabel={displayDurationLabel}
              startsAt={startsAt}
              endsAt={endsAt}
              onEdit={setStep}
            />
          ) : null}

          {error ? (
            <Alert tone="danger" className="mt-5">
              {error}
            </Alert>
          ) : null}
      </div>
    </DialogScaffold>
  );
}
