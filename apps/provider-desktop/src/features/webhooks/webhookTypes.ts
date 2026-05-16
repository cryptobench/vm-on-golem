import type React from "react";
import type {
  WebhookConfig,
  WebhookEventType,
} from "../../lib/types";

export type DialogStep = "basics" | "events" | "review";

export type ServiceFilter = "all" | WebhookConfig["service_type"];

export type StatusFilter =
  | "all"
  | "enabled"
  | "disabled"
  | "success"
  | "failed"
  | "pending";

export type WebhookEventOption = {
  id: WebhookEventType;
  label: string;
  description: string;
  icon: React.ElementType;
};

export type WebhookFormSetter = React.Dispatch<
  React.SetStateAction<WebhookConfig>
>;
