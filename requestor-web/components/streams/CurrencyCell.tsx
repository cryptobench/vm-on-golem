import {
  type DisplayCurrency,
  formatFiat,
  type StreamRow,
} from "./streamModel";

type CurrencyCellProps = {
  amount: number;
  displayCurrency: DisplayCurrency;
  row: StreamRow;
  fiatAmount?: number | null;
  tokenLabelSuffix?: string;
};

export function CurrencyCell({
  amount,
  displayCurrency,
  row,
  fiatAmount,
  tokenLabelSuffix = "",
}: CurrencyCellProps) {
  const fiat =
    fiatAmount === undefined
      ? row.usdPrice == null
        ? null
        : amount * row.usdPrice
      : fiatAmount;
  const tokenValue = `${formatTokenValue(amount, row.tokenSymbol)}${tokenLabelSuffix}`;

  return (
    <div>
      <div className="font-medium text-text-primary">
        {displayCurrency === "fiat" && fiat != null
          ? `${formatFiat(fiat, 2)}${tokenLabelSuffix}`
          : tokenValue}
      </div>
      <div className="mt-1 text-xs text-text-secondary">
        {displayCurrency === "fiat" && fiat != null
          ? tokenValue
          : fiat == null
            ? "No fiat price"
            : `${formatFiat(fiat, 2)}${tokenLabelSuffix}`}
      </div>
    </div>
  );
}

export function formatTokenValue(value: number, symbol: string) {
  return `${value.toFixed(4)} ${symbol || "TOKEN"}`;
}
