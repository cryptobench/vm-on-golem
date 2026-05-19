import type { WebhookEventOption } from "./webhookTypes";

export function EventCard({
  event,
  selected,
  onChange,
}: {
  event: WebhookEventOption;
  selected: boolean;
  onChange: (checked: boolean) => void;
}) {
  const Icon = event.icon;

  return (
    <label className="flex min-h-24 cursor-pointer gap-4 rounded-md border border-border bg-surface px-4 py-4 hover:bg-surface-muted">
      <input
        type="checkbox"
        className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
        checked={selected}
        onChange={(item) => onChange(item.target.checked)}
      />
      <Icon className="mt-0.5 h-5 w-5 shrink-0 text-text-secondary" aria-hidden />
      <span>
        <span className="block font-semibold text-text-primary">
          {event.label}
        </span>
        <span className="mt-2 block text-sm text-text-secondary">
          {event.description}
        </span>
      </span>
    </label>
  );
}
