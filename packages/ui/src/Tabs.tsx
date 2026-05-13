"use client";

import React from "react";
import { cn } from "./cn";

export type TabItem<T extends string> = {
  id: T;
  label: string;
};

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: Array<TabItem<T>>;
  active: T;
  onChange: (tab: T) => void;
}) {
  return (
    <div className="border-b border-border">
      <nav className="-mb-px flex flex-wrap gap-3 text-sm">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={cn(
              "whitespace-nowrap border-b-2 px-3 py-2",
              active === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-text-secondary hover:border-border-strong hover:text-text-primary",
            )}
            onClick={() => onChange(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
