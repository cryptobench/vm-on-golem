"use client";
import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AdsProvider, useAds } from "../context/AdsContext";
import "./globals.css";
// Ensure Buffer is available in the browser for SDK dependencies
import { Buffer } from "buffer";
if (typeof window !== "undefined") {
  // @ts-ignore
  if (!(globalThis as any).Buffer) (globalThis as any).Buffer = Buffer;
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <AdsProvider>
          <div className="min-h-screen w-full grid grid-cols-1 lg:grid-cols-[16rem_1fr]">
            <Sidebar />
            <div className="flex min-h-screen flex-col">
              <Topbar />
              <main className="p-4 sm:p-6 lg:p-8">
                <div className="mx-auto w-full max-w-6xl">{children}</div>
              </main>
            </div>
          </div>
        </AdsProvider>
      </body>
    </html>
  );
}

function Sidebar() {
  const pathname = usePathname();
  const nav = [
    { href: "/", label: "Home" },
    { href: "/providers", label: "Providers" },
    { href: "/rentals", label: "Rentals" },
    { href: "/streams", label: "Streams" },
    { href: "/settings", label: "Settings" },
  ];
  return (
    <aside className="hidden lg:flex min-h-screen flex-col border-r bg-white/80 backdrop-blur">
      <div className="px-4 py-5 border-b">
        <Link href="/" className="flex items-center gap-2">
          <div className="size-8 rounded-xl bg-gradient-to-tr from-brand-600 to-brand-400" />
          <div className="font-semibold">Golem Requestor</div>
        </Link>
      </div>
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
              {i.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 text-xs text-gray-500">v0.1</div>
    </aside>
  );
}

function Topbar() {
  return (
    <header className="sticky top-0 z-20 w-full border-b bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2 lg:hidden">
          <div className="size-6 rounded-lg bg-gradient-to-tr from-brand-600 to-brand-400" />
          <span className="font-semibold">Golem Requestor</span>
        </div>
        <div />
      </div>
    </header>
  );
}
