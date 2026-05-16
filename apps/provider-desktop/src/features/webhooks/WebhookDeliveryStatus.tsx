import { StatusBadge } from "@golem/ui";
import { EMPTY_VALUE, titleCase } from "../../lib/format";
import type { WebhookConfig } from "../../lib/types";

export function DeliveryStatus({ webhook }: { webhook: WebhookConfig }) {
  if (!webhook.last_status) {
    return <StatusBadge label={EMPTY_VALUE} tone="neutral" />;
  }

  return (
    <StatusBadge
      label={titleCase(webhook.last_status)}
      tone={
        webhook.last_status === "success"
          ? "success"
          : webhook.last_status === "pending"
            ? "warning"
            : "danger"
      }
    />
  );
}
