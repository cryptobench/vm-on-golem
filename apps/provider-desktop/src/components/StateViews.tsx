import React from "react";
import {
  Button,
  Callout,
  Card,
  CardBody,
  Skeleton,
  Spinner,
  cn,
} from "@golem/ui";
import {
  RiArrowLeftLine,
  RiCheckboxCircleFill,
  RiCloseCircleFill,
  RiLockLine,
} from "@remixicon/react";
import type { SetupStage, StartupSetupStatus } from "../lib/types";

const DEFAULT_HTTP_PORT = 80;
const DEFAULT_HTTPS_PORT = 443;
const DEFAULT_VM_PORT_RANGE_START = 50800;
const DEFAULT_VM_PORT_RANGE_END = 50900;

export function LoadingGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Card key={index}>
          <CardBody className="space-y-4">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-8 w-36" />
            <Skeleton className="h-4 w-24" />
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

export function ServiceStopped({
  error,
  busy,
  setupStatus,
  exiting = false,
  onStart,
}: {
  error: string | null;
  busy: boolean;
  setupStatus: StartupSetupStatus | null;
  exiting?: boolean;
  onStart: () => void;
}) {
  const setupFailed = setupStatus?.stages.some((stage) => stage.state === "failed");
  const startupVisible = Boolean(busy || setupStatus);

  if (startupVisible) {
    return (
      <ProviderStartupScreen
        error={error}
        setupFailed={setupFailed ?? false}
        status={setupStatus ?? startingStartupStatus()}
        busy={busy}
        exiting={exiting}
        onStart={onStart}
      />
    );
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-5 px-6">
      <ProviderMark className="justify-start" />
      <div>
        <h1 className="text-2xl font-semibold text-text-primary">Golem Provider</h1>
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          Start the provider service to load dashboard data.
        </p>
      </div>
      {error ? (
        <Callout tone="danger">
          {setupFailed ? "Secure setup stopped" : "Provider command failed"}: {error}
        </Callout>
      ) : null}
      <Button busy={busy} onClick={onStart}>
        Start Provider
      </Button>
    </div>
  );
}

function ProviderStartupScreen({
  status,
  error,
  setupFailed,
  busy,
  exiting,
  onStart,
}: {
  status: StartupSetupStatus;
  error: string | null;
  setupFailed: boolean;
  busy: boolean;
  exiting: boolean;
  onStart: () => void;
}) {
  const visibleStages = startupVisibleStages(status);
  const failed = visibleStages.some((stage) => stage.state === "failed");
  const portForwardingFailed = visibleStages.some(
    (stage) =>
      stage.state === "failed" &&
      (stage.name === "api_port_forwarding" || stage.name === "vm_port_range"),
  );
  const complete =
    visibleStages.length > 0 && visibleStages.every((stage) => stage.state === "success");
  const startupError = error ?? (failed ? status.error ?? status.message ?? null : null);
  const [showPortForwardingGuide, setShowPortForwardingGuide] = React.useState(false);

  React.useEffect(() => {
    if (!portForwardingFailed) {
      setShowPortForwardingGuide(false);
    }
  }, [portForwardingFailed]);

  if (portForwardingFailed && showPortForwardingGuide) {
    return (
      <PortForwardingGuideScreen
        status={status}
        busy={busy}
        onRetry={onStart}
        onBack={() => setShowPortForwardingGuide(false)}
      />
    );
  }

  return (
    <div
      className={cn(
        "provider-startup-screen flex min-h-screen items-center justify-center px-6 py-12",
        exiting ? "provider-startup-screen--exit" : null,
      )}
    >
      <Card className="provider-startup-card w-full max-w-3xl overflow-hidden">
        <CardBody className="px-8 py-8 sm:px-12 sm:py-10">
          <div className="flex flex-col items-center text-center">
            <ProviderMark />
            <h1 className="mt-8 text-3xl font-semibold tracking-normal text-text-primary">
              {failed
                ? startupFailureTitle(visibleStages)
                : complete
                  ? "SSL setup complete"
                  : "Starting Golem Provider"}
            </h1>
            <p className="mt-3 max-w-md text-sm leading-6 text-text-secondary">
              Preparing secure provider access so you can rent out machines to requestors.
            </p>
          </div>

          <div className="mt-8 space-y-3">
            <StartupSteps
              stages={visibleStages}
              onReadPortForwarding={() => setShowPortForwardingGuide(true)}
            />
          </div>

          {startupError ? (
            <Callout tone="danger" className="mt-5">
              {startupFailureSummary(visibleStages, setupFailed)}: {startupError}
            </Callout>
          ) : null}

          <div className="mt-6 border-t border-border pt-5">
            <div className="flex items-center gap-4 text-left">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-primary-soft text-text-secondary">
                <RiLockLine className="h-5 w-5" aria-hidden />
              </span>
              <p className="text-sm leading-6 text-text-secondary">
                Golem Provider uses ACME IP certificates for SSL.
                <br />
                Your HTTPS endpoint URL appears when the certificate is ready.
              </p>
            </div>
            {failed ? (
              <div className="mt-5 flex justify-end">
                <Button busy={busy} onClick={onStart}>
                  Try Again
                </Button>
              </div>
            ) : null}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function PortForwardingGuideScreen({
  status,
  busy,
  onRetry,
  onBack,
}: {
  status: StartupSetupStatus;
  busy: boolean;
  onRetry: () => void;
  onBack: () => void;
}) {
  const ports = startupPortConfig(status);
  return (
    <div className="provider-portforward-screen min-h-screen bg-background px-8 py-8 sm:px-12 lg:px-14">
      <div className="grid min-h-[calc(100vh-4rem)] items-center gap-10 lg:grid-cols-[0.72fr_1.28fr]">
        <div className="max-w-xl">
          <ProviderMark className="justify-start" />
          <h1 className="mt-14 text-4xl font-semibold leading-tight tracking-normal text-text-primary sm:text-5xl">
            Portforwarding setup
          </h1>
          <p className="mt-8 text-base leading-7 text-text-secondary">
            The Golem Provider requires you to portforward port {ports.http} and{" "}
            {ports.https} in order for the REST API to be publicly available for
            requestors. Furthermore you must also portforward the port range{" "}
            {ports.vmStart}-{ports.vmEnd} so that requestors can access the VM they rent
            from you.
          </p>

          <div className="mt-12 flex flex-col gap-3 sm:flex-row">
            <Button busy={busy} onClick={onRetry} className="sm:min-w-64">
              I've configured my router
            </Button>
            <Button variant="secondary" onClick={onBack} className="sm:min-w-36">
              <RiArrowLeftLine className="h-4 w-4" aria-hidden />
              Back
            </Button>
          </div>
        </div>

        <div className="flex min-h-[560px] min-w-0 items-center justify-center">
          <img
            src="/startup_ill.png"
            alt=""
            className="h-auto max-h-[calc(100vh-6rem)] w-full max-w-5xl object-contain"
            draggable={false}
          />
        </div>
      </div>
    </div>
  );
}

function StartupSteps({
  stages,
  onReadPortForwarding,
}: {
  stages: SetupStage[];
  onReadPortForwarding: () => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface px-4 py-5 shadow-sm sm:px-6">
      <div className="space-y-0">
        {stages.map((stage, index) => (
          <SetupStageRow
            key={stage.name}
            stage={stage}
            index={index}
            isLast={index === stages.length - 1}
            onReadPortForwarding={onReadPortForwarding}
          />
        ))}
      </div>
    </div>
  );
}

function ProviderMark({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-3", className ?? "justify-center")}>
      <GolemCubeMark />
      <span className="text-xl font-semibold text-text-primary">Golem Provider</span>
    </div>
  );
}

function GolemCubeMark() {
  return (
    <span className="relative grid h-10 w-10 place-items-center text-primary" aria-hidden>
      <span className="absolute h-7 w-7 rotate-[30deg] rounded-sm border-4 border-current" />
      <span className="absolute h-5 w-5 -translate-y-1 rotate-[30deg] rounded-sm border-l-4 border-t-4 border-current" />
    </span>
  );
}

function startingStartupStatus(): StartupSetupStatus {
  return {
    message: "Preparing secure connection before the provider starts.",
    api_http_public_port: DEFAULT_HTTP_PORT,
    api_https_public_port: DEFAULT_HTTPS_PORT,
    vm_port_range_start: DEFAULT_VM_PORT_RANGE_START,
    vm_port_range_end: DEFAULT_VM_PORT_RANGE_END,
    stages: [
      {
        name: "host_requirements",
        state: "running",
        label: "Checking host requirements",
        detail: "starting Multipass checks",
      },
      { name: "public_ip", state: "pending", label: "Public IP detected", detail: "" },
      {
        name: "network_access",
        state: "pending",
        label: "Ports 80 and 443 available",
        detail: "",
      },
      { name: "certificate", state: "pending", label: "Checking certificate", detail: "" },
      {
        name: "https_verification",
        state: "pending",
        label: "Secure endpoint verified",
        detail: "",
      },
      {
        name: "vm_port_range",
        state: "pending",
        label: "VM ports 50800-50900 reachable",
        detail: "",
      },
      {
        name: "provider_start",
        state: "pending",
        label: "Provider service started",
        detail: "",
      },
    ],
  };
}

export function isStartupSetupComplete(status: StartupSetupStatus): boolean {
  const visibleStages = startupVisibleStages(status);
  return visibleStages.length > 0 && visibleStages.every((stage) => stage.state === "success");
}

function startupVisibleStages(status: StartupSetupStatus): SetupStage[] {
  return [
    hostRequirementsStage(status.stages),
    apiPortForwardingStage(status),
    certificateStage(status.stages),
    secureEndpointStage(status.stages),
    vmPortRangeStage(status),
    providerStartStage(status.stages),
  ];
}

function hostRequirementsStage(stages: SetupStage[]): SetupStage {
  const stage = findStage(stages, "host_requirements");
  if (!stage) {
    return {
      name: "host_requirements",
      state: "success",
      label: "Checking host requirements",
      detail: "ready",
    };
  }

  return {
    ...stage,
    label:
      stage.state === "failed"
        ? "Host requirements need attention"
        : "Checking host requirements",
  };
}

function apiPortForwardingStage(status: StartupSetupStatus): SetupStage {
  const stages = status.stages;
  const ports = startupPortConfig(status);
  const publicIp = findStage(stages, "public_ip");
  const networkAccess = findStage(stages, "network_access");
  const sources = [publicIp, networkAccess].filter(Boolean) as SetupStage[];
  const failed = sources.find((stage) => stage.state === "failed");
  const base = failed ?? networkAccess ?? publicIp;

  if (failed) {
    return {
      ...failed,
      name: "api_port_forwarding",
      label: networkAccessFailureLabel(failed),
      detail: failed.detail || "blocked",
      port_checks: apiPortChecks(status, failed),
    };
  }

  const running = [publicIp, networkAccess].find(
    (stage) => stage?.state === "running",
  );
  if (running) {
    return {
      ...running,
      name: "api_port_forwarding",
      label: `Verifying ports ${ports.http} and ${ports.https} for API server`,
      detail: "checking",
      port_checks: apiPortChecks(status, running),
    };
  }

  if (networkAccess?.state === "success") {
    return {
      ...networkAccess,
      name: "api_port_forwarding",
      label: `Verifying ports ${ports.http} and ${ports.https} for API server`,
      detail: networkAccess.detail === "skipped" ? "skipped" : "ready",
      port_checks: apiPortChecks(status, networkAccess),
    };
  }

  return {
    name: "api_port_forwarding",
    state: base?.state ?? "pending",
    label: `Verifying ports ${ports.http} and ${ports.https} for API server`,
    detail: base?.detail || "waiting",
    remediation: base?.remediation,
    port_checks: apiPortChecks(status, base),
  };
}

function certificateStage(stages: SetupStage[]): SetupStage {
  const certificate = findStage(stages, "certificate");
  if (!certificate) {
    return {
      name: "certificate",
      state: "pending",
      label: "Checking certificate",
      detail: "waiting",
    };
  }

  return {
    ...certificate,
    label: certificateStageLabel(certificate),
  };
}

function secureEndpointStage(stages: SetupStage[]): SetupStage {
  const stage = findStage(stages, "https_verification");
  if (!stage) {
    return {
      name: "https_verification",
      state: "pending",
      label: "Verifying HTTPS endpoint",
      detail: "waiting",
    };
  }

  return {
    ...stage,
    label: secureEndpointStageLabel(stage),
  };
}

function vmPortRangeStage(status: StartupSetupStatus): SetupStage {
  const ports = startupPortConfig(status);
  const stage = findStage(status.stages, "vm_port_range");

  return {
    name: "vm_port_range",
    state: stage?.state ?? "pending",
    label: `Verifying VM ports ${ports.vmStart}-${ports.vmEnd}`,
    detail: stage?.detail || "waiting",
    remediation: stage?.remediation,
    port_checks: vmPortChecks(status, stage),
  };
}

function providerStartStage(stages: SetupStage[]): SetupStage {
  const stage = findStage(stages, "provider_start");
  if (!stage) {
    return {
      name: "provider_start",
      state: "pending",
      label: "Starting provider service",
      detail: "waiting",
    };
  }

  return {
    ...stage,
    label: providerStartStageLabel(stage),
  };
}

function apiPortChecks(status: StartupSetupStatus, stage?: SetupStage) {
  if (stage?.port_checks?.length) {
    return stage.port_checks;
  }
  const ports = startupPortConfig(status);
  return [
    { port: ports.http, state: "pending" as const },
    { port: ports.https, state: "pending" as const },
  ];
}

function vmPortChecks(status: StartupSetupStatus, stage?: SetupStage) {
  if (stage?.port_checks?.length) {
    return stage.port_checks;
  }
  const ports = startupPortConfig(status);
  return Array.from({ length: ports.vmEnd - ports.vmStart + 1 }, (_, index) => ({
    port: ports.vmStart + index,
    state: "pending" as const,
  }));
}

function startupPortConfig(status: StartupSetupStatus) {
  return {
    http: status.api_http_public_port ?? DEFAULT_HTTP_PORT,
    https: status.api_https_public_port ?? DEFAULT_HTTPS_PORT,
    vmStart: status.vm_port_range_start ?? DEFAULT_VM_PORT_RANGE_START,
    vmEnd: status.vm_port_range_end ?? DEFAULT_VM_PORT_RANGE_END,
  };
}

function formatPortRanges(ports: number[]): string {
  if (ports.length === 0) return "";
  const sortedPorts = Array.from(new Set(ports)).sort((a, b) => a - b);
  const ranges: string[] = [];
  let start = sortedPorts[0];
  let previous = sortedPorts[0];

  for (const port of sortedPorts.slice(1)) {
    if (port === previous + 1) {
      previous = port;
      continue;
    }
    ranges.push(formatPortRange(start, previous));
    start = port;
    previous = port;
  }

  ranges.push(formatPortRange(start, previous));
  return ranges.join(", ");
}

function formatPortRange(start: number, end: number): string {
  return start === end ? String(start) : `${start}-${end}`;
}

function networkAccessFailureLabel(stage: SetupStage): string {
  if (stage.name === "public_ip") {
    return "Public IP could not be detected";
  }

  if (stage.detail.startsWith("port unavailable")) {
    return "API ports are not reachable";
  }

  return "Ports 80 or 443 are not publicly available";
}

function certificateStageLabel(stage: SetupStage): string {
  if (stage.state === "running" && stage.detail === "requesting") {
    return "Acquiring certificate";
  }

  if (stage.state === "failed") {
    return "Certificate setup failed";
  }

  if (stage.state === "success") {
    return stage.detail === "skipped" ? "Certificate skipped" : "Certificate ready";
  }

  return "Checking certificate";
}

function secureEndpointStageLabel(stage: SetupStage): string {
  if (stage.state === "failed") {
    return "HTTPS endpoint verification failed";
  }

  if (stage.state === "success") {
    return "HTTPS endpoint verified";
  }

  return "Verifying HTTPS endpoint";
}

function providerStartStageLabel(stage: SetupStage): string {
  if (stage.state === "failed") {
    return "Provider service failed to start";
  }

  if (stage.state === "success") {
    return "Provider service started";
  }

  return "Starting provider service";
}

function startupFailureTitle(stages: SetupStage[]): string {
  const failedStage = stages.find((stage) => stage.state === "failed");
  if (failedStage?.name === "provider_start") {
    return "Provider service failed to start";
  }
  return "SSL setup needs attention";
}

function startupFailureSummary(
  stages: SetupStage[],
  setupFailed: boolean,
): string {
  const failedStage = stages.find((stage) => stage.state === "failed");
  if (failedStage?.name === "provider_start") {
    return "Provider service failed";
  }
  return setupFailed ? "SSL setup stopped" : "Provider command failed";
}

function findStage(stages: SetupStage[], name: string): SetupStage | undefined {
  return stages.find((stage) => stage.name === name);
}

function SetupStageRow({
  stage,
  index,
  isLast,
  onReadPortForwarding,
}: {
  stage: SetupStage;
  index: number;
  isLast: boolean;
  onReadPortForwarding: () => void;
}) {
  const active = stage.state === "running";
  const blocked = stage.state === "failed";
  const done = stage.state === "success";
  const detail = stageDetailText(stage);
  const showPortForwardingLink =
    blocked &&
    (stage.name === "api_port_forwarding" || stage.name === "vm_port_range");
  return (
    <div
      data-state={stage.state}
      className={cn(
        "provider-startup-step grid grid-cols-[auto_minmax(0,1fr)_auto] gap-3 transition-all duration-500 sm:gap-5",
        !isLast ? "pb-4" : null,
      )}
      style={{
        animationDelay: `${index * 45}ms`,
        transitionDelay: `${index * 45}ms`,
      }}
    >
      <div className="relative flex justify-center">
        <span
          className={cn(
            "z-10 grid h-8 w-8 place-items-center rounded-full border text-sm font-semibold transition-all duration-300",
            done ? "border-primary bg-primary text-white shadow-soft" : null,
            active ? "scale-105 border-primary bg-surface text-primary shadow-soft" : null,
            blocked ? "border-danger bg-danger text-white shadow-soft" : null,
            stage.state === "pending" ? "border-border-strong bg-surface text-text-primary" : null,
          )}
        >
          {done ? (
            <RiCheckboxCircleFill className="h-4 w-4" aria-hidden />
          ) : blocked ? (
            <RiCloseCircleFill className="h-4 w-4" aria-hidden />
          ) : (
            index + 1
          )}
        </span>
        {!isLast ? (
          <span
            className={cn(
              "absolute top-8 h-full w-px transition-colors duration-500",
              done ? "bg-primary" : "bg-border",
            )}
            aria-hidden
          />
        ) : null}
      </div>

      <div
        className={cn(
          "min-w-0 border-b border-dashed border-border pb-4 transition-colors duration-300",
          isLast ? "border-b-0 pb-0" : null,
        )}
      >
        <div className="truncate text-sm font-semibold text-text-primary sm:text-base">
          {stage.label}
        </div>
        {detail ? (
          <div className="mt-1 min-w-0 text-sm leading-5 text-text-secondary">
            {detail}
          </div>
        ) : null}
        {showPortForwardingLink ? (
          <button
            type="button"
            onClick={onReadPortForwarding}
            className="mt-1 text-left text-sm font-medium leading-5 text-blue-text transition-colors hover:text-primary-hover focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
          >
            Read more about port forwarding
          </button>
        ) : null}
        {stage.port_checks?.length ? <PortCheckStrip stage={stage} /> : null}
        {stage.remediation ? (
          <div className="mt-1 text-sm leading-5 text-text-secondary">{stage.remediation}</div>
        ) : null}
      </div>

      <div
        className={cn(
          "flex justify-end border-b border-dashed border-border pb-4 transition-colors duration-300",
          isLast ? "border-b-0 pb-0" : null,
        )}
      >
        <span className="grid h-6 w-6 place-items-center">
          {active ? (
            <Spinner className="h-5 w-5 text-primary" />
          ) : blocked ? (
            <RiCloseCircleFill className="h-5 w-5 text-danger" aria-label="failed" />
          ) : done ? (
            <RiCheckboxCircleFill className="h-5 w-5 text-success" aria-label="complete" />
          ) : (
            <span
              className="h-3 w-3 rounded-full border border-border-strong bg-surface"
              aria-label="pending"
            />
          )}
        </span>
      </div>
    </div>
  );
}

function stageDetailText(stage: SetupStage): string | null {
  const detail = stage.detail.trim();
  if (!detail || GENERIC_STAGE_DETAILS.has(detail)) {
    return null;
  }
  return detail;
}

const GENERIC_STAGE_DETAILS = new Set([
  "checking",
  "ready",
  "skipped",
  "started",
  "starting",
  "waiting",
]);

function PortCheckStrip({ stage }: { stage: SetupStage }) {
  const failedPorts = stage.port_checks
    ?.filter((check) => check.state === "closed")
    .map((check) => check.port);
  const failedSummary = failedPorts?.length ? formatPortRanges(failedPorts) : null;

  return (
    <div className="mt-2">
      <div className="flex max-w-full flex-wrap gap-1" aria-label="Port check status">
        {stage.port_checks?.map((check) => (
          <span
            key={check.port}
            title={`Port ${check.port}: ${check.state}`}
            aria-label={`Port ${check.port} ${check.state}`}
            className={cn(
              "h-2 w-2 border transition-colors duration-300",
              check.state === "pending" ? "border-border-strong bg-surface-muted" : null,
              check.state === "checking"
                ? "animate-pulse border-primary bg-primary"
                : null,
              check.state === "open" ? "border-success bg-success" : null,
              check.state === "closed" ? "border-danger bg-danger" : null,
            )}
          />
        ))}
      </div>
      {failedSummary ? (
        <div className="mt-2 text-sm font-medium leading-5 text-danger">
          Failed ports: {failedSummary}
        </div>
      ) : null}
    </div>
  );
}

export function EndpointErrors({ errors }: { errors: Record<string, string> }) {
  const entries = Object.entries(errors);
  if (entries.length === 0) return null;
  return (
    <Callout tone="warning">
      Some provider endpoints could not be loaded:{" "}
      {entries.map(([name, message]) => `${name}: ${message}`).join("; ")}
    </Callout>
  );
}

export function EmptyPanel({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted px-4 py-8 text-center">
      <p className="font-medium text-text-primary">{title}</p>
      {detail ? <p className="mt-1 text-sm text-text-secondary">{detail}</p> : null}
    </div>
  );
}
