"use client";

import React from "react";
import { cn } from "./cn";
import { Spinner } from "./Spinner";

type ButtonVariant = "primary" | "secondary" | "danger";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  busy?: boolean;
};

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  danger: "btn-danger",
};

export function Button({
  variant = "primary",
  busy = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      className={cn("btn gap-2", VARIANT_CLASS[variant], className)}
      disabled={disabled || busy}
      {...props}
    >
      {busy ? <Spinner className="h-4 w-4 text-current" /> : null}
      {children}
    </button>
  );
}
