import React from "react";
import {
  ActionMenu,
  Card,
  CardBody,
  DataTable,
  LineAreaChart,
  PageHeader,
  Sparkline,
  StatCard,
  StatusBadge,
  Tabs,
} from "@golem/ui";
import { RiAddLine, RiCheckboxCircleLine, RiLineChartLine, RiMoneyDollarCircleLine, RiStackLine } from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import type { NavigateTarget } from "../../components/types";
import { streamEarningsPoints, streamsTotals } from "../../lib/derived";
import { EMPTY_VALUE, formatCurrency, formatGlm, formatDuration, weiToToken } from "../../lib/format";
import { glmToUsd, useGlmUsdPrice } from "../../lib/prices";
import type { DashboardData } from "../../lib/useProviderData";

type StreamTab = "active" | "all";

export function StreamsPage({
  data,
  loading,
  onNavigate,
}: {
  data: DashboardData | null;
  loading: boolean;
  onNavigate: (target: NavigateTarget) => void;
}) {
  const [tab, setTab] = React.useState<StreamTab>("active");
  const glmUsd = useGlmUsdPrice();
  if (loading && !data) return <LoadingGrid />;
  const streams = data?.streams ?? [];
  const totals = streamsTotals(streams);
  const totalEarnedUsd = glmToUsd(totals.vested, glmUsd);
  const activeStreams = streams.filter((stream) => (stream.payment_state ?? "active") === "active");
  const visible = tab === "active" ? activeStreams : streams;
  const points = streamEarningsPoints(streams);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Streams & Earnings"
        description="Track revenue from machines rented out to requestors."
      />
      <EndpointErrors errors={data?.errors ?? {}} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Earned (USD)" value={formatCurrency(totalEarnedUsd)} detail={glmUsd == null ? "Waiting for GLM/USD quote" : "Converted from stream GLM"} icon={<RiMoneyDollarCircleLine className="h-5 w-5" />} tone="success" />
        <StatCard label="Total Earned (GLM)" value={formatGlm(totals.vested)} detail="From stream vested values" icon={<RiStackLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Active Streams" value={activeStreams.length} detail={`${streams.length} mapped`} icon={<RiLineChartLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Withdrawable (GLM)" value={formatGlm(totals.withdrawable)} icon={<RiAddLine className="h-5 w-5" />} tone="success" />
      </div>

      <Tabs<StreamTab>
        tabs={[
          { id: "active", label: "Active Streams" },
          { id: "all", label: "All Streams" },
        ]}
        active={tab}
        onChange={setTab}
      />

      <Card>
        <CardBody className="p-0">
          <DataTable
            rows={visible}
            getRowKey={(stream) => `${stream.vm_id}-${stream.stream_id}`}
            empty="No payment streams"
            columns={[
              {
                key: "vm",
                header: "VM",
                render: (stream) => {
                  const vm = data?.vms.find((item) => item.id === stream.vm_id);
                  return (
                    <button
                      type="button"
                      className="text-left font-medium text-text-primary hover:text-primary"
                      onClick={() => onNavigate({ page: "vm-detail", vmId: stream.vm_id })}
                    >
                      {stream.vm_id}
                      <span className="block text-sm font-normal text-text-secondary">
                        {vm ? `${vm.resources.cpu} CPU - ${vm.resources.memory} GB RAM` : EMPTY_VALUE}
                      </span>
                    </button>
                  );
                },
              },
              { key: "stream", header: "Stream ID", render: (stream) => stream.stream_id },
              {
                key: "verified",
                header: "Verified",
                render: (stream) => (
                  <StatusBadge
                    label={stream.verified ? "Verified" : "Issue"}
                    tone={stream.verified ? "success" : "danger"}
                  />
                ),
              },
              {
                key: "rate",
                header: "Rate (GLM / sec)",
                render: (stream) => formatGlm(weiToToken(stream.chain.ratePerSecond), 6),
              },
              {
                key: "remaining",
                header: "Remaining",
                render: (stream) => formatDuration(stream.computed.remaining_seconds),
              },
              {
                key: "vested",
                header: "Vested (GLM)",
                render: (stream) => formatGlm(weiToToken(stream.computed.vested_wei)),
              },
              {
                key: "withdrawable",
                header: "Withdrawable (GLM)",
                render: (stream) => formatGlm(weiToToken(stream.computed.withdrawable_wei)),
              },
              {
                key: "spark",
                header: "Trend",
                render: () => <Sparkline data={points} />,
              },
              {
                key: "actions",
                header: "",
                render: (stream) => (
                  <ActionMenu
                    items={[
                      { label: "Open VM", onSelect: () => onNavigate({ page: "vm-detail", vmId: stream.vm_id }) },
                    ]}
                  />
                ),
              },
            ]}
          />
        </CardBody>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardBody>
            <div className="mb-4">
              <h2 className="text-base font-semibold text-text-primary">Earnings (GLM)</h2>
              <p className="mt-1 text-2xl font-semibold">{formatGlm(totals.vested)}</p>
            </div>
            <LineAreaChart data={points} height={260} />
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <h2 className="text-base font-semibold text-text-primary">Top Earning VMs</h2>
            <div className="mt-4 space-y-3">
              {streams
                .slice()
                .sort((a, b) => b.computed.vested_wei - a.computed.vested_wei)
                .slice(0, 5)
                .map((stream) => (
                  <div key={stream.vm_id} className="flex items-center justify-between gap-4 border-b border-border pb-3">
                    <span className="font-medium text-text-primary">{stream.vm_id}</span>
                    <span className="text-text-secondary">
                      {formatGlm(weiToToken(stream.computed.vested_wei))}
                    </span>
                  </div>
                ))}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
