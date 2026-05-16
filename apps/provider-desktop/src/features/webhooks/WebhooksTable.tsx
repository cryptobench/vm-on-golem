import { ActionMenu, Button, DataTable, ToggleSwitch } from "@golem/ui";
import { RiWebhookLine } from "@remixicon/react";
import type { WebhookConfig } from "../../lib/types";
import { DeliveryStatus } from "./WebhookDeliveryStatus";
import { ServiceBadge } from "./WebhookServiceVisuals";
import { relativeDelivery, summarizeEvents } from "./webhookUtils";

export function WebhooksTable({
  webhooks,
  pendingToggleIds,
  onToggle,
  onEdit,
  onTest,
  onDelete,
}: {
  webhooks: WebhookConfig[];
  pendingToggleIds: ReadonlySet<number>;
  onToggle: (webhook: WebhookConfig, enabled: boolean) => void;
  onEdit: (webhook: WebhookConfig) => void;
  onTest: (webhook: WebhookConfig) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <DataTable
        rows={webhooks}
        getRowKey={(webhook) => webhook.id ?? webhook.name}
        empty="No webhooks match the current filters"
        columns={[
          {
            key: "name",
            header: "Name",
            render: (webhook) => <WebhookIdentity webhook={webhook} />,
          },
          {
            key: "service",
            header: "Service type",
            render: (webhook) => <ServiceBadge type={webhook.service_type} />,
          },
          {
            key: "enabled",
            header: "Enabled",
            render: (webhook) => (
              <ToggleSwitch
                checked={webhook.enabled}
                onChange={(enabled) => onToggle(webhook, enabled)}
                disabled={
                  webhook.id == null || pendingToggleIds.has(webhook.id)
                }
                label={`${webhook.name} enabled`}
              />
            ),
          },
          {
            key: "events",
            header: "Events",
            render: (webhook) => <WebhookEventsSummary webhook={webhook} />,
          },
          {
            key: "status",
            header: "Last delivery",
            render: (webhook) => <DeliveryStatus webhook={webhook} />,
          },
          {
            key: "delivered",
            header: "Last delivered",
            render: (webhook) => relativeDelivery(webhook.last_delivered_at),
          },
          {
            key: "actions",
            header: "Actions",
            render: (webhook) => (
              <ActionMenu
                items={[
                  {
                    label: "Edit webhook",
                    onSelect: () => onEdit(webhook),
                  },
                  {
                    label: "Test webhook",
                    disabled: webhook.id == null,
                    onSelect: () => onTest(webhook),
                  },
                  {
                    label: "Delete webhook",
                    tone: "danger",
                    disabled: webhook.id == null,
                    onSelect: () => {
                      if (webhook.id != null) onDelete(webhook.id);
                    },
                  },
                ]}
              />
            ),
          },
        ]}
      />
      <TableFooter count={webhooks.length} />
    </div>
  );
}

function WebhookIdentity({ webhook }: { webhook: WebhookConfig }) {
  return (
    <div className="flex min-w-0 items-center gap-4 py-3">
      <div className="grid h-12 w-12 shrink-0 place-items-center rounded-md border border-border bg-surface">
        <RiWebhookLine className="h-6 w-6 text-text-secondary" aria-hidden />
      </div>
      <div className="min-w-0">
        <div className="font-semibold text-text-primary">{webhook.name}</div>
        <div className="mt-1 max-w-xs truncate text-sm text-text-secondary">
          {webhook.url}
        </div>
      </div>
    </div>
  );
}

function WebhookEventsSummary({ webhook }: { webhook: WebhookConfig }) {
  return (
    <div className="min-w-0">
      <div className="font-semibold text-text-primary">
        {webhook.events.length} events
      </div>
      <div className="mt-1 max-w-56 text-sm leading-6 text-text-secondary">
        {summarizeEvents(webhook.events)}
      </div>
    </div>
  );
}

function TableFooter({ count }: { count: number }) {
  return (
    <div className="flex items-center justify-between border-t border-border px-6 py-4 text-sm text-text-secondary">
      <span>
        Showing {count === 0 ? 0 : 1} to {count} of {count} webhooks
      </span>
      <div className="flex items-center gap-2">
        <Button variant="secondary" className="h-10 w-10 px-0" disabled>
          ‹
        </Button>
        <Button className="h-10 w-10 px-0">1</Button>
        <Button variant="secondary" className="h-10 w-10 px-0" disabled>
          ›
        </Button>
      </div>
    </div>
  );
}
