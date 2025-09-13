"use client";
import React from "react";
import { Spinner } from "../ui/Spinner";
import { Skeleton } from "../ui/Skeleton";
import { useAds } from "../../context/AdsContext";
import { fetchAllProviders, computePriceRange, computeEstimate, loadSettings, saveSettings, type SSHKey, type ProviderAd } from "../../lib/api";
import { Modal } from "../ui/Modal";
import { ProviderRow } from "../providers/ProviderRow";
import { KeyPicker } from "../ssh/KeyPicker";
import { countryFullName, countryFlagEmoji } from "../../lib/intl";

type Step = 0 | 1 | 2 | 3 | 4;

export function CreateWizard({ open, onClose, onComplete }: { open: boolean; onClose: () => void; onComplete: (data: { countries?: string[]; cpu?: number; memory?: number; storage?: number; platform?: string; sshKeyId?: string; max_usd_per_month?: number; provider_id?: string }) => void }) {
  const { ads } = useAds();
  const settings = loadSettings();
  const initialKeys: SSHKey[] = settings.ssh_keys || (settings.ssh_public_key ? [{ id: 'default', name: 'Default', value: settings.ssh_public_key }] : []);

  const [step, setStep] = React.useState<Step>(0);
  const [allProviders, setAllProviders] = React.useState<ProviderAd[] | null>(null);
  const [loadingCountries, setLoadingCountries] = React.useState(false);
  const [countryOptions, setCountryOptions] = React.useState<string[]>([]);
  const [countries, setCountries] = React.useState<string[]>([]);
  const [anyCountry, setAnyCountry] = React.useState(true);

  const [mode, setMode] = React.useState<'specific' | 'explore'>('specific');
  const [cpu, setCpu] = React.useState<number | undefined>();
  const [memory, setMemory] = React.useState<number | undefined>();
  const [storage, setStorage] = React.useState<number | undefined>();
  const [platform, setPlatform] = React.useState<string>("");

  const [priceMin, setPriceMin] = React.useState<number | null>(null);
  const [priceMax, setPriceMax] = React.useState<number | null>(null);
  const [maxPrice, setMaxPrice] = React.useState<number | null>(null);

  const [sshKeys, setSshKeys] = React.useState<SSHKey[]>(initialKeys);
  const [sshKeyId, setSshKeyId] = React.useState<string | undefined>(settings.default_ssh_key_id || initialKeys[0]?.id);
  const [busy, setBusy] = React.useState(false);
  const [selectedProvider, setSelectedProvider] = React.useState<string | null>(null);
  // SSH key add handled by KeyPicker
  const displayCurrency: 'fiat' | 'token' = ((typeof window !== 'undefined' && (JSON.parse(localStorage.getItem('requestor_settings_v1') || '{}')?.display_currency === 'token')) ? 'token' : 'fiat');

  // Reset on open
  React.useEffect(() => {
    if (open) {
      setStep(0); setAnyCountry(true); setCountries([]); setMode('specific'); setCpu(undefined); setMemory(undefined); setStorage(undefined); setPlatform(""); setMaxPrice(null);
      // Refresh SSH keys from settings when opening
      const s = loadSettings();
      const ks: SSHKey[] = s.ssh_keys || (s.ssh_public_key ? [{ id: 'default', name: 'Default', value: s.ssh_public_key }] : []);
      setSshKeys(ks);
      setSshKeyId(s.default_ssh_key_id || ks[0]?.id);
    }
  }, [open]);

  // Fetch countries and all providers
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      setLoadingCountries(true);
      try {
        const { listCountries } = await import('../../lib/providers');
        const providers = await fetchAllProviders(ads);
        if (cancelled) return;
        setAllProviders(providers);
        const list = await listCountries(ads);
        if (cancelled) return;
        setCountryOptions(list);
      } catch (e) {
        console.warn('Failed to load providers for country list', e);
        setCountryOptions([]);
      } finally { setLoadingCountries(false); }
    })();
    return () => { cancelled = true; };
  }, [open, ads]);

  // Recompute price range when spec or provider list changes
  React.useEffect(() => {
    if (!allProviders) { setPriceMin(null); setPriceMax(null); setMaxPrice(null); return; }
    const spec = (mode === 'specific') ? { cpu, memory, storage } : undefined;
    const range = computePriceRange(allProviders, spec);
    if (!range) { setPriceMin(null); setPriceMax(null); setMaxPrice(null); return; }
    setPriceMin(range.min);
    setPriceMax(range.max);
    if (maxPrice == null || maxPrice < range.min || maxPrice > range.max) setMaxPrice(range.max);
  }, [allProviders, cpu, memory, storage, mode]);

  const headerId = "create-wizard-title";
  const matches = React.useMemo(() => {
    if (!allProviders) return [] as ProviderAd[];
    const setC = new Set(countries.map(c => c.toUpperCase()));
    return allProviders.filter(p => {
      if (!anyCountry) {
        const cc = (p.country || '').toUpperCase();
        if (!cc || !setC.has(cc)) return false;
      }
      if (platform && (p.platform || '').trim() !== platform.trim()) return false;
      if (mode === 'specific') {
        if (cpu != null && (p.resources.cpu < cpu)) return false;
        if (memory != null && (p.resources.memory < memory)) return false;
        if (storage != null && (p.resources.storage < storage)) return false;
        if (maxPrice != null && cpu != null && memory != null && storage != null) {
          const est = computeEstimate(p, cpu, memory, storage);
          if (!est || est.usd_per_month > maxPrice) return false;
        }
      }
      return true;
    });
  }, [allProviders, anyCountry, countries, platform, mode, cpu, memory, storage, maxPrice]);

  const next = () => setStep((s) => (s < 4 ? ((s + 1) as Step) : s));
  const back = () => setStep((s) => (s > 0 ? ((s - 1) as Step) : s));
  const finish = async () => {
    setBusy(true);
    try {
      // Require a provider selection before finishing
      if (!selectedProvider) {
        alert('Please select a provider to continue.');
        return;
      }
      // If no SSH key is present/selected, prompt to add one first
      if (!sshKeyId || sshKeys.length === 0) {
        const go = confirm('No SSH key found. You need an SSH key to provision. Go to Settings to add one now?');
        if (go) {
          try {
            localStorage.setItem('requestor_pending_create', JSON.stringify({
              countries: anyCountry ? undefined : countries,
              cpu: mode === 'specific' ? cpu : undefined,
              memory: mode === 'specific' ? memory : undefined,
              storage: mode === 'specific' ? storage : undefined,
              platform: platform || undefined,
              max_usd_per_month: (mode === 'specific' && maxPrice != null) ? maxPrice : undefined,
            }));
            localStorage.setItem('requestor_pending_rent', selectedProvider);
          } catch {}
          // Navigate to settings
          window.location.href = '/settings';
          return;
        } else {
          setBusy(false);
          return;
        }
      }
      onComplete({
        countries: anyCountry ? undefined : countries,
        cpu: mode === 'specific' ? cpu : undefined,
        memory: mode === 'specific' ? memory : undefined,
        storage: mode === 'specific' ? storage : undefined,
        platform: platform || undefined,
        sshKeyId,
        max_usd_per_month: (mode === 'specific' && maxPrice != null) ? maxPrice : undefined,
        provider_id: selectedProvider,
      });
    } finally { setBusy(false); }
  };

  if (!open) return null;
  const contentPad = step === 3 ? "px-4 sm:px-6 pt-2 pb-6" : "px-4 sm:px-6 py-6";
  const contentWidth = step === 3 ? "" : "mx-auto max-w-5xl";

  return (
    <div className="fixed inset-0 z-50 lg:left-[16rem]" role="dialog" aria-modal="true" aria-labelledby={headerId}>
      <div className="absolute inset-0 bg-white" />
      {/* Top bar */}
      <div className="relative z-10 flex items-center justify-between border-b px-4 sm:px-6 py-4">
        <div>
          <h3 id={headerId} className="text-lg font-semibold">Create — guided setup</h3>
          <div className="text-sm text-gray-600">{step === 0 ? 'Select countries (multi-select) or choose Any.' : step === 1 ? 'Choose specific specs or explore without constraints. Optionally pick platform.' : step === 2 ? 'Set your monthly price cap.' : step === 3 ? 'Pick a provider' : 'Select an SSH key.'}</div>
        </div>
        <button className="btn btn-secondary" onClick={onClose}>Close</button>
      </div>
      {/* Content */}
      <div className={"relative z-10 " + contentWidth + " " + contentPad}>
        <div className="transition-all">
          {step === 0 && (
            <div className="grid gap-4">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-700">Countries</div>
                <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand-600" checked={anyCountry} onChange={(e) => setAnyCountry(e.target.checked)} /><span>Any country</span></label>
              </div>
              {loadingCountries ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {Array.from({ length: 8 }).map((_, i) => (<Skeleton key={i} className="h-10" />))}
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {countryOptions.map((code) => {
                    const active = countries.includes(code);
                    const label = countryFullName(code);
                    const flag = countryFlagEmoji(code);
                    return (
                      <button
                        key={code}
                        className={
                          "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition " +
                          (active ? "border-brand-300 bg-brand-50 text-brand-700" : "hover:bg-gray-50")
                        }
                        onClick={() => {
                          setCountries((prev) => {
                            // If "Any country" is active, deselect it automatically
                            if (anyCountry) setAnyCountry(false);
                            return prev.includes(code) ? prev.filter(x => x !== code) : [...prev, code];
                          });
                        }}
                      >
                        <span className="text-lg">{flag}</span>
                        <span>{label}</span>
                      </button>
                    );
                  })}
                  {!countryOptions.length && <div className="col-span-full text-sm text-gray-500">No countries available from current advertiser.</div>}
                </div>
              )}
              {!anyCountry && countries.length > 0 && (
                <div className="text-xs text-gray-500">Selected: {countries.join(', ')}</div>
              )}
            </div>
          )}

          {step === 1 && (
            <div className="grid gap-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl border p-4">
                  <div className="mb-3 font-medium">Specific specs</div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="label">CPU</label>
                      <input className="input" type="number" min={1} value={cpu ?? ''} onChange={e => { setMode('specific'); setCpu(e.target.value ? Number(e.target.value) : undefined); }} placeholder="e.g., 2" />
                    </div>
                    <div>
                      <label className="label">Memory (GB)</label>
                      <input className="input" type="number" min={1} value={memory ?? ''} onChange={e => { setMode('specific'); setMemory(e.target.value ? Number(e.target.value) : undefined); }} placeholder="e.g., 4" />
                    </div>
                    <div>
                      <label className="label">Disk (GB)</label>
                      <input className="input" type="number" min={1} value={storage ?? ''} onChange={e => { setMode('specific'); setStorage(e.target.value ? Number(e.target.value) : undefined); }} placeholder="e.g., 50" />
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="label">Platform</label>
                      <select className="input" value={platform} onChange={e => setPlatform(e.target.value)}>
                        <option value="">Any</option>
                        <option value="x86_64">x86_64</option>
                        <option value="arm64">arm64</option>
                      </select>
                    </div>
                  </div>
                </div>
                <button
                  className="group flex flex-col justify-center rounded-xl border p-4 text-left transition hover:bg-gray-50"
                  onClick={() => { setMode('explore'); next(); }}
                >
                  <div className="mb-1 font-medium">I’m just exploring</div>
                  <div className="text-sm text-gray-600">Skip specs and browse what’s out there.</div>
                  <div className="mt-3 inline-flex items-center text-brand-700">Continue <span className="ml-1 transition-transform group-hover:translate-x-0.5">→</span></div>
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="grid gap-4 md:grid-cols-[1fr_18rem] md:items-start">
              <div>
                <div className="text-sm text-gray-700">Max monthly price</div>
                {priceMin == null || priceMax == null ? (
                  <div className="mt-2 space-y-3">
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="h-2 w-full" />
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-4 w-16" />
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-4 w-16" />
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 space-y-3">
                    <input
                      type="range"
                      min={priceMin}
                      max={priceMax}
                      step={1}
                      value={maxPrice ?? priceMax}
                      onChange={(e) => setMaxPrice(Number(e.target.value))}
                      className="w-full accent-brand-600"
                      disabled={mode !== 'specific'}
                    />
                    <div className="flex items-center justify-between text-sm text-gray-600">
                      <span>${priceMin}/mo</span>
                      <span className="font-medium">Max: ${maxPrice ?? priceMax}/mo</span>
                      <span>${priceMax}/mo</span>
                    </div>
                    {mode !== 'specific' && (
                      <div className="text-xs text-gray-500">Select specific specs to enable price capping.</div>
                    )}
                  </div>
                )}
              </div>
              <div className="rounded-xl border p-4">
                <div className="text-sm text-gray-700">Matches</div>
                <div className="mt-2 text-3xl font-semibold">{matches.length}</div>
                <div className="mt-1 text-xs text-gray-500">providers found</div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              {matches.map((p) => {
                const estRaw = (mode === 'specific' && cpu != null && memory != null && storage != null) ? computeEstimate(p, cpu!, memory!, storage!) : null;
                const estimate = estRaw ? { usd_per_month: estRaw.usd_per_month, usd_per_hour: estRaw.usd_per_hour, glm_per_month: (estRaw.glm_per_month ?? undefined) } : null;
                return (
                  <div key={p.provider_id} className="mb-3 last:mb-0">
                    <ProviderRow
                      provider={p as any}
                      estimate={estimate}
                      displayCurrency={displayCurrency}
                      selected={selectedProvider === p.provider_id}
                      onToggle={() => setSelectedProvider(prev => prev === p.provider_id ? null : p.provider_id)}
                    />
                  </div>
                );
              })}
              {!matches.length && (
                <div className="py-4 text-sm text-gray-500">No matching providers with current filters.</div>
              )}
            </div>
          )}

          {step === 4 && (
            <div className="grid gap-3">
              <div className="text-sm text-gray-700">Select an SSH key</div>
              <KeyPicker value={sshKeyId} onChange={(id) => setSshKeyId(id)} />
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="absolute bottom-0 left-0 right-0 z-10 border-t bg-white/90 backdrop-blur px-4 sm:px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-2">
          <div className="text-xs text-gray-500">Step {step + 1} of 5</div>
          <div className="flex items-center gap-2">
            <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
            {step > 0 && <button className="btn btn-secondary" onClick={back}>Back</button>}
            {step < 4 && <button className="btn btn-primary" onClick={next}>Next</button>}
            {step === 4 && <button className="btn btn-primary" onClick={finish} disabled={busy}>{busy ? (<><Spinner className="h-4 w-4 text-white" /> Finish</>) : 'Finish'}</button>}
          </div>
        </div>
      </div>

      {/* Subtle fade-in background */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-gray-50/50 to-transparent" />

      {/* SSH Key add handled by KeyPicker */}
    </div>
  );
}

// Country helpers now imported from lib/intl
