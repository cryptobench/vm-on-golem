"use client";

import React from "react";
import {
  RiArrowDownSLine,
  RiEyeFill,
  RiEyeOffFill,
  RiSearchLine,
} from "@remixicon/react";
import { cn } from "./cn";

const inputBaseClass = [
  "relative block w-full appearance-none rounded-md border px-2.5 py-2 shadow-sm outline-none transition sm:text-sm",
  "border-border bg-surface text-text-primary placeholder:text-text-muted",
  "disabled:border-border disabled:bg-surface-muted disabled:text-text-muted disabled:cursor-not-allowed",
  "focus:border-primary focus:ring-2 focus:ring-primary",
  "aria-invalid:border-danger aria-invalid:ring-2 aria-invalid:ring-danger",
  "[&::-webkit-search-cancel-button]:hidden [&::-webkit-search-decoration]:hidden",
].join(" ");

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  inputClassName?: string;
  hasError?: boolean;
  enableStepper?: boolean;
};

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      inputClassName,
      hasError,
      enableStepper = true,
      type,
      ...props
    },
    forwardedRef,
  ) => {
    const [typeState, setTypeState] = React.useState(type);
    const isPassword = type === "password";
    const isSearch = type === "search";

    React.useEffect(() => setTypeState(type), [type]);

    return (
      <div className={cn("relative w-full", className)}>
        <input
          ref={forwardedRef}
          type={isPassword ? typeState : type}
          aria-invalid={hasError || props["aria-invalid"] || undefined}
          className={cn(
            inputBaseClass,
            isSearch && "pl-8",
            isPassword && "pr-10",
            !enableStepper &&
              "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
            inputClassName,
          )}
          {...props}
        />
        {isSearch ? (
          <div className="pointer-events-none absolute bottom-0 left-2 flex h-full items-center justify-center text-text-muted">
            <RiSearchLine className="h-[1.125rem] w-[1.125rem] shrink-0" aria-hidden />
          </div>
        ) : null}
        {isPassword ? (
          <div className="absolute bottom-0 right-0 flex h-full items-center justify-center px-3">
            <button
              type="button"
              className="h-fit w-fit rounded-sm text-text-muted outline-none transition hover:text-text-secondary focus:ring-2 focus:ring-primary"
              aria-label="Change password visibility"
              onClick={() =>
                setTypeState(typeState === "password" ? "text" : "password")
              }
            >
              <span className="sr-only">
                {typeState === "password" ? "Show password" : "Hide password"}
              </span>
              {typeState === "password" ? (
                <RiEyeFill className="h-5 w-5 shrink-0" aria-hidden />
              ) : (
                <RiEyeOffFill className="h-5 w-5 shrink-0" aria-hidden />
              )}
            </button>
          </div>
        ) : null}
      </div>
    );
  },
);

Input.displayName = "Input";

export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  selectClassName?: string;
  hasError?: boolean;
};

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, selectClassName, hasError, children, ...props }, forwardedRef) => (
    <div className={cn("relative w-full", className)}>
      <select
        ref={forwardedRef}
        aria-invalid={hasError || props["aria-invalid"] || undefined}
        className={cn(inputBaseClass, "cursor-pointer pr-9", selectClassName)}
        {...props}
      >
        {children}
      </select>
      <RiArrowDownSLine
        className="pointer-events-none absolute right-2.5 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted"
        aria-hidden
      />
    </div>
  ),
);

Select.displayName = "Select";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  textareaClassName?: string;
  hasError?: boolean;
};

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, textareaClassName, hasError, ...props }, forwardedRef) => (
    <div className={cn("relative w-full", className)}>
      <textarea
        ref={forwardedRef}
        aria-invalid={hasError || props["aria-invalid"] || undefined}
        className={cn(inputBaseClass, "min-h-24 resize-y", textareaClassName)}
        {...props}
      />
    </div>
  ),
);

Textarea.displayName = "Textarea";
