"use client";
import React from "react";
import { Wallet } from "../components/Wallet";
import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-6">
      <div className="card">
        <div className="card-body flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1>VM on Golem — Requestor Portal</h1>
            <p className="mt-1 text-gray-600">Discover providers, open payment streams, rent and manage your VMs.</p>
          </div>
          <Wallet />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/providers" className="card hover:shadow-md transition-shadow">
          <div className="card-body">
            <div className="text-sm text-gray-500">Explore</div>
            <div className="mt-1 font-semibold">Browse Providers</div>
            <div className="mt-3 text-sm text-gray-600">Filter by CPU, memory, disk and estimate cost.</div>
          </div>
        </Link>
        <Link href="/rentals" className="card hover:shadow-md transition-shadow">
          <div className="card-body">
            <div className="text-sm text-gray-500">Manage</div>
            <div className="mt-1 font-semibold">Your Rentals</div>
            <div className="mt-3 text-sm text-gray-600">Access, stop or destroy your virtual machines.</div>
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
    </div>
  );
}
