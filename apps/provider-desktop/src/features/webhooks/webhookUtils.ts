import { parseAbsoluteTimestamp } from "@golem/ui";
import { EMPTY_VALUE, formatDateTime, titleCase } from "../../lib/format";
import type {
  WebhookConfig,
  WebhookEventType,
} from "../../lib/types";
import type {
  ServiceFilter,
  StatusFilter,
} from "./webhookTypes";

export function serviceLabel(type: WebhookConfig["service_type"]) {
  return type === "generic_json" ? "Generic JSON" : titleCase(type);
}

export function summarizeEvents(events: WebhookEventType[]) {
  if (events.length === 0) return EMPTY_VALUE;
  return events.slice(0, 4).join(", ");
}

export function relativeDelivery(value: string | null | undefined) {
  if (!value) return EMPTY_VALUE;
  const timestamp = parseAbsoluteTimestamp(value);
  if (timestamp == null || !Number.isFinite(timestamp)) {
    return formatDateTime(value);
  }

  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "Just now";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;

  return formatDateTime(value);
}

export function filterWebhooks(
  webhooks: WebhookConfig[],
  search: string,
  serviceFilter: ServiceFilter,
  statusFilter: StatusFilter,
) {
  const query = search.trim().toLowerCase();

  return webhooks.filter((webhook) => {
    const matchesSearch =
      !query ||
      webhook.name.toLowerCase().includes(query) ||
      webhook.url.toLowerCase().includes(query);
    const matchesService =
      serviceFilter === "all" || webhook.service_type === serviceFilter;
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "enabled" && webhook.enabled) ||
      (statusFilter === "disabled" && !webhook.enabled) ||
      webhook.last_status === statusFilter;

    return matchesSearch && matchesService && matchesStatus;
  });
}

export function isValidWebhookUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed || /\s/.test(trimmed)) return false;

  try {
    const url = new URL(trimmed);
    return (url.protocol === "https:" || url.protocol === "http:") && Boolean(url.hostname);
  } catch {
    return false;
  }
}

export function toggleEvent(
  events: WebhookEventType[],
  eventType: WebhookEventType,
  checked: boolean,
) {
  if (checked) return Array.from(new Set([...events, eventType]));
  return events.filter((item) => item !== eventType);
}
