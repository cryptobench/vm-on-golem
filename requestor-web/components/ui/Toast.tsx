"use client";
import React from "react";

type ToastCtx = { show: (msg: string, timeoutMs?: number) => void };
const Ctx = React.createContext<ToastCtx>({ show: () => {} });

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = React.useState<string | null>(null);
  const [visible, setVisible] = React.useState(false);
  const timerRef = React.useRef<number | null>(null);

  const show = (msg: string, timeoutMs = 1400) => {
    setMessage(msg);
    setVisible(true);
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setVisible(false), timeoutMs);
  };

  React.useEffect(() => () => { if (timerRef.current) window.clearTimeout(timerRef.current); }, []);

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      <div
        className={
          "pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center transition-all " +
          (visible ? "opacity-100" : "opacity-0 translate-y-2")
        }
      >
        {message && (
          <div className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-800 shadow-lg">
            {message}
          </div>
        )}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() { return React.useContext(Ctx); }

