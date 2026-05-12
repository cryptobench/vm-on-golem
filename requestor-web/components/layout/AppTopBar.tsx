"use client";

import React from "react";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { WalletStatusButton } from "./WalletStatusButton";
import { RentVmButton } from "../create/RentVmButton";

export function AppTopBar() {
  return (
    <header className="flex flex-col gap-4 px-4 py-4 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
      <ProjectSwitcher />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
        <WalletStatusButton />
        <RentVmButton className="sm:min-w-40" />
      </div>
    </header>
  );
}
