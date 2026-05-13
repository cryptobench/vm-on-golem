"use client";

import React from "react";
import { useRouter } from "next/navigation";
import {
  RiAddLine,
  RiArrowRightSLine,
  RiCalendarLine,
  RiCheckboxCircleLine,
  RiCloseLine,
  RiCpuLine,
  RiDatabase2Line,
  RiInformationLine,
  RiRamLine,
} from "@remixicon/react";
import {
  computeEstimate,
  createVm,
  loadRentals,
  loadSettings,
  saveRentals,
  saveSettings,
  vmAccess,
  vmJobStatus,
  type AdsConfig,
  type CreateVMRequest,
  type Rental,
  type ProviderAd,
  type SSHKey,
} from "../../lib/api";
import type { RemixiconComponentType } from "@remixicon/react";
import { getPaymentNetworkErrorMessage } from "../../lib/chain";
import { markCreateFailedSettled } from "../../lib/rentalLifecycle";
import { openPaymentStream } from "../../lib/paymentStreams";
import { vmDetailsHref } from "../../lib/routes";
import { terminateStreamWithWallet } from "../../lib/streams";
import { parseHumanDuration } from "../../lib/time";
import { useWallet } from "../../context/WalletContext";
import { useProjects } from "../../context/ProjectsContext";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { KeyAddModal } from "../ssh/KeyAddModal";
import { NumberStepper } from "../ui/NumberStepper";
import { Spinner } from "../ui/Spinner";
import { cn } from "../ui/cn";
import {
  clampSpec,
  durationTotal,
  formatUsd,
  hourlyGlm,
} from "./rent-dialog/formatting";
import type { DurationPreset, RentSpec } from "./rent-dialog/types";

const RENT_STEPS = [
  "Choose specs",
  "Rental duration",
  "Access",
  "Review",
] as const;

const DURATION_OPTIONS: Array<{
  preset: Exclude<DurationPreset, "custom"> | "24h";
  label: string;
  seconds: number;
}> = [
  { preset: "24h", label: "24 hours", seconds: 24 * 3600 },
  { preset: "1w", label: "7 days", seconds: 7 * 24 * 3600 },
  { preset: "2w", label: "14 days", seconds: 14 * 24 * 3600 },
  { preset: "30d", label: "30 days", seconds: 30 * 24 * 3600 },
];

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
    () => `vm-${provider.provider_id.slice(-4).toLowerCase()}`,
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
  const [step, setStep] = React.useState(0);
  const [preset, setPreset] = React.useState<DurationPreset | "24h">("30d");
  const [customInput, setCustomInput] = React.useState("");

  React.useEffect(() => {
    setSpec(clampSpec(defaultSpec, provider));
    setName(`vm-${provider.provider_id.slice(-4).toLowerCase()}`);
    setStreamId(null);
    setOpenedStreamPaymentAddress("");
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

  const openStream = async (): Promise<{
    id: string;
    contractAddress: string;
  }> => {
    setError(null);
    const opened = await openPaymentStream({
      provider,
      resources: spec,
      durationSeconds,
      ads: adsMode,
      account,
      ensurePaymentsNetwork,
      onPhase: setPhase,
    });
    setStreamId(opened.id);
    setOpenedStreamPaymentAddress(opened.contractAddress);
    return opened;
  };

  const create = async () => {
    let pendingEntry: Rental | null = null;
    let activeStreamPaymentAddress = "";
    try {
      setCreating(true);
      setError(null);
      setPhase(paymentReady ? "Preparing VM rental" : "Preparing wallet");
      const opened = streamId
        ? {
            id: String(streamId),
            contractAddress: (
              openedStreamPaymentAddress ||
              loadSettings().stream_payment_address ||
              process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS ||
              ""
            ).trim(),
          }
        : await openStream();
      const activeStreamId = opened.id;
      activeStreamPaymentAddress = opened.contractAddress;
      setPhase("Creating VM on provider");
      const payload: CreateVMRequest = {
        name: name.trim(),
        resources: spec,
        ssh_key: sshKey,
        stream_id: Number(activeStreamId),
      };
      pendingEntry = {
        name: payload.name,
        provider_id: provider.provider_id,
        provider_ip: provider.ip_address || null,
        platform: provider.platform || null,
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
      const vm = await createVm(provider.provider_id, payload, adsMode);
      const jobId = (vm as any)?.job_id || null;
      let vmId = (vm as any)?.vm_id || (vm as any)?.id || null;
      if (!vmId && jobId) {
        setPhase("Waiting for VM creation job");
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
      try {
        setPhase("Loading VM access details");
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
      router.push(vmDetailsHref(vmId));
    } catch (createError: any) {
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
      setError(getPaymentNetworkErrorMessage(createError, expectedChain));
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
    <Modal
      open
      onClose={onClose}
      size="6xl"
      className="flex h-[calc(100vh-2rem)] max-h-[calc(100vh-2rem)] flex-col overflow-hidden rounded-lg"
    >
      <div className="shrink-0 px-6 pt-6 sm:px-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text-primary">
              Rent a VM
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              Configure your virtual machine and choose a rental duration.
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
      </div>

      <div className="mt-6 grid min-h-0 flex-1 grid-cols-1 overflow-hidden border-t border-border md:grid-cols-[13rem_minmax(0,1fr)]">
        <StepProgress step={step} onStepChange={setStep} />

        <main
          key={step}
          className="rent-vm-step min-h-0 min-w-0 overflow-y-auto px-6 py-6 sm:px-8"
        >
          {step === 0 ? (
            <SpecsStep provider={provider} spec={spec} onSpecChange={setSpec} />
          ) : null}
          {step === 1 ? (
            <DurationStep
              preset={preset}
              customInput={customInput}
              customSeconds={customSeconds}
              monthlyUsd={estimate.usd_per_month}
              onPresetChange={setPreset}
              onCustomInputChange={setCustomInput}
            />
          ) : null}
          {step === 2 ? (
            <AccessStep
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
            <ReviewStep
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
            <div className="mt-5 rounded-md border border-danger bg-danger-soft px-4 py-3 text-sm text-danger">
              {error}
            </div>
          ) : null}
        </main>
      </div>

      <BottomSummaryBar
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
    </Modal>
  );
}

function StepProgress({
  step,
  onStepChange,
}: {
  step: number;
  onStepChange: (step: number) => void;
}) {
  return (
    <nav
      aria-label="Rent VM progress"
      className="overflow-x-auto border-b border-border px-5 py-4 md:border-b-0 md:border-r md:py-6"
    >
      <ol className="flex gap-4 md:block md:space-y-5">
        {RENT_STEPS.map((label, index) => {
          const complete = index < step;
          const active = index === step;
          return (
            <li key={label} className="flex items-center gap-3">
              <button
                type="button"
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium transition",
                  active && "border-primary bg-primary text-white",
                  complete && "border-primary bg-primary-soft text-primary",
                  !active &&
                    !complete &&
                    "border-border-strong bg-surface text-text-secondary",
                )}
                onClick={() => {
                  if (index <= step) onStepChange(index);
                }}
                disabled={index > step}
                aria-current={active ? "step" : undefined}
              >
                {complete ? (
                  <RiCheckboxCircleLine className="h-4 w-4" aria-hidden />
                ) : (
                  index + 1
                )}
              </button>
              <span
                className={cn(
                  "whitespace-nowrap text-sm",
                  active || complete
                    ? "font-medium text-text-primary"
                    : "text-text-secondary",
                )}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function SpecsStep({
  provider,
  spec,
  onSpecChange,
}: {
  provider: ProviderAd;
  spec: RentSpec;
  onSpecChange: (spec: RentSpec) => void;
}) {
  return (
    <section className="mx-auto max-w-4xl">
      <h3 className="text-lg font-semibold text-text-primary">
        Choose your specs
      </h3>
      <p className="mt-2 text-sm text-text-secondary">
        Select the resources your VM will have.
      </p>
      <div className="mt-8 space-y-8">
        <SpecRow
          icon={RiCpuLine}
          label="vCPU (Cores)"
          value={spec.cpu}
          unit="vCPU"
          min={1}
          max={provider.resources.cpu}
          onChange={(cpu) => onSpecChange({ ...spec, cpu })}
        />
        <SpecRow
          icon={RiRamLine}
          label="RAM (GB)"
          value={spec.memory}
          unit="GB"
          min={1}
          max={provider.resources.memory}
          onChange={(memory) => onSpecChange({ ...spec, memory })}
        />
        <SpecRow
          icon={RiDatabase2Line}
          label="Storage (GB)"
          value={spec.storage}
          unit="GB"
          min={1}
          max={provider.resources.storage}
          onChange={(storage) => onSpecChange({ ...spec, storage })}
        />
      </div>
    </section>
  );
}

function SpecRow({
  icon: Icon,
  label,
  value,
  unit,
  min,
  max,
  onChange,
}: {
  icon: RemixiconComponentType;
  label: string;
  value: number;
  unit: string;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  const safeMax = Math.max(min, Math.floor(max || min));
  return (
    <div className="grid gap-4 sm:grid-cols-[11rem_10rem_minmax(12rem,1fr)] sm:items-center">
      <div className="flex min-w-0 items-center gap-4">
        <Icon className="h-5 w-5 shrink-0 text-text-secondary" aria-hidden />
        <div className="min-w-0 text-sm font-semibold text-text-primary">
          {label}
        </div>
      </div>
      <div className="w-40">
        <NumberStepper
          label={label}
          value={value}
          min={min}
          max={safeMax}
          onChange={onChange}
          hideLabel
        />
      </div>
      <div className="flex flex-wrap items-center gap-x-1 gap-y-1 text-xs text-text-secondary">
        <span>
          Min {min} {unit} · Max {safeMax} {unit}
        </span>
        {label.startsWith("Storage") ? (
          <span className="inline-flex items-center gap-1">
            Storage can only be increased later
            <RiInformationLine className="h-3.5 w-3.5" aria-hidden />
          </span>
        ) : null}
      </div>
    </div>
  );
}

function DurationStep({
  preset,
  customInput,
  customSeconds,
  monthlyUsd,
  onPresetChange,
  onCustomInputChange,
}: {
  preset: DurationPreset | "24h";
  customInput: string;
  customSeconds: number;
  monthlyUsd?: number;
  onPresetChange: (preset: DurationPreset | "24h") => void;
  onCustomInputChange: (value: string) => void;
}) {
  return (
    <section className="mx-auto max-w-4xl">
      <h3 className="text-lg font-semibold text-text-primary">
        Choose your rental duration
      </h3>
      <p className="mt-2 text-sm text-text-secondary">
        Select a duration or enter a custom one.
      </p>
      <div className="mt-6 grid gap-3 sm:grid-cols-4">
        {DURATION_OPTIONS.map((option) => (
          <DurationCard
            key={option.preset}
            active={preset === option.preset}
            label={option.label}
            total={formatUsd(durationTotal(monthlyUsd, option.seconds) || 0)}
            onClick={() => onPresetChange(option.preset)}
          />
        ))}
      </div>
      <label className="label mt-7">Custom duration</label>
      <div className="relative mt-2 max-w-2xl">
        <input
          className="input h-10 pr-10"
          placeholder="e.g. 2d 12h or 45h 30m"
          value={customInput}
          onChange={(event) => {
            onPresetChange("custom");
            onCustomInputChange(event.target.value);
          }}
        />
        <RiInformationLine
          className="absolute right-3 top-3 h-4 w-4 text-text-secondary"
          aria-hidden
        />
      </div>
      <div className="mt-3 text-sm text-text-secondary">
        Enter a duration in days (d) and hours (h). Minimum is 1 hour.
      </div>
      {preset === "custom" && customInput.trim() && customSeconds <= 0 ? (
        <div className="mt-2 text-sm text-danger">Enter a valid duration.</div>
      ) : null}
    </section>
  );
}

function DurationCard({
  active,
  label,
  total,
  onClick,
}: {
  active: boolean;
  label: string;
  total: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn(
        "relative flex min-h-28 flex-col items-center justify-center rounded-md border border-border bg-surface px-4 py-4 text-center transition hover:border-border-strong hover:bg-surface-muted",
        active && "border-primary ring-1 ring-primary",
      )}
      onClick={onClick}
    >
      {active ? (
        <RiCheckboxCircleLine
          className="absolute right-3 top-3 h-5 w-5 text-primary"
          aria-hidden
        />
      ) : null}
      <span className="font-semibold text-text-primary">{label}</span>
      <span className="mt-5 font-semibold text-text-primary">{total}</span>
      <span className="mt-1 text-sm text-text-secondary">total</span>
    </button>
  );
}

function AccessStep({
  name,
  keys,
  selectedKeyId,
  defaultKeyId,
  onNameChange,
  onSshKeyChange,
  onSshKeyAdded,
}: {
  name: string;
  keys: SSHKey[];
  selectedKeyId: string;
  defaultKeyId: string;
  onNameChange: (value: string) => void;
  onSshKeyChange: (id: string, key: SSHKey) => void;
  onSshKeyAdded: (key: SSHKey) => void;
}) {
  const [openAdd, setOpenAdd] = React.useState(false);

  return (
    <section className="mx-auto max-w-2xl">
      <h3 className="text-lg font-semibold text-text-primary">Set up access</h3>
      <p className="mt-2 text-sm text-text-secondary">
        Choose or add an SSH key to access your VM.
      </p>
      <div className="mt-8">
        <label className="label">SSH key</label>
        <div className="relative mt-2">
          <select
            className="input h-10 appearance-none pr-10"
            value={selectedKeyId}
            disabled={!keys.length}
            onChange={(event) => {
              const key = keys.find((item) => item.id === event.target.value);
              if (key) onSshKeyChange(key.id, key);
            }}
          >
            {keys.length ? (
              keys.map((key) => (
                <option key={key.id} value={key.id}>
                  {key.name || "Unnamed key"}
                  {key.id === defaultKeyId ? " (default)" : ""}
                </option>
              ))
            ) : (
              <option>No SSH keys saved</option>
            )}
          </select>
          <RiArrowRightSLine
            className="pointer-events-none absolute right-3 top-3 h-4 w-4 rotate-90 text-text-secondary"
            aria-hidden
          />
        </div>
        <button
          type="button"
          className="mt-3 inline-flex h-10 items-center gap-2 rounded-md px-2 text-sm font-medium text-primary hover:bg-primary-soft"
          onClick={() => setOpenAdd(true)}
        >
          <RiAddLine className="h-4 w-4" aria-hidden />
          Add new SSH key
        </button>
        <KeyAddModal
          open={openAdd}
          onClose={() => setOpenAdd(false)}
          onAdded={onSshKeyAdded}
        />
      </div>

      <div className="mt-8">
        <label className="label">VM name</label>
        <input
          className="input mt-2 h-10"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="vm-ed1d"
        />
        <p className="mt-3 text-sm text-text-secondary">
          Use a descriptive name to easily identify your VM.
        </p>
      </div>
    </section>
  );
}

function ReviewStep({
  spec,
  name,
  keyName,
  keyFingerprint,
  durationLabel: displayDurationLabel,
  startsAt,
  endsAt,
  onEdit,
}: {
  spec: RentSpec;
  name: string;
  keyName: string;
  keyFingerprint: string;
  durationLabel: string;
  startsAt: Date;
  endsAt: Date;
  onEdit: (step: number) => void;
}) {
  return (
    <section className="mx-auto max-w-4xl">
      <h3 className="text-lg font-semibold text-text-primary">
        Review and confirm
      </h3>
      <p className="mt-2 text-sm text-text-secondary">
        Please review your configuration before creating the VM.
      </p>
      <div className="mt-5 overflow-hidden rounded-lg border border-border bg-surface">
        <ReviewRow
          label="Specs"
          value={`${spec.cpu} vCPU · ${spec.memory} GB RAM · ${spec.storage} GB Storage`}
          onEdit={() => onEdit(0)}
        />
        <ReviewRow
          label="Duration"
          value={`${displayDurationLabel} (${formatDate(startsAt)} - ${formatDate(endsAt)})`}
          onEdit={() => onEdit(1)}
        />
        <ReviewRow
          label="Access (SSH key)"
          value={`${keyName} (${keyFingerprint})`}
          onEdit={() => onEdit(2)}
        />
        <ReviewRow label="VM name" value={name} onEdit={() => onEdit(2)} />
      </div>
      <InfoCallout>
        By creating this VM, a payment stream will be opened for the selected
        duration.
      </InfoCallout>
    </section>
  );
}

function ReviewRow({
  label,
  value,
  onEdit,
}: {
  label: string;
  value: string;
  onEdit: () => void;
}) {
  return (
    <button
      type="button"
      className="grid min-h-14 w-full grid-cols-[8rem_minmax(0,1fr)_2rem] items-center gap-4 border-b border-border px-4 py-3 text-left text-sm last:border-b-0 hover:bg-surface-muted"
      onClick={onEdit}
    >
      <span className="text-text-secondary">{label}</span>
      <span className="truncate font-medium text-text-primary">{value}</span>
      <RiArrowRightSLine className="h-4 w-4 justify-self-end text-text-secondary" />
    </button>
  );
}

function BottomSummaryBar({
  step,
  spec,
  durationLabel,
  estimateLabel,
  estimatePrimary,
  estimateSecondary,
  creating,
  phase,
  disabledReason,
  onCancel,
  onBack,
  onContinue,
  actionDisabled,
}: {
  step: number;
  spec: RentSpec;
  durationLabel: string;
  estimateLabel: string;
  estimatePrimary: string;
  estimateSecondary: string;
  creating: boolean;
  phase: string;
  disabledReason: string;
  onCancel: () => void;
  onBack: () => void;
  onContinue: () => void;
  actionDisabled: boolean;
}) {
  return (
    <div className="shrink-0 border-t border-border px-6 py-4 sm:px-8">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_10rem_auto] lg:items-center">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-text-primary">Summary</div>
          <div className="mt-2 grid gap-3 text-xs text-text-primary sm:grid-cols-4">
            <SummaryChip icon={RiCpuLine} label={`${spec.cpu} vCPU`} />
            <SummaryChip icon={RiRamLine} label={`${spec.memory} GB RAM`} />
            <SummaryChip
              icon={RiDatabase2Line}
              label={`${spec.storage} GB Storage`}
            />
            <SummaryChip
              icon={RiCalendarLine}
              label={step === 0 ? "-" : durationLabel}
            />
          </div>
          {creating && phase ? (
            <div className="mt-2 inline-flex items-center gap-2 text-sm text-text-secondary">
              <Spinner className="h-4 w-4 text-primary" />
              {phase}
            </div>
          ) : disabledReason ? (
            <div className="mt-2 text-sm text-text-secondary">
              {disabledReason}
            </div>
          ) : null}
        </div>
        <div className="border-border lg:border-l lg:pl-6">
          <div className="text-xs font-semibold text-text-secondary">
            {estimateLabel}
          </div>
          <div className="mt-1 text-xl font-semibold text-text-primary">
            {estimatePrimary}
          </div>
          <div className="text-xs text-text-secondary">
            approx. {estimateSecondary}
          </div>
        </div>
        <div className="flex gap-3 lg:justify-end">
          {step === 0 ? (
            <Button
              variant="secondary"
              className="min-w-28"
              onClick={onCancel}
              disabled={creating}
            >
              Back
            </Button>
          ) : (
            <Button
              variant="secondary"
              className="min-w-28"
              onClick={onBack}
              disabled={creating}
            >
              Back
            </Button>
          )}
          <Button
            className="min-w-36"
            onClick={onContinue}
            disabled={actionDisabled}
            busy={creating}
          >
            {step === RENT_STEPS.length - 1 ? "Create VM" : "Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function SummaryChip({
  icon: Icon,
  label,
}: {
  icon: RemixiconComponentType;
  label: string;
}) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <Icon className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden />
      <span className="truncate">{label}</span>
    </span>
  );
}

function InfoCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-7 flex gap-3 rounded-md bg-primary-soft px-4 py-3 text-sm text-text-secondary">
      <RiInformationLine
        className="mt-0.5 h-4 w-4 shrink-0 text-primary"
        aria-hidden
      />
      <span>{children}</span>
    </div>
  );
}

function getStepDisabledReason({
  step,
  name,
  sshKey,
  durationSeconds,
  preset,
  customInput,
}: {
  step: number;
  name: string;
  sshKey: string;
  durationSeconds: number;
  preset: DurationPreset | "24h";
  customInput: string;
}) {
  if (step >= 1 && !durationSeconds) {
    if (preset === "custom" && customInput.trim()) {
      return "Enter a valid custom duration to continue.";
    }
    return "Select a valid rental duration to continue.";
  }
  if (step >= 2 && !name.trim()) return "Enter a VM name to continue.";
  if (step >= 2 && !sshKey.trim())
    return "Select or add an SSH key to continue.";
  return "";
}

function formatGlm(value?: number) {
  if (value == null || Number.isNaN(value)) return "0";
  if (value >= 100) return value.toFixed(2);
  if (value >= 1) return value.toFixed(4);
  return value.toFixed(6);
}

function formatDurationLabel(seconds: number) {
  if (!seconds) return "Duration required";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (days) parts.push(`${days}d`);
  if (hours) parts.push(`${hours}h`);
  if (minutes) parts.push(`${minutes}m`);
  return parts.join(" ") || "1h";
}

function formatDate(date: Date) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function fingerprintForKey(key: SSHKey | null, fallback: string) {
  const source = key?.value || key?.public_key || fallback;
  const body = source.split(" ")[1] || source;
  if (!body) return "Unavailable";
  const compact = body.replace(/\s+/g, "");
  if (compact.length <= 36) return compact;
  return `SHA256:${compact.slice(0, 24)}...${compact.slice(-12)}`;
}
