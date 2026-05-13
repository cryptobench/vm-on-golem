"use client";

import React from "react";
import { cn } from "./cn";

export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={cn("card", className)}>{children}</section>;
}

export function CardBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("card-body", className)}>{children}</div>;
}

export function StatCard({
  label,
  value,
  detail,
  icon,
  tone = "primary",
  className,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  detail?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "primary" | "success" | "warning" | "danger" | "neutral";
  className?: string;
}) {
  const toneClass = {
    primary: "bg-primary-soft text-primary",
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    neutral: "bg-surface-muted text-text-secondary",
  }[tone];

  return (
    <Card className={className}>
      <CardBody className="flex min-h-28 items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-medium text-text-secondary">{label}</div>
          <div className="mt-3 text-2xl font-semibold text-text-primary">
            {value}
          </div>
          {detail ? (
            <div className="mt-3 text-sm text-text-secondary">{detail}</div>
          ) : null}
        </div>
        {icon ? (
          <span
            className={cn(
              "grid h-11 w-11 shrink-0 place-items-center rounded-lg",
              toneClass,
            )}
          >
            {icon}
          </span>
        ) : null}
      </CardBody>
    </Card>
  );
}
