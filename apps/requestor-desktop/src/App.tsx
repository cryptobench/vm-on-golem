import React from "react";
import { HashRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { SWRConfig } from "swr";
import { ToastProvider } from "@golem/ui";
import { AdsProvider } from "../../../requestor-web/context/AdsContext";
import { ProjectsProvider } from "../../../requestor-web/context/ProjectsContext";
import { WalletProvider } from "../../../requestor-web/context/WalletContext";
import { Sidebar } from "../../../requestor-web/components/layout/Sidebar";
import { AppTopBar } from "../../../requestor-web/components/layout/AppTopBar";
import { CreateWizardHost } from "../../../requestor-web/components/create/CreateWizardHost";
import { ProjectDashboard } from "../../../requestor-web/components/dashboard/ProjectDashboard";
import ProvidersScreen from "../../../requestor-web/app/providers/ProvidersScreen";
import RentalsScreen from "../../../requestor-web/app/rentals/RentalsScreen";
import StreamsScreen from "../../../requestor-web/app/streams/StreamsScreen";
import ProjectsScreen from "../../../requestor-web/app/projects/ProjectsScreen";
import SettingsScreen from "../../../requestor-web/app/settings/SettingsScreen";
import VmDetailsClient from "../../../requestor-web/app/vm/VmDetailsClient";
import { startPricePolling } from "../../../requestor-web/lib/prices";

export function App() {
  React.useEffect(() => {
    const stop = startPricePolling();
    return () => {
      try {
        stop?.();
      } catch {}
    };
  }, []);

  return (
    <HashRouter>
      <WalletProvider>
        <AdsProvider>
          <ProjectsProvider>
            <ToastProvider>
              <SWRConfig value={{ revalidateOnFocus: false }}>
                <div className="grid min-h-screen w-full grid-cols-1 bg-background text-text-primary lg:grid-cols-[var(--sidebar-width)_1fr]">
                  <Sidebar />
                  <div className="relative">
                    <AppTopBar />
                    <main className="px-4 pb-8 sm:px-6 lg:px-8">
                      <div className="w-full">
                      <Routes>
                        <Route path="/" element={<ProjectDashboard />} />
                        <Route path="/providers" element={<ProvidersScreen />} />
                        <Route path="/rentals" element={<RentalsScreen />} />
                        <Route path="/streams" element={<StreamsScreen />} />
                        <Route path="/projects" element={<ProjectsScreen />} />
                        <Route path="/settings" element={<SettingsScreen />} />
                        <Route path="/vm" element={<VmDetailsClient />} />
                        <Route path="/vm/:id" element={<VmDetailsRoute />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                      </Routes>
                      </div>
                    </main>
                    <CreateWizardHost />
                  </div>
                </div>
              </SWRConfig>
            </ToastProvider>
          </ProjectsProvider>
        </AdsProvider>
      </WalletProvider>
    </HashRouter>
  );
}

function VmDetailsRoute() {
  const { id } = useParams();
  return <VmDetailsClient vmId={id} />;
}
