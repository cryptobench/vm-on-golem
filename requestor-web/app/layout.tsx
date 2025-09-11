"use client";
import React from "react";
import { AdsProvider } from "../context/AdsContext";
import { WalletProvider } from "../context/WalletContext";
import { ProjectsProvider } from "../context/ProjectsContext";
import "./globals.css";
import { Sidebar } from "../components/layout/Sidebar";
import { Topbar } from "../components/layout/Topbar";
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
        <WalletProvider>
          <AdsProvider>
            <ProjectsProvider>
            <div className="min-h-screen w-full grid grid-cols-1 lg:grid-cols-[16rem_1fr]">
              <Sidebar />
              <div className="flex min-h-screen flex-col">
                <Topbar />
                <main className="p-4 sm:p-6 lg:p-8">
                  <div className="mx-auto w-full max-w-6xl">{children}</div>
                </main>
              </div>
            </div>
            </ProjectsProvider>
          </AdsProvider>
        </WalletProvider>
      </body>
    </html>
  );
}
