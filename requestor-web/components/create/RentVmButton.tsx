"use client";

import React from "react";
import { RiAddLine } from "@remixicon/react";
import { cn } from "@golem/ui";

type RentVmButtonProps = {
  className?: string;
  variant?: "primary" | "secondary";
};

export function RentVmButton({
  className,
  variant = "primary",
}: RentVmButtonProps) {
  const openCreateWizard = () => {
    window.dispatchEvent(new CustomEvent("requestor-open-create-wizard"));
  };

  return (
    <button
      className={cn(
        "btn gap-2 px-5",
        variant === "primary"
          ? "btn-primary"
          : "btn-secondary text-primary ring-primary",
        className,
      )}
      onClick={openCreateWizard}
      type="button"
    >
      <RiAddLine className="h-5 w-5" aria-hidden />
      Rent a VM
    </button>
  );
}
