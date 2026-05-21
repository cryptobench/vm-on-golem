"use client";

import React from "react";
import { RiFilter3Line } from "@remixicon/react";
import { Alert } from "@golem/ui";
import { Button } from "@golem/ui";
import { PageHeader } from "@golem/ui";
import { Pagination } from "@golem/ui";
import { Spinner } from "@golem/ui";
import { TableSkeleton } from "@golem/ui";
import { ToggleSwitch } from "@golem/ui";
import { RentDialog } from "../../components/providers/RentDialog";
import {
  ProviderFiltersPanel,
} from "../../components/providers/ProviderFiltersPanel";
import { ProvidersTable } from "../../components/providers/ProvidersTable";
import {
  PROVIDERS_PAGE_SIZE,
  providerCountLabel,
  useProvidersScreen,
} from "./useProvidersScreen";

export default function ProvidersPage() {
  const screen = useProvidersScreen();

  return (
    <div
      className={`providers-page grid ${screen.filtersMounted ? "providers-page--filters-mounted" : ""} ${
        screen.filtersOpen ? "providers-page--filters-open" : ""
      }`}
    >
      <div className="min-w-0 space-y-5">
        <PageHeader
          title="Providers"
          description="Browse available providers on the Golem Network."
          actions={
            <Button variant="secondary" className="h-11 px-5" onClick={screen.openFilters}>
              <RiFilter3Line className="h-5 w-5" aria-hidden />
              Filter
            </Button>
          }
        />

        <div className="flex flex-col gap-4 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-lg font-semibold text-text-primary">
            {providerCountLabel(screen.rows.length)} <span className="text-sm font-normal text-text-secondary">available</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-text-secondary">
            <span>Prices in USD</span>
            <ToggleSwitch
              checked={screen.showTokenPrices}
              label="Toggle GLM prices"
              onChange={(checked) => screen.setDisplayCurrency(checked ? "token" : "fiat")}
            />
            <span>Show price in GLM</span>
          </div>
        </div>

        {screen.error && <Alert tone="danger">{screen.error}</Alert>}

        {screen.loading ? (
          <TableSkeleton rows={PROVIDERS_PAGE_SIZE} cols={7} />
        ) : (
          <>
            <ProvidersTable
              providers={screen.visibleRows}
              spec={screen.spec}
              showTokenPrices={screen.showTokenPrices}
              donationBps={screen.donationBps}
              onSelect={(provider) => screen.setSelectedProvider(provider)}
            />
            {!screen.visibleRows.length && (
              <div className="rounded-lg border border-border bg-surface p-10 text-center text-sm text-text-secondary">
                No providers match these filters.
              </div>
            )}
          </>
        )}

        <Pagination
          page={screen.page}
          pageCount={screen.pageCount}
          total={screen.rows.length}
          pageSize={PROVIDERS_PAGE_SIZE}
          itemLabel={providerCountLabel}
          onPageChange={screen.setPage}
        />
      </div>

      {screen.filtersMounted && (
        <ProviderFiltersPanel
          filters={screen.filters}
          open={screen.filtersOpen}
          countries={screen.countries}
          loadingCountries={screen.loadingCountries}
          resultLabel={providerCountLabel(screen.rows.length)}
          showTokenPrices={screen.showTokenPrices}
          onChange={screen.setFilters}
          onApply={() => screen.loadProviders(screen.filters)}
          onReset={screen.resetFilters}
          onClose={screen.closeFilters}
          onToggleCurrency={screen.toggleCurrency}
        />
      )}

      {screen.selectedProvider && (
        <RentDialog
          provider={screen.selectedProvider}
          defaultSpec={screen.spec}
          onClose={() => screen.setSelectedProvider(null)}
          adsMode={screen.ads}
        />
      )}

      {screen.loading && (
        <div className="fixed bottom-4 right-4 hidden items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-secondary shadow-soft lg:flex">
          <Spinner className="h-4 w-4" />
          Updating providers
        </div>
      )}
    </div>
  );
}
