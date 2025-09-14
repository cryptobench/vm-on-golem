"use client";
import React from "react";
import Link from "next/link";
import { ProjectDashboard } from "../components/dashboard/ProjectDashboard";

export default function Home() {
  return (
    <div className="space-y-6">
      <div className="card">
        <div className="card-body flex flex-col gap-4 sm:flex-row sm:items-center">
          <div>
            <h1>Rent VMs on Golem</h1>
            <p className="mt-1 text-gray-600">Find providers, pay as you go, and manage your VMs.</p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/providers" className="card hover:shadow-md transition-shadow">
          <div className="card-body">
            <div className="text-sm text-gray-500">Explore</div>
            <div className="mt-1 font-semibold">Providers</div>
            <div className="mt-3 text-sm text-gray-600">Filter by vCPU, RAM, storage and estimate cost.</div>
          </div>
        </Link>
        <Link href="/rentals" className="card hover:shadow-md transition-shadow">
          <div className="card-body">
            <div className="text-sm text-gray-500">Manage</div>
            <div className="mt-1 font-semibold">My VMs</div>
            <div className="mt-3 text-sm text-gray-600">Access, terminate or connect to your VMs.</div>
          </div>
        </Link>
        <Link href="/streams" className="card hover:shadow-md transition-shadow">
          <div className="card-body">
            <div className="text-sm text-gray-500">Monitor</div>
            <div className="mt-1 font-semibold">Streams</div>
            <div className="mt-3 text-sm text-gray-600">Track stream status, rates and balances.</div>
          </div>
        </Link>
        <Link href="/settings" className="card hover:shadow-md transition-shadow">
          <div className="card-body">
            <div className="text-sm text-gray-500">Configure</div>
            <div className="mt-1 font-semibold">Settings</div>
            <div className="mt-3 text-sm text-gray-600">Set discovery mode, RPC endpoints and keys.</div>
          </div>
        </Link>
      </div>

      {/* Project-focused dashboard sections */}
      <ProjectDashboard />
    </div>
  );
}
