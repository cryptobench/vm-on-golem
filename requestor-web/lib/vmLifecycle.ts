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

type LifecycleSource = {
  status?: string | null;
  lifecycle_stage?: string | null;
  status_message?: string | null;
  progress?: number | null;
  transitioning?: boolean | null;
  next_poll_seconds?: number | null;
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
  unknown: 0,
};

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

function normalizeStatus(status?: string | null) {
  const normalized = String(status || "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_");
  return normalized;
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
  if (status === "deleted" || status === "terminated") return "danger";
  if (status === "stopped" || status === "suspended") return "neutral";
  if (TRANSITIONAL_STATUSES.has(status)) return "warning";
  return "primary";
}

function titleCase(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
