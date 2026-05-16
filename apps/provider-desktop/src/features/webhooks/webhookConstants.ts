import {
  RiAlertLine,
  RiCheckboxCircleLine,
  RiComputerLine,
  RiDeleteBinLine,
  RiErrorWarningLine,
  RiWebhookLine,
} from "@remixicon/react";
import type {
  WebhookConfig,
  WebhookTemplateField,
} from "../../lib/types";
import type {
  DialogStep,
  ServiceFilter,
  StatusFilter,
  WebhookEventOption,
} from "./webhookTypes";

export const DIALOG_STEPS: Array<{ id: DialogStep; label: string }> = [
  { id: "basics", label: "Basics" },
  { id: "events", label: "Events" },
  { id: "review", label: "Review" },
];

export const WEBHOOK_EVENTS: WebhookEventOption[] = [
  {
    id: "alert.fired",
    label: "alert.fired",
    description: "An alert has been triggered",
    icon: RiAlertLine,
  },
  {
    id: "alert.resolved",
    label: "alert.resolved",
    description: "An alert has been resolved",
    icon: RiCheckboxCircleLine,
  },
  {
    id: "vm.ready",
    label: "vm.ready",
    description: "A VM is ready",
    icon: RiComputerLine,
  },
  {
    id: "vm.failed",
    label: "vm.failed",
    description: "A VM has failed",
    icon: RiErrorWarningLine,
  },
  {
    id: "vm.stopped",
    label: "vm.stopped",
    description: "A VM has been stopped",
    icon: RiComputerLine,
  },
  {
    id: "vm.deleted",
    label: "vm.deleted",
    description: "A VM has been deleted",
    icon: RiDeleteBinLine,
  },
  {
    id: "payment.stream.lost",
    label: "payment.stream.lost",
    description: "A payment stream was lost",
    icon: RiWebhookLine,
  },
];

export const SERVICE_FILTER_OPTIONS: Array<[ServiceFilter, string]> = [
  ["all", "All"],
  ["slack", "Slack"],
  ["discord", "Discord"],
  ["generic_json", "Generic JSON"],
];

export const STATUS_FILTER_OPTIONS: Array<[StatusFilter, string]> = [
  ["all", "All"],
  ["enabled", "Enabled"],
  ["disabled", "Disabled"],
  ["success", "Success"],
  ["failed", "Failed"],
  ["pending", "Pending"],
];

const DEFAULT_FIELDS: WebhookTemplateField[] = [
  { name: "Event", value: "{{event.type}}" },
  { name: "Resource", value: "{{resource.id}}" },
  { name: "Severity", value: "{{severity}}" },
];

export function createDefaultWebhook(): WebhookConfig {
  return {
    id: null,
    name: "Production alerts",
    url: "",
    enabled: true,
    service_type: "slack",
    events: ["alert.fired", "alert.resolved", "vm.ready", "vm.failed"],
    template: {
      title: "{{summary}}",
      message: "{{summary}}",
      color: "severity",
      fields: DEFAULT_FIELDS.map((field) => ({ ...field })),
      footer: "Golem Provider",
    },
    last_status: null,
    last_http_status: null,
    last_error: null,
    last_delivered_at: null,
  };
}
