"use client";

import React from "react";
import { Button } from "./Button";

export function Pagination({
  page,
  pageCount,
  total,
  pageSize,
  itemLabel,
  onPageChange,
}: {
  page: number;
  pageCount: number;
  total: number;
  pageSize: number;
  itemLabel: (count: number) => string;
  onPageChange: (page: number) => void;
}) {
  const firstItem = total ? (page - 1) * pageSize + 1 : 0;
  const lastItem = Math.min(page * pageSize, total);

  return (
    <div className="grid gap-4 pt-2 text-sm text-text-secondary sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center">
      <span className="sm:justify-self-start">
        Showing {firstItem} to {lastItem} of {itemLabel(total)}
      </span>
      <div className="flex items-center justify-center gap-2 sm:justify-self-center">
        <Button
          variant="secondary"
          className="h-9 w-9 px-0"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page === 1}
          aria-label="Previous page"
        >
          &lsaquo;
        </Button>
        {Array.from({ length: Math.min(3, pageCount) }).map((_, index) => {
          const pageNumber = index + 1;
          return (
            <Button
              variant={page === pageNumber ? "primary" : "secondary"}
              className="h-9 w-9 px-0"
              key={pageNumber}
              onClick={() => onPageChange(pageNumber)}
              aria-label={`Page ${pageNumber}`}
            >
              {pageNumber}
            </Button>
          );
        })}
        {pageCount > 4 ? <span className="px-2">...</span> : null}
        {pageCount > 3 ? (
          <Button
            variant={page === pageCount ? "primary" : "secondary"}
            className="h-9 w-9 px-0"
            onClick={() => onPageChange(pageCount)}
            aria-label={`Page ${pageCount}`}
          >
            {pageCount}
          </Button>
        ) : null}
        <Button
          variant="secondary"
          className="h-9 w-9 px-0"
          onClick={() => onPageChange(Math.min(pageCount, page + 1))}
          disabled={page === pageCount}
          aria-label="Next page"
        >
          &rsaquo;
        </Button>
      </div>
    </div>
  );
}
