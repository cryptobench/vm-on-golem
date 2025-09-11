"use client";
import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { IcDashboard, IcProviders, IcServers, IcStreams, IcSettings } from "../icons";

export function Sidebar() {
  const pathname = usePathname();
  const nav = [
    { href: "/", label: "Dashboard", Icon: IcDashboard },
    { href: "/providers", label: "Providers", Icon: IcProviders },
    { href: "/rentals", label: "Servers", Icon: IcServers },
    { href: "/streams", label: "Payment Streams", Icon: IcStreams },
    { href: "/settings", label: "Settings", Icon: IcSettings },
  ];
  return (
    <aside className="hidden lg:flex min-h-screen w-[16rem] flex-col border-r bg-white/80 backdrop-blur">
      <div className="px-4 py-5">
        <Link href="/" className="flex items-center gap-2">
          <div className="size-8 rounded-xl bg-gradient-to-tr from-brand-600 to-brand-400" />
          <div className="font-semibold">Golem Requestor</div>
        </Link>
      </div>
      <ProjectSwitcher />
      <nav className="flex-1 p-3 space-y-1">
        {nav.map((i) => {
          const active = pathname === i.href;
          return (
            <Link
              key={i.href}
              href={i.href}
              className={
                "block rounded-lg px-3 py-2 text-sm font-medium transition-colors " +
                (active
                  ? "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200"
                  : "text-gray-700 hover:bg-gray-50")
              }
            >
              <span className="inline-flex items-center gap-2">
                <i className="text-gray-500">{React.createElement(i.Icon)}</i>
                {i.label}
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="p-4 text-xs text-gray-500">v0.1</div>
    </aside>
  );
}
