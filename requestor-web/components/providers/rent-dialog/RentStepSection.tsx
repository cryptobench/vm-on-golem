"use client";

import React from "react";

export function RentStepSection({
  title,
  description,
  size = "lg",
  children,
}: {
  title: string;
  description: string;
  size?: "md" | "lg";
  children: React.ReactNode;
}) {
  return (
    <section className={size === "md" ? "mx-auto max-w-2xl" : "mx-auto max-w-4xl"}>
      <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
      <p className="mt-2 text-sm text-text-secondary">{description}</p>
      {children}
    </section>
  );
}
