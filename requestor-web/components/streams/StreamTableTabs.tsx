import Link from "next/link";
import { RiSettings3Line } from "@remixicon/react";
import { ToggleSwitch } from "@golem/ui";
import { cn } from "@golem/ui";

type StreamView = "active" | "ended";

type StreamTableTabsProps = {
  activeCount: number;
  endedCount: number;
  showEnded: boolean;
  view: StreamView;
  onShowEndedToggle: () => void;
  onViewChange: (view: StreamView) => void;
};

export function StreamTableTabs({
  activeCount,
  endedCount,
  showEnded,
  view,
  onShowEndedToggle,
  onViewChange,
}: StreamTableTabsProps) {
  return (
    <div className="flex flex-col gap-4 border-b border-border sm:flex-row sm:items-center sm:justify-between">
      <div className="flex">
        <TabButton
          active={view === "active"}
          label={`Active streams (${activeCount})`}
          onClick={() => onViewChange("active")}
        />
        {showEnded ? (
          <TabButton
            active={view === "ended"}
            label={`Ended streams (${endedCount})`}
            onClick={() => onViewChange("ended")}
          />
        ) : null}
      </div>
      <div className="flex items-center gap-4 px-4 pb-4 sm:px-5 sm:pb-0">
        <div className="inline-flex h-10 select-none items-center gap-3 text-sm font-medium text-text-secondary">
          <ToggleSwitch
            checked={showEnded}
            label="Show ended streams"
            onChange={onShowEndedToggle}
          />
          <span>Show ended streams</span>
        </div>
        <Link
          aria-label="Stream settings"
          className="btn btn-secondary w-10 px-0"
          href="/settings"
        >
          <RiSettings3Line className="h-5 w-5" aria-hidden />
        </Link>
      </div>
    </div>
  );
}

function TabButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "relative h-16 px-5 text-sm font-semibold transition",
        active ? "text-primary" : "text-text-secondary hover:text-text-primary",
      )}
      onClick={onClick}
      type="button"
    >
      {label}
      {active ? (
        <span
          aria-hidden
          className="absolute inset-x-0 bottom-0 h-0.5 rounded-md bg-primary"
        />
      ) : null}
    </button>
  );
}
