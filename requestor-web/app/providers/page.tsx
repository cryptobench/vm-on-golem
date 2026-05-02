"use client";
import React from "react";
import { fetchProviders, computeEstimate } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { Spinner } from "../../components/ui/Spinner";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { ProviderRow } from "../../components/providers/ProviderRow";
import { RentDialog as RentDialogExt } from "../../components/providers/RentDialog";
import { countryFlagEmoji, countryFullName } from "../../lib/intl";
import { useSettings } from "../../hooks/useSettings";

export default function ProvidersPage() {
  const { displayCurrency } = useSettings();
  const [cpu, setCpu] = React.useState<number | undefined>();
  const [memory, setMemory] = React.useState<number | undefined>();
  const [storage, setStorage] = React.useState<number | undefined>();
  const [country, setCountry] = React.useState<string>("");
  const [platform, setPlatform] = React.useState<string>("");
  const [countries, setCountries] = React.useState<string[] | undefined>(undefined);
  const [countryOptions, setCountryOptions] = React.useState<string[]>([]);
  const [loadingCountries, setLoadingCountries] = React.useState<boolean>(false);
  const [maxUsd, setMaxUsd] = React.useState<number | undefined>(undefined);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [rows, setRows] = React.useState<any[]>([]);
  const [selectedProviderId, setSelectedProviderId] = React.useState<string | null>(null);
  const [rentOpen, setRentOpen] = React.useState(false);

  // Refs to enable focusing first missing input
  const cpuRef = React.useRef<HTMLInputElement | null>(null);
  const memRef = React.useRef<HTMLInputElement | null>(null);
  const stoRef = React.useRef<HTMLInputElement | null>(null);

  const { ads } = useAds();

  const isSpecValid = (cpu ?? 0) > 0 && (memory ?? 0) > 0 && (storage ?? 0) >= 10;
  const missing: string[] = [
    ...((cpu ?? 0) > 0 ? [] : ["vCPU"]),
    ...((memory ?? 0) > 0 ? [] : ["RAM"]),
    ...((storage ?? 0) >= 10 ? [] : ["Storage ≥ 10 GB"]),
  ];

  const focusFirstMissing = React.useCallback(() => {
    if ((cpu ?? 0) <= 0) { cpuRef.current?.focus(); return; }
    if ((memory ?? 0) <= 0) { memRef.current?.focus(); return; }
    if ((storage ?? 0) <= 0) { stoRef.current?.focus(); return; }
  }, [cpu, memory, storage]);

  const search = async () => {
    setLoading(true); setError(null);
    try {
      let data = await fetchProviders({ cpu, memory, storage, country: (countries && countries.length && !country) ? undefined : (country || undefined), platform: platform || undefined }, ads);
      // Apply multi-country filter client-side if provided
      if (countries && countries.length) {
        const setC = new Set(countries.map(c => c.trim().toUpperCase()));
        data = data.filter(p => (p.country ? setC.has(p.country.toUpperCase()) : false));
      }
      // Apply price cap if specified and we have full spec
      if (maxUsd != null && cpu != null && memory != null && storage != null) {
        data = data.filter(p => {
          const est = computeEstimate(p, cpu, memory, storage);
          return est && est.usd_per_month <= maxUsd;
        });
      }
      setRows(data);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally { setLoading(false); }
  };

  React.useEffect(() => {
    // Load country options from advertisements for the select
    let cancelled = false;
    (async () => {
      setLoadingCountries(true);
      try {
        const { listCountries } = await import('../../lib/providers');
        const list = await listCountries(ads);
        if (cancelled) return;
        setCountryOptions(list);
      } catch {
        setCountryOptions([]);
      } finally { setLoadingCountries(false); }
    })();
    return () => { cancelled = true; };
  }, [ads]);

  React.useEffect(() => {
    // Initialize from URL first, then pending create, then run initial search
    let hasUrlCpu = false, hasUrlMem = false, hasUrlSto = false, hasUrlCountry = false, hasUrlPlatform = false, hasUrlMax = false;
    try {
      const sp = new URL(window.location.href).searchParams;
      const urlCpu = sp.get('cpu'); hasUrlCpu = urlCpu != null;
      const urlMem = sp.get('memory'); hasUrlMem = urlMem != null;
      const urlSto = sp.get('storage'); hasUrlSto = urlSto != null;
      const urlCountry = sp.get('country'); hasUrlCountry = urlCountry != null;
      const urlPlatform = sp.get('platform'); hasUrlPlatform = urlPlatform != null;
      const urlMax = sp.get('max_usd'); hasUrlMax = urlMax != null;
      if (urlCpu != null) setCpu(Number(urlCpu));
      if (urlMem != null) setMemory(Number(urlMem));
      if (urlSto != null) setStorage(Number(urlSto));
      if (urlCountry != null) setCountry(urlCountry);
      if (urlPlatform != null) setPlatform(urlPlatform);
      if (urlMax != null) setMaxUsd(Number(urlMax));
    } catch {}

    // Fallback to pre-fill from quick create wizard if present
    try {
      const raw = localStorage.getItem('requestor_pending_create');
      if (raw) {
        const data = JSON.parse(raw);
        if (data.cpu != null && !hasUrlCpu) setCpu(Number(data.cpu));
        if (data.memory != null && !hasUrlMem) setMemory(Number(data.memory));
        if (data.storage != null && !hasUrlSto) setStorage(Number(data.storage));
        if (Array.isArray(data.countries) && data.countries.length) { setCountries(data.countries); setCountry(""); }
        else if (data.country && !hasUrlCountry) setCountry(String(data.country));
        if (data.platform && !hasUrlPlatform) setPlatform(String(data.platform));
        if (data.max_usd_per_month != null && !hasUrlMax) setMaxUsd(Number(data.max_usd_per_month));
        localStorage.removeItem('requestor_pending_create');
      }
    } catch {}
    // Initial search
    search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep URL in sync with current spec/filters
  React.useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const setOrDel = (key: string, val?: string | number) => {
        if (val == null || String(val) === '' || (typeof val === 'number' && !Number.isFinite(val))) params.delete(key);
        else params.set(key, String(val));
      };
      setOrDel('cpu', cpu);
      setOrDel('memory', memory);
      setOrDel('storage', storage);
      setOrDel('country', country || undefined);
      setOrDel('platform', platform || undefined);
      setOrDel('max_usd', maxUsd);
      const next = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState(null, '', next);
    } catch {}
  }, [cpu, memory, storage, country, platform, maxUsd]);


  // Debounced search on filter/spec changes for a seamless feel
  React.useEffect(() => {
    const t = setTimeout(() => { search(); }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cpu, memory, storage, country, platform, maxUsd]);

  React.useEffect(() => {
    if (!rows.length) return;
    try {
      const pending = localStorage.getItem('requestor_pending_rent');
      if (!pending) return;
      if (!rows.some((row) => row.provider_id === pending)) return;
      localStorage.removeItem('requestor_pending_rent');
      setSelectedProviderId(pending);
      setRentOpen(true);
    } catch {}
  }, [rows]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2>Providers</h2>
      </div>
      <div className="card">
        <div className="card-body">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="text-base font-medium">VM requirements</div>
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">Required</span>
            </div>
            <div className="text-sm text-gray-600">
              {isSpecValid ? `${rows.length} matching provider${rows.length === 1 ? '' : 's'}` : 'Enter vCPU, RAM, and Storage to see matches'}
            </div>
          </div>
          {/* Specs row */}
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label">vCPU</label>
              <input ref={cpuRef} className="input w-24" type="number" min={1} value={cpu ?? ''} onChange={e => setCpu(e.target.value ? Number(e.target.value) : undefined)} />
            </div>
            <div>
              <label className="label">RAM (GB)</label>
              <input ref={memRef} className="input w-24" type="number" min={1} value={memory ?? ''} onChange={e => setMemory(e.target.value ? Number(e.target.value) : undefined)} />
            </div>
            <div>
              <label className="label">Storage (GB)</label>
              <input ref={stoRef} className="input w-24" type="number" min={10} value={storage ?? ''} onChange={e => setStorage(e.target.value ? Number(e.target.value) : undefined)} />
            </div>
          </div>
          {/* Inline checklist for required specs */}
          <div className="mt-2 flex items-center gap-3 text-xs text-gray-600">
            <span className={"inline-flex items-center gap-1 " + ((cpu ?? 0) > 0 ? 'text-emerald-700' : 'text-gray-500')}>
              <span className={`h-2 w-2 rounded-full ${((cpu ?? 0) > 0) ? 'bg-emerald-500' : 'bg-gray-300'}`} aria-hidden /> vCPU
            </span>
            <span className={"inline-flex items-center gap-1 " + ((memory ?? 0) > 0 ? 'text-emerald-700' : 'text-gray-500')}>
              <span className={`h-2 w-2 rounded-full ${((memory ?? 0) > 0) ? 'bg-emerald-500' : 'bg-gray-300'}`} aria-hidden /> RAM
            </span>
            <span className={"inline-flex items-center gap-1 " + ((storage ?? 0) > 0 ? 'text-emerald-700' : 'text-gray-500')}>
              <span className={`h-2 w-2 rounded-full ${((storage ?? 0) >= 10) ? 'bg-emerald-500' : 'bg-gray-300'}`} aria-hidden /> Storage ≥ 10 GB
            </span>
            {!isSpecValid && (
              <span className="ml-2 text-gray-500">Add {missing.join(', ')} to continue</span>
            )}
          </div>
          {/* Secondary filters row */}
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <div>
              <label className="label">Country</label>
              <select
                className="input"
                value={country}
                onChange={e => setCountry(e.target.value)}
                disabled={loadingCountries}
              >
                <option value="">Any</option>
                {countryOptions.map(code => (
                  <option key={code} value={code}>{countryFlagEmoji(code)} {countryFullName(code)} ({code})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Platform</label>
              <select className="input" value={platform} onChange={e => setPlatform(e.target.value)}>
                <option value="">Any</option>
                <option value="x86_64">x86_64</option>
                <option value="arm64">arm64</option>
              </select>
            </div>
            <div>
              <label className="label">Max $/mo</label>
              <input className="input w-28" type="number" min={0} value={maxUsd ?? ''} onChange={e => setMaxUsd(e.target.value ? Number(e.target.value) : undefined)} placeholder="cap" />
            </div>
            <div className="ml-auto flex items-center gap-3">
              {loading && <Spinner />}
            </div>
          </div>
          {countries && countries.length > 0 && (
            <div className="mt-2 text-xs text-gray-500">Countries: {countries.join(', ')}</div>
          )}
          {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        </div>
      </div>
      <div>
        {loading ? (
          <TableSkeleton rows={6} cols={5} />
        ) : (
          <div className="space-y-3">
            {rows.map((p) => {
              const estRaw = (cpu && memory && storage) ? computeEstimate(p, cpu, memory, storage) : null;
              const est = estRaw ? { usd_per_month: estRaw.usd_per_month, usd_per_hour: estRaw.usd_per_hour, glm_per_month: (estRaw.glm_per_month ?? undefined) } : null;
              return (
                <ProviderRow
                  key={p.provider_id}
                  provider={p}
                  estimate={est}
                  displayCurrency={displayCurrency as any}
                  selected={selectedProviderId === p.provider_id}
                  onToggle={() => {
                    setSelectedProviderId(prev => prev === p.provider_id ? null : p.provider_id);
                    if (!isSpecValid) {
                      // Nudge user to fill required specs
                      setTimeout(() => focusFirstMissing(), 0);
                    }
                  }}
                />
              );
            })}
          </div>
        )}
      </div>
      {/* Bottom checkout banner */}
      {selectedProviderId && (() => {
        const sel = rows.find(r => r.provider_id === selectedProviderId);
        if (!sel) return null;
        const est = (cpu && memory && storage) ? computeEstimate(sel, cpu, memory, storage) : null;
        const priceStr = est ? (
          displayCurrency === 'token' && est.glm_per_month != null ? `~${est.glm_per_month} GLM/mo (~${(est.glm_per_month/730).toFixed(8)} GLM/hr)` : `~$${est.usd_per_month} / mo (~${est.usd_per_hour}/hr)`
        ) : '—';
        return (
          <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-white">
            <div className="mx-auto max-w-6xl px-4 py-3">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm text-gray-700">Selected provider</div>
                  <div className="text-sm font-medium text-gray-900 truncate">{sel.provider_name || sel.provider_id}</div>
                </div>
                <div className="ml-auto flex items-center gap-6">
                  <div className="text-right">
                    <div className="text-xs text-gray-600">Estimated price</div>
                    <div className="text-base text-gray-900">{priceStr}</div>
                  </div>
                  {!isSpecValid && (
                    <div className="text-sm text-gray-600">Add {missing.join(', ')} to proceed</div>
                  )}
                  <button
                    className="btn btn-primary"
                    onClick={() => setRentOpen(true)}
                    disabled={loading || !isSpecValid}
                    aria-disabled={loading || !isSpecValid}
                    aria-label={isSpecValid ? 'Rent VM' : `Disabled. Missing: ${missing.join(', ')}`}
                  >
                    Rent VM
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}
      {/* Rent dialog from banner */}
      {rentOpen && selectedProviderId && (() => {
        const sel = rows.find(r => r.provider_id === selectedProviderId);
        if (!sel) return null;
        return (
          <RentDialogExt
            provider={sel}
            defaultSpec={{ cpu: cpu || 1, memory: memory || 2, storage: storage || 20 }}
            onClose={() => setRentOpen(false)}
            adsMode={ads}
          />
        );
      })()}
    </div>
  );
}
