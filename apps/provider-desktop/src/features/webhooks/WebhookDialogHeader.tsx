import { RiCloseLine } from "@remixicon/react";

export function WebhookDialogHeader({
  editing,
  onClose,
}: {
  editing: boolean;
  onClose: () => void;
}) {
  return (
    <div className="flex shrink-0 items-start justify-between gap-4 px-8 pt-8">
      <div>
        <h2 className="text-2xl font-semibold text-text-primary">
          {editing ? "Edit webhook" : "Create webhook"}
        </h2>
        <p className="mt-2 text-sm text-text-secondary">
          Send automated notifications to your services when important events
          happen.
        </p>
      </div>
      <button
        type="button"
        className="grid h-10 w-10 place-items-center rounded-md text-text-secondary hover:bg-surface-muted hover:text-text-primary"
        onClick={onClose}
        aria-label="Close webhook dialog"
      >
        <RiCloseLine className="h-5 w-5" aria-hidden />
      </button>
    </div>
  );
}
