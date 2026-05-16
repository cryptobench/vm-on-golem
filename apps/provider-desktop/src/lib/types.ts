export type ProviderServiceStatus = {
  running: boolean;
  apiBaseUrl: string;
};

export type SetupStageState = "pending" | "running" | "success" | "failed";
export type PortCheckState = "pending" | "checking" | "open" | "closed";

export type PortCheck = {
  port: number;
  state: PortCheckState;
};

export type SetupStage = {
  name: string;
  state: SetupStageState;
  label: string;
  detail: string;
  remediation?: string | null;
  port_checks?: PortCheck[];
};

export type StartupSetupStatus = {
  stages: SetupStage[];
  endpoint_url?: string | null;
  api_http_public_port?: number | null;
  api_https_public_port?: number | null;
  vm_port_range_start?: number | null;
  vm_port_range_end?: number | null;
  message?: string;
  error?: string;
};

export type ProviderInfo = {
  provider_id: string;
  stream_payment_address: string;
  glm_token_address: string;
  eth_token_address: string;
  ip_address: string | null;
  endpoint_url: string | null;
  country: string | null;
  platform: string | null;
};

export type ProviderSummary = {
  status: string;
  resources: {
    total?: Partial<VMResources>;
    available?: Partial<VMResources>;
    total_resources?: Partial<VMResources>;
    available_resources?: Partial<VMResources>;
    detected?: Partial<VMResources>;
    allocated?: Partial<VMResources>;
    [key: string]: unknown;
  };
  pricing: Record<string, number | string | null | undefined>;
  vms: Array<Record<string, unknown>>;
  env: {
    environment?: string;
    network?: string;
    [key: string]: unknown;
  };
};

export type ProviderPricingSettings = {
  usd_per_core_month: number;
  usd_per_gb_ram_month: number;
  usd_per_gb_storage_month: number;
  glm_per_core_month: number;
  glm_per_gb_ram_month: number;
  glm_per_gb_storage_month: number;
  warning: string | null;
};

export type ProviderSettings = {
  detected_resources: VMResources;
  offered_resources: VMResources;
  allocated_resources: VMResources;
  available_resources: VMResources;
  minimum_configurable_resources: VMResources;
  pricing: ProviderPricingSettings;
};

export type UpdateProviderResources = VMResources;

export type UpdateProviderPricing = Pick<
  ProviderPricingSettings,
  | "usd_per_core_month"
  | "usd_per_gb_ram_month"
  | "usd_per_gb_storage_month"
>;

export type VMStatus =
  | "creating"
  | "starting"
  | "restarting"
  | "running"
  | "delayed_shutdown"
  | "suspending"
  | "suspended"
  | "stopping"
  | "stopped"
  | "error"
  | "deleted"
  | "unknown";

export type VMResources = {
  cpu: number;
  memory: number;
  storage: number;
};

export type VMInfo = {
  id: string;
  name: string;
  status: VMStatus;
  resources: VMResources;
  ip_address: string | null;
  ssh_port: number | null;
  lifecycle_stage: string;
  status_message: string;
  progress: number;
  transitioning: boolean;
  next_poll_seconds: number;
  created_at: string;
  updated_at: string;
  error_message: string | null;
};

export type VMAccessInfo = {
  ssh_host?: string;
  ssh_port?: number;
  ssh_user?: string;
  vm_id: string;
  multipass_name?: string;
  status?: VMStatus;
  lifecycle_stage?: string;
  status_message?: string;
  progress?: number;
  transitioning?: boolean;
  next_poll_seconds?: number;
};

export type StreamOnChain = {
  token: string;
  sender: string;
  recipient: string;
  startTime: number;
  stopTime: number;
  ratePerSecond: number;
  deposit: number;
  withdrawn: number;
  leaseId: string;
  termsHash: string;
};

export type StreamComputed = {
  now: number;
  remaining_seconds: number;
  vested_wei: number;
  withdrawable_wei: number;
};

export type StreamStatus = {
  vm_id: string;
  stream_id: number;
  chain: StreamOnChain;
  computed: StreamComputed;
  verified: boolean;
  reason: string;
  payment_state?: string;
};

export type MetricSample = {
  scope: "host" | "vm";
  source: "infrastructure" | "guest_agent";
  metric: string;
  value: number;
  unit: string;
  timestamp: string;
  vm_id: string | null;
};

export type MetricHistoryPoint = {
  scope: "host" | "vm";
  source: "infrastructure" | "guest_agent";
  vm_id: string | null;
  metric: string;
  unit: string;
  bucket_start: string;
  bucket_end: string;
  avg: number;
  min: number;
  max: number;
  count: number;
};

export type MetricsLatestResponse = {
  host: Record<string, unknown>;
  vms: Record<string, Record<string, unknown>>;
  generated_at: string;
};

export type MetricsHistoryResponse = {
  points: MetricHistoryPoint[];
  range: HistoryRange;
  resolution_seconds: number;
  generated_at: string;
};

export type MonitoringOverview = {
  status: string;
  host: Record<string, unknown>;
  vms: Array<Record<string, unknown>>;
  active_alerts: ActiveAlert[];
  last_sample_at: string | null;
};

export type ActiveAlert = {
  name: string;
  severity: string;
  metric: string;
  scope: string;
  vm_id?: string;
  value?: number;
  threshold?: number;
  message?: string;
  created_at?: string;
  [key: string]: unknown;
};

export type AlertRule = {
  id: number | null;
  name: string;
  metric: string;
  scope: "host" | "vm";
  source: "infrastructure" | "guest_agent";
  operator: string;
  threshold: number;
  duration_seconds: number;
  severity: string;
  enabled: boolean;
};

export type WebhookConfig = {
  id: number | null;
  name: string;
  url: string;
  enabled: boolean;
  service_type: "generic_json" | "discord" | "slack";
  events: WebhookEventType[];
  template: WebhookTemplate;
  last_status: "pending" | "success" | "failed" | null;
  last_http_status: number | null;
  last_error: string | null;
  last_delivered_at: string | null;
};

export type WebhookEventType =
  | "alert.fired"
  | "alert.resolved"
  | "vm.ready"
  | "vm.failed"
  | "vm.stopped"
  | "vm.deleted"
  | "payment.stream.lost";

export type WebhookTemplateField = {
  name: string;
  value: string;
};

export type WebhookTemplate = {
  title: string;
  message: string;
  color: string;
  fields: WebhookTemplateField[];
  footer: string;
};

export type WebhookDeliveryAttempt = {
  id: number | null;
  webhook_id: number;
  event_id: string;
  event_type: string;
  attempt: number;
  status: "pending" | "success" | "failed";
  http_status: number | null;
  error: string | null;
  attempted_at: string;
};

export type WebhookPreviewRequest = {
  service_type: WebhookConfig["service_type"];
  template: WebhookTemplate;
  event_type: WebhookEventType;
};

export type WebhookPreviewResponse = {
  service_type: WebhookConfig["service_type"];
  payload: Record<string, unknown>;
};

export type WebhookTestResponse = {
  ok: boolean;
  status: number | null;
  error: string | null;
  event_id: string | null;
  payload: Record<string, unknown> | null;
};

export type HistoryRange = "1h" | "6h" | "24h" | "7d" | "30d";
