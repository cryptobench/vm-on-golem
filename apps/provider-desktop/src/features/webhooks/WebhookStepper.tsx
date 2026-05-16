import { DIALOG_STEPS } from "./webhookConstants";
import type { DialogStep } from "./webhookTypes";

export function WebhookStepper({
  step,
  onStepChange,
}: {
  step: DialogStep;
  onStepChange: (step: DialogStep) => void;
}) {
  const activeIndex = DIALOG_STEPS.findIndex((item) => item.id === step);

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {DIALOG_STEPS.map((item, index) => {
        const active = item.id === step;
        const complete = index < activeIndex;

        return (
          <button
            key={item.id}
            type="button"
            className="flex items-center gap-3 text-left"
            onClick={() => onStepChange(item.id)}
          >
            <span
              className={[
                "grid h-8 w-8 shrink-0 place-items-center rounded-full",
                "border text-sm font-semibold",
                active
                  ? "border-primary bg-primary text-white"
                  : complete
                    ? "border-primary bg-primary-soft text-primary"
                    : "border-border-strong bg-surface text-text-secondary",
              ].join(" ")}
            >
              {index + 1}
            </span>
            <span
              className={[
                "min-w-0 text-sm font-semibold",
                active ? "text-text-primary" : "text-text-secondary",
              ].join(" ")}
            >
              {item.label}
            </span>
            {index < DIALOG_STEPS.length - 1 ? (
              <span className="hidden h-px flex-1 bg-border md:block" />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
