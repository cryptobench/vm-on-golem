"use client";

import { StreamsEmptyState, StreamsInfoBanner } from "../../components/streams/StreamsEmptyState";
import { StreamsSkeleton } from "../../components/streams/StreamsSkeleton";
import { StreamsSummary } from "../../components/streams/StreamsSummary";
import { StreamsTable } from "../../components/streams/StreamsTable";
import { StreamsToolbar } from "../../components/streams/StreamsToolbar";
import { Alert } from "@golem/ui";
import { PageHeader } from "@golem/ui";
import { useStreamsScreen } from "./useStreamsScreen";

export default function StreamsPage() {
  const screen = useStreamsScreen();

  return (
    <div className="streams-shell space-y-6">
      <PageHeader
        title="Streams"
        description="Monitor and manage payment streams for your active VMs."
        className="border-b-0 pb-0 xl:items-end"
        actions={
          <StreamsToolbar
            displayCurrency={screen.displayCurrency}
            onDisplayCurrencyChange={screen.updateDisplayCurrency}
            onRefresh={() => screen.refreshStreams({ background: true })}
            refreshing={screen.refreshing}
          />
        }
      />

      {screen.error ? (
        <Alert tone="danger" className="rounded-lg">
          {screen.error}
        </Alert>
      ) : null}

      {!screen.mounted || screen.rows === null ? (
        <StreamsSkeleton />
      ) : (
        <>
          <StreamsSummary
            active={screen.active}
            ended={screen.ended}
            displayCurrency={screen.displayCurrency}
            nowSec={screen.nowSec}
            onShowEnded={() => screen.updateShowEnded(true)}
          />

          {screen.hasRows ? (
            <StreamsTable
              active={screen.active}
              ended={screen.ended}
              nowSec={screen.nowSec}
              showEnded={screen.showEnded}
              onShowEndedChange={screen.updateShowEnded}
              busy={screen.busy}
              actionsDisabled={!screen.paymentReady}
              actionsDisabledReason={
                !screen.paymentReady ? screen.paymentMessage : null
              }
              displayCurrency={screen.displayCurrency}
              onTopUp={screen.topUp}
            />
          ) : (
            <StreamsEmptyState
              title={
                screen.hasConfiguredStreams
                  ? "No stream data available"
                  : "No streams yet"
              }
              description={
                screen.hasConfiguredStreams
                  ? "Your VMs have stream IDs, but their on-chain stream data could not be loaded."
                  : "You don't have any payment streams yet. Rent a VM to create your first payment stream."
              }
              showRentAction={!screen.hasConfiguredStreams}
            />
          )}
        </>
      )}

      <StreamsInfoBanner />
    </div>
  );
}
