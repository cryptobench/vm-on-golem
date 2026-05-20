"use client";
import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RiCopperCoinLine,
  RiDashboardLine,
  RiHardDrive2Line,
  RiRadioButtonLine,
  RiSettings3Line,
  RiWallet3Line,
} from "@remixicon/react";
import { Wallet } from "../Wallet";
import { useWallet } from "../../context/WalletContext";

function GolemMark() {
  return (
    <span className="relative h-10 w-8 text-primary" aria-hidden>
      <span className="absolute left-2 top-0 h-4 w-4 rounded-full border-2 border-current bg-surface" />
      <span className="absolute left-2 bottom-0 h-4 w-4 rounded-full border-2 border-current bg-surface" />
      <span className="absolute left-0 top-3 h-4 w-4 rounded-full border-2 border-current bg-surface" />
    </span>
  );
}

function WalletSummary() {
  const { isConnected, account } = useWallet();
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="flex items-center gap-3">
        <RiWallet3Line className="h-5 w-5 text-text-secondary" aria-hidden />
        <div className="min-w-0">
          <div className="text-xs text-text-secondary">Wallet</div>
          <div className={isConnected ? "truncate text-xs font-medium text-text-primary" : "text-xs font-medium text-danger"}>
            {isConnected && account ? `${account.slice(0, 6)}...${account.slice(-4)}` : "Not connected"}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const nav = [
    { href: "/", label: "Dashboard", Icon: RiDashboardLine },
    { href: "/providers", label: "Providers", Icon: RiRadioButtonLine },
    { href: "/rentals", label: "My VMs", Icon: RiHardDrive2Line },
    { href: "/streams", label: "Streams", Icon: RiRadioButtonLine },
    { href: "/funding", label: "Funding", Icon: RiCopperCoinLine },
    { href: "/settings", label: "Settings", Icon: RiSettings3Line },
  ];
  return (
    <aside className="hidden min-h-screen w-sidebar flex-col border-r border-border bg-surface lg:flex">
      <div className="px-5 py-8">
        <Link href="/" className="flex items-center gap-4">
          <GolemMark />
          <div className="text-lg font-semibold tracking-tight">Golem Requestor</div>
        </Link>
      </div>
      <nav className="flex-1 space-y-2 px-3">
        {nav.map((i) => {
          const active = pathname === i.href || pathname.startsWith(i.href + "/");
          const Icon = i.Icon;
          return (
            <Link
              key={i.href}
              href={i.href}
              className={
                "flex h-12 items-center gap-3 rounded-lg px-4 text-sm font-medium transition-colors " +
                (active
                  ? "bg-primary-soft text-primary"
                  : "text-text-secondary hover:bg-surface-muted")
              }
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden />
              {i.label}
            </Link>
          );
        })}
      </nav>
      <div className="space-y-4 border-t border-border p-4">
        <WalletSummary />
        <Wallet />
        <div className="pt-2 text-sm text-text-muted">
          <div className="mb-2 flex items-center gap-2 text-lg tracking-wider">golem <span className="text-xs tracking-normal">v0.9.4</span></div>
          <div className="flex items-center gap-2 text-xs">
            <span className="h-2 w-2 rounded-full bg-success" aria-hidden />
            All systems operational
          </div>
        </div>
      </div>
    </aside>
  );
}
