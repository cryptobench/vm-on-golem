"use client";
import React from "react";

// Lightweight wrapper around @metamask/logo that mounts a small fox head
// as a DOM node. Keeps it tiny for button/icon usage.
export function MetaMaskLogo({ size = 18, className = "" }: { size?: number; className?: string }) {
  const ref = React.useRef<HTMLSpanElement | null>(null);
  const viewerRef = React.useRef<any>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function mount() {
      try {
        const mod: any = await import("@metamask/logo");
        if (cancelled) return;
        const viewer = mod.default
          ? mod.default({ pxNotRatio: true, width: size, height: size, followMouse: false, slowDrift: false })
          : mod({ pxNotRatio: true, width: size, height: size, followMouse: false, slowDrift: false });
        viewerRef.current = viewer;
        if (ref.current) {
          ref.current.innerHTML = "";
          ref.current.appendChild(viewer.container);
        }
      } catch {
        // fail silently; icon is decorative
      }
    }
    mount();
    return () => {
      cancelled = true;
      try { viewerRef.current?.stopAnimation?.(); } catch {}
      if (ref.current) ref.current.innerHTML = "";
    };
  }, [size]);

  return <span ref={ref} className={className} aria-hidden />;
}

