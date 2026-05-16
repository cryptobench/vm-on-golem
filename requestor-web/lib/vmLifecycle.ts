export type VmLifecycleTone =
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "primary";

export type VmLifecycleView = {
  status: string;
  stage: string;
  label: string;
  message: string;
  progress: number;
  transitioning: boolean;
  tone: VmLifecycleTone;
  nextPollMs: number;
};

export type LifecycleSource = {
  status?: string | null;
  lifecycle_stage?: string | null;
  status_message?: string | null;
  progress?: number | null;
  transitioning?: boolean | null;
  next_poll_seconds?: number | null;
};

export type VmDisplayLifecycleInput = {
  lifecycle?: LifecycleSource | null;
  fallback?: LifecycleSource | null;
  safeStatus?: unknown;
  statusError?: unknown;
  accessError?: unknown;
};

const TRANSITIONAL_STATUSES = new Set([
  "creating",
  "starting",
  "restarting",
  "delayed_shutdown",
  "suspending",
  "stopping",
]);

const READY_STAGES = new Set([
  "ready",
  "running",
  "stopped",
  "suspended",
  "deleted",
  "terminated",
  "offline",
  "failed",
  "error",
]);

const STATUS_LABELS: Record<string, string> = {
  creating: "Creating",
  starting: "Starting",
  restarting: "Restarting",
  running: "Online",
  delayed_shutdown: "Shutdown pending",
  suspending: "Suspending",
  suspended: "Suspended",
  stopping: "Stopping",
  stopped: "Stopped",
  error: "Error",
  failed: "Failed",
  deleted: "Deleted",
  terminated: "Terminated",
  offline: "Offline",
  unknown: "Checking",
};

const STATUS_MESSAGES: Record<string, string> = {
  creating: "Provisioning VM",
  starting: "Starting VM",
  restarting: "Restarting VM",
  running: "VM is online",
  delayed_shutdown: "Shutdown is scheduled",
  suspending: "Suspending VM",
  suspended: "VM is suspended",
  stopping: "Stopping VM",
  stopped: "VM is stopped",
  error: "VM requires attention",
  failed: "VM creation failed",
  deleted: "VM has been deleted",
  terminated: "VM has been terminated",
  offline: "Provider unreachable",
  unknown: "Checking provider status",
};

const STAGE_MESSAGES: Record<string, string> = {
  queued: "Queued VM creation",
  allocating_resources: "Reserving provider resources",
  preparing_guest: "Preparing guest configuration",
  launching: "Launching VM image",
  waiting_for_guest: "Waiting for VM to start",
  provisioning: "VM is being provisioned",
  configuring_access: "Configuring SSH access",
  ready: "VM is online",
  failed: "VM creation failed",
};

const PROGRESS_BY_STATUS: Record<string, number> = {
  creating: 15,
  starting: 60,
  restarting: 60,
  running: 100,
  delayed_shutdown: 70,
  suspending: 70,
  suspended: 100,
  stopping: 70,
  stopped: 100,
  error: 100,
  failed: 100,
  deleted: 100,
  terminated: 100,
  offline: 0,
  unknown: 0,
};

export function deriveVmDisplayLifecycle({
  lifecycle,
  fallback,
  safeStatus,
  statusError,
  accessError,
}: VmDisplayLifecycleInput): VmLifecycleView {
  if (
    isProviderUnreachable({
      safeStatus,
      statusError,
      accessError,
      lifecycle,
    })
  ) {
    const failureStatus = lastKnownFailureStatus(lifecycle, fallback);
    if (failureStatus) {
      return deriveVmLifecycle({
        status: failureStatus,
        lifecycle_stage: "failed",
        status_message:
          lifecycle?.status_message ||
          fallback?.status_message ||
          STATUS_MESSAGES[failureStatus],
        progress: lifecycle?.progress ?? fallback?.progress ?? 100,
        transitioning: false,
        next_poll_seconds: 8,
      });
    }

    const transitionalStatus = lastKnownTransitionalStatus(lifecycle, fallback);
    if (transitionalStatus) {
      return deriveVmLifecycle({
        status: transitionalStatus,
        lifecycle_stage: lastKnownLifecycleStage(lifecycle, fallback),
        status_message: STATUS_MESSAGES.offline,
        progress:
          lifecycle?.progress ??
          fallback?.progress ??
          PROGRESS_BY_STATUS[transitionalStatus],
        transitioning: true,
        next_poll_seconds: 8,
      });
    }

    return deriveVmLifecycle({
      status: "offline",
      lifecycle_stage: lastKnownLifecycleStage(lifecycle, fallback),
      status_message: STATUS_MESSAGES.offline,
      progress: 0,
      transitioning: false,
      next_poll_seconds: 8,
    });
  }

  return deriveVmLifecycle(lifecycle || {}, fallback);
}

export function deriveVmLifecycle(
  source: LifecycleSource,
  fallback?: LifecycleSource | null,
): VmLifecycleView {
  const fallbackStatus = normalizeStatus(fallback?.status);
  const sourceStatus = normalizeStatus(source.status);
  const status =
    sourceStatus === "unknown" && TRANSITIONAL_STATUSES.has(fallbackStatus)
      ? fallbackStatus
      : sourceStatus || fallbackStatus || "unknown";
  const stage = normalizeStage(
    source.lifecycle_stage || fallback?.lifecycle_stage || status,
  );
  const message =
    source.status_message ||
    fallback?.status_message ||
    STAGE_MESSAGES[stage] ||
    STATUS_MESSAGES[status] ||
    STATUS_MESSAGES.unknown;
  const progress = clampProgress(
    source.progress ?? fallback?.progress ?? PROGRESS_BY_STATUS[status] ?? 0,
  );
  const transitioning =
    Boolean(source.transitioning ?? fallback?.transitioning) ||
    TRANSITIONAL_STATUSES.has(status) ||
    (!READY_STAGES.has(stage) && status !== "unknown");
  const nextPollSeconds = Number(
    source.next_poll_seconds || fallback?.next_poll_seconds || 0,
  );

  return {
    status,
    stage,
    label: STATUS_LABELS[status] || titleCase(status),
    message,
    progress,
    transitioning,
    tone: toneForStatus(status),
    nextPollMs: Math.max(
      1000,
      (nextPollSeconds || (transitioning ? 2 : 8)) * 1000,
    ),
  };
}

export function isVmTransitioning(status?: string | null) {
  return TRANSITIONAL_STATUSES.has(normalizeStatus(status));
}

export function isProviderUnreachable({
  safeStatus,
  statusError,
  accessError,
  lifecycle,
}: Pick<
  VmDisplayLifecycleInput,
  "safeStatus" | "statusError" | "accessError" | "lifecycle"
>) {
  if (safeStatus && typeof safeStatus === "object" && "exists" in safeStatus) {
    const safe = safeStatus as { exists?: boolean; code?: number | string | null };
    if (safe.exists) return false;
    return Number(safe.code || 0) !== 404;
  }

  if (isReachabilityError(statusError)) return true;
  if (hasUsableLifecycleStatus(lifecycle)) return false;
  return isReachabilityError(accessError);
}

function normalizeStatus(status?: string | null) {
  const normalized = String(status || "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_");
  return normalized;
}

function hasUsableLifecycleStatus(source?: LifecycleSource | null) {
  const status = normalizeStatus(source?.status);
  return Boolean(status && status !== "unknown" && status !== "offline");
}

function isReachabilityError(error: unknown) {
  if (!error) return false;
  const status = Number((error as { status?: number | string } | null)?.status || 0);
  return status !== 404;
}

function lastKnownLifecycleStage(
  lifecycle?: LifecycleSource | null,
  fallback?: LifecycleSource | null,
) {
  return (
    lifecycle?.lifecycle_stage ||
    fallback?.lifecycle_stage ||
    lifecycle?.status ||
    fallback?.status ||
    "offline"
  );
}

function lastKnownTransitionalStatus(
  lifecycle?: LifecycleSource | null,
  fallback?: LifecycleSource | null,
) {
  const lifecycleStatus = normalizeStatus(lifecycle?.status);
  if (TRANSITIONAL_STATUSES.has(lifecycleStatus)) return lifecycleStatus;

  const fallbackStatus = normalizeStatus(fallback?.status);
  if (TRANSITIONAL_STATUSES.has(fallbackStatus)) return fallbackStatus;

  return null;
}

function lastKnownFailureStatus(
  lifecycle?: LifecycleSource | null,
  fallback?: LifecycleSource | null,
) {
  const lifecycleStatus = normalizeStatus(lifecycle?.status);
  if (lifecycleStatus === "failed" || lifecycleStatus === "error") {
    return lifecycleStatus;
  }

  const fallbackStatus = normalizeStatus(fallback?.status);
  if (fallbackStatus === "failed" || fallbackStatus === "error") {
    return fallbackStatus;
  }

  return null;
}

function normalizeStage(stage?: string | null) {
  return String(stage || "unknown")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_");
}

function clampProgress(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function toneForStatus(status: string): VmLifecycleTone {
  if (status === "running") return "success";
  if (status === "error" || status === "failed") return "danger";
  if (status === "deleted" || status === "terminated" || status === "offline") {
    return "danger";
  }
  if (status === "stopped" || status === "suspended") return "neutral";
  if (TRANSITIONAL_STATUSES.has(status)) return "primary";
  return "primary";
}

function titleCase(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
