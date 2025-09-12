"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { Card, Tracker } from "@tremor/react";
import { RiCheckboxCircleFill, RiErrorWarningFill, RiCloseCircleFill, RiTimeFill } from "@remixicon/react";
import { humanDuration } from "../../lib/streams";

export type StreamMeta = {
  tokenSymbol: string;
  tokenDecimals: number;
  usdPrice: number | null;
};

export type StreamCardProps = {
  title?: string;
  streamId?: string | number | null;
  chain: {
    token: string; recipient: string; ratePerSecond: bigint; deposit: bigint; withdrawn: bigint; halted: boolean;
  };
  remaining: number; // seconds
  meta: StreamMeta;
  displayCurrency: 'fiat' | 'token';
  onTopUp?: (seconds: number) => void;
  busy?: boolean;
  actionsRight?: React.ReactNode;
  detailsHref?: string;
};

export function StreamCard({ title, streamId, chain, remaining, meta, displayCurrency, onTopUp, busy, actionsRight, detailsHref }: StreamCardProps) {
  const router = useRouter();
  const [localRemaining, setLocalRemaining] = React.useState<number>(remaining);
  const dec = meta.tokenDecimals || 18;
  const rps = Number(chain.ratePerSecond) / 10 ** dec;
  const rph = rps * 3600;
  const dep = Number(chain.deposit) / 10 ** dec;
  const wid = Number(chain.withdrawn) / 10 ** dec;
  // For requestors, "balance" should reflect remaining budget (tokens left to pay),
  // not the provider's withdrawable amount. Compute from runway: rate * remaining seconds.
  const reqRemainingTok = Math.max(0, rps * localRemaining);

  const ratePerHour = (displayCurrency === 'fiat' && meta.usdPrice != null)
    ? `$${(rph * meta.usdPrice).toFixed(6)}/h`
    : `${rph.toFixed(6)} ${meta.tokenSymbol}/h`;
  const remStr = (displayCurrency === 'fiat' && meta.usdPrice != null)
    ? `$${(reqRemainingTok * meta.usdPrice).toFixed(2)}`
    : `${reqRemainingTok.toFixed(6)} ${meta.tokenSymbol}`;

  const outOfFunds = !chain.halted && (localRemaining <= 0 || reqRemainingTok <= 0);
  const needsTopUp = !chain.halted && !outOfFunds && remaining < 3600; // < 1h runway
  const accent = chain.halted ? 'bg-red-500' : outOfFunds ? 'bg-red-500' : needsTopUp ? 'bg-amber-500' : 'bg-emerald-500';
  const statusColor = chain.halted ? 'text-red-600' : outOfFunds ? 'text-red-600' : needsTopUp ? 'text-amber-600' : 'text-emerald-600';
  const StatusIcon = chain.halted ? RiCloseCircleFill : outOfFunds ? RiCloseCircleFill : needsTopUp ? RiErrorWarningFill : RiCheckboxCircleFill;
  const statusText = chain.halted ? 'Halted' : outOfFunds ? 'Out of funds' : needsTopUp ? 'Needs top-up' : 'Active';
  // Green/gray bars represent % RUNWAY time left
  const totalSegments = 60;
  const totalDurationSec = rps > 0 ? Math.max(1, Math.floor(dep / rps)) : 0; // seconds
  const pctRunway = totalDurationSec > 0 ? Math.max(0, Math.min(1, remaining / totalDurationSec)) : 0;
  const remainingSeg = (chain.halted || outOfFunds)
    ? 0
    : Math.min(totalSegments, Math.max(0, Math.floor(pctRunway * totalSegments)));
  const trackerData = [
    ...Array.from({ length: remainingSeg }, () => ({ color: 'emerald-500' })),
    ...Array.from({ length: totalSegments - remainingSeg }, () => ({ color: 'gray-300' })),
  ];

  // Keep local countdown even if parent doesn't tick
  React.useEffect(() => { setLocalRemaining(remaining); }, [remaining]);
  React.useEffect(() => {
    if (chain.halted) return;
    const t = setInterval(() => {
      setLocalRemaining((x) => (x > 0 ? x - 1 : 0));
    }, 1000);
    return () => clearInterval(t);
  }, [chain.halted]);

  // Custom human input for top-up like "1h30m", "45m"
  const [customInput, setCustomInput] = React.useState<string>("");
  function parseHumanTime(v: string): number | null {
    if (!v) return null;
    const t = v.trim().toLowerCase();
    if (!t) return null;
    if (/^\d+$/.test(t)) return parseInt(t, 10) * 60; // minutes default
    let seconds = 0; const re = /(\d+)\s*(h|m|s)/g; let m;
    while ((m = re.exec(t))) { const n = parseInt(m[1], 10); const u = m[2]; if (u === 'h') seconds += n * 3600; else if (u === 'm') seconds += n * 60; else seconds += n; }
    return seconds || null;
  }

  const navigate = () => { if (detailsHref) router.push(detailsHref); };

  return (
    <Card className={detailsHref ? "cursor-pointer" : undefined} onClick={detailsHref ? navigate : undefined}>
      <div className="flex gap-3">
        <span className={`w-1 shrink-0 rounded ${accent}`} aria-hidden />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 pl-2.5">
              <div className={`flex items-center gap-1.5 ${statusColor}`}>
                <span className={`text-sm font-medium ${statusColor}`}>{statusText}</span>
              </div>
              <h3 className="mt-2 text-lg font-semibold text-gray-900 truncate">
                {title || 'Stream'}{streamId ? ` — ${streamId}` : ''}
              </h3>
            </div>
            <div className="text-right text-sm text-gray-700">
              <div className="flex items-center gap-1 justify-end">
                <RiTimeFill className="h-4 w-4 text-gray-500" aria-hidden />
                <span className="font-medium">{humanDuration(localRemaining)}</span>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-700" onClick={(e) => e.stopPropagation()}>
              Recipient
              <span className="font-mono text-[11px] text-gray-600 truncate max-w-[10rem] sm:max-w-[16rem]" title={chain.recipient}>{chain.recipient}</span>
            </span>
            <span className="inline-flex items-center gap-1.5 rounded bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-700" onClick={(e) => e.stopPropagation()}>
              Rate
              <span className="text-[11px] text-gray-600 truncate" title={`${ratePerHour}`}>{ratePerHour}</span>
            </span>
            <span className="inline-flex items-center gap-1.5 rounded bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-700">
              Balance
              <span className="text-[11px] text-gray-600 truncate" title={remStr}>{remStr}</span>
            </span>
          </div>

          <Tracker data={trackerData} className="mt-5 hidden sm:flex" />
          <Tracker data={trackerData.slice(0, 30)} className="mt-5 flex sm:hidden" />

          <div className="mt-5 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-3" onClick={(e) => e.stopPropagation()}>
            {detailsHref && <a href={detailsHref} className="btn btn-secondary" onClick={(e) => e.stopPropagation()}>Details</a>}
            {onTopUp && !chain.halted && (
              <>
                <button className="btn btn-secondary" disabled={busy} onClick={(e) => { e.stopPropagation(); onTopUp(1800); }}>+30 min</button>
                <button className="btn btn-secondary" disabled={busy} onClick={(e) => { e.stopPropagation(); onTopUp(3600); }}>{busy ? (<span>+1 h</span>) : '+1 h'}</button>
                <button className="btn btn-secondary" disabled={busy} onClick={(e) => { e.stopPropagation(); onTopUp(7200); }}>+2 h</button>
                <div className="flex items-center gap-2">
                  <input
                    className="input w-44"
                    placeholder="Custom: 45m, 1h30m"
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onFocus={(e) => e.stopPropagation()}
                    disabled={busy}
                  />
                  <button
                    className="btn btn-secondary"
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      const secs = parseHumanTime(customInput);
                      if (secs && secs > 0) onTopUp(secs);
                    }}
                  >Top up</button>
                </div>
              </>
            )}
            {actionsRight}
          </div>
        </div>
      </div>
    </Card>
  );
}
