import React from "react";

export function SectionCard({
  title,
  eyebrow,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-border bg-surface p-4 ${className}`}>
      {eyebrow ? (
        <div className="text-xs font-medium text-text-secondary">{eyebrow}</div>
      ) : null}
      <h3 className="text-base font-semibold text-text-primary">{title}</h3>
      <div className="mt-4">{children}</div>
    </section>
  );
}
