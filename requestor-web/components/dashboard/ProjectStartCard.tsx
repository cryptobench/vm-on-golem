"use client";

import React from "react";
import { RiAddLine, RiMagicLine } from "@remixicon/react";

export function ProjectStartCard({ hasSelectedProject }: { hasSelectedProject: boolean }) {
  const openCreateProject = () => {
    window.dispatchEvent(new CustomEvent("requestor-open-new-project"));
  };
  const openProjectSwitcher = () => {
    window.dispatchEvent(new CustomEvent("requestor-open-project-switcher"));
  };
  const openCreateWizard = () => {
    window.dispatchEvent(new CustomEvent("requestor-open-create-wizard"));
  };

  return (
    <section className="rounded-lg border border-border bg-surface-soft p-4 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="hidden h-14 w-14 items-center justify-center rounded-lg bg-primary-soft text-primary sm:flex">
            <RiMagicLine className="h-8 w-8 opacity-80" aria-hidden />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text-primary">
              {hasSelectedProject ? "Add more capacity" : "Get started with Golem"}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              {hasSelectedProject
                ? "Rent another VM when this project needs more compute."
                : "Create or select a project to organize your VMs, streams, and spending."}
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {hasSelectedProject ? (
            <button className="btn btn-primary px-5" onClick={openCreateWizard} type="button">
              <RiAddLine className="h-5 w-5" aria-hidden />
              Rent a VM
            </button>
          ) : (
            <>
              <button className="btn btn-primary px-5" onClick={openCreateProject} type="button">
                <RiAddLine className="h-5 w-5" aria-hidden />
                Create project
              </button>
              <button className="btn btn-secondary px-5" onClick={openProjectSwitcher} type="button">
                Select existing project
              </button>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
