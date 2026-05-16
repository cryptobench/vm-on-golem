import { StatusBadge } from "@golem/ui";
import {
  RiCodeSSlashLine,
  RiDiscordLine,
  RiSlackLine,
} from "@remixicon/react";
import type { WebhookConfig } from "../../lib/types";
import { serviceLabel } from "./webhookUtils";

export function ServiceBadge({
  type,
}: {
  type: WebhookConfig["service_type"];
}) {
  const tone = type === "generic_json" ? "primary" : "neutral";
  return <StatusBadge label={serviceLabel(type)} tone={tone} />;
}

export function ServiceIcon({
  type,
}: {
  type: WebhookConfig["service_type"];
}) {
  const Icon =
    type === "slack"
      ? RiSlackLine
      : type === "discord"
        ? RiDiscordLine
        : RiCodeSSlashLine;

  return (
    <span className="inline-grid h-8 w-8 place-items-center rounded-full bg-primary-soft text-primary">
      <Icon className="h-5 w-5" aria-hidden />
    </span>
  );
}

export function ServiceCard({
  type,
  selected,
  onSelect,
}: {
  type: WebhookConfig["service_type"];
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={[
        "min-h-28 rounded-md border bg-surface p-4 text-left transition",
        "hover:border-border-strong hover:bg-surface-muted",
        selected ? "border-primary ring-1 ring-primary" : "border-border",
      ].join(" ")}
      onClick={onSelect}
    >
      <ServiceIcon type={type} />
      <div className="mt-3 font-semibold text-text-primary">
        {serviceLabel(type)}
      </div>
      <div className="mt-2 text-sm leading-6 text-text-secondary">
        {serviceDescription(type)}
      </div>
    </button>
  );
}

function serviceDescription(type: WebhookConfig["service_type"]) {
  if (type === "slack") return "Send to a Slack incoming webhook";
  if (type === "discord") return "Send to a Discord webhook";
  return "Send as generic JSON";
}
