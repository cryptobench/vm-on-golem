import { FormField, Input, Select } from "@golem/ui";
import {
  SERVICE_FILTER_OPTIONS,
  STATUS_FILTER_OPTIONS,
} from "./webhookConstants";
import type {
  ServiceFilter,
  StatusFilter,
} from "./webhookTypes";

export function WebhookFilters({
  search,
  serviceFilter,
  statusFilter,
  onSearchChange,
  onServiceFilterChange,
  onStatusFilterChange,
}: {
  search: string;
  serviceFilter: ServiceFilter;
  statusFilter: StatusFilter;
  onSearchChange: (search: string) => void;
  onServiceFilterChange: (filter: ServiceFilter) => void;
  onStatusFilterChange: (filter: StatusFilter) => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="grid items-end gap-4 lg:grid-cols-[minmax(0,1fr)_12rem_12rem]">
        <FormField label="Search">
          <Input
            type="search"
            placeholder="Search webhooks..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </FormField>
        <FilterSelect
          label="Service type"
          value={serviceFilter}
          options={SERVICE_FILTER_OPTIONS}
          onChange={(value) => onServiceFilterChange(value as ServiceFilter)}
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          options={STATUS_FILTER_OPTIONS}
          onChange={(value) => onStatusFilterChange(value as StatusFilter)}
        />
      </div>
    </div>
  );
}

function FilterSelect<TValue extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: TValue;
  options: Array<[TValue, string]>;
  onChange: (value: TValue) => void;
}) {
  return (
    <FormField label={label}>
      <Select
        value={value}
        onChange={(event) => onChange(event.target.value as TValue)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </Select>
    </FormField>
  );
}
