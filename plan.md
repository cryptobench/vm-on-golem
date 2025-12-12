# VM on Golem: Milestone Plan

**Project:** VM on Golem
**Version:** 1.0
**Last Updated:** December 2025

---

## Executive Summary

This document outlines the complete milestone plan for VM on Golem across all phases. Each phase includes timeline, high-level acceptance criteria, and definition of done.

### Note on KPIs

While KPIs were initially requested, this document uses acceptance criteria and definition of done as the primary success measures for each milestone. KPIs are better suited for ongoing operational metrics (uptime, user adoption, performance SLAs) rather than one-time development milestones. Each milestone is binary: either the acceptance criteria are met and demonstrable, or they aren't. This approach aligns with similar internal Golem funding arrangements (e.g., Neti) where acceptance criteria serve as the verification standard.

---

## Funding Structure

This proposal combines a fixed monthly salary in EUR with milestone-based rewards paid in GLM tokens. The salary ensures sustained focus, while milestone rewards are unlocked in stages tied to clear, verifiable outcomes.

*Note: All GLM token rewards are calculated at a reference rate of €0.21 per GLM. Final amounts may be adjusted to reflect the prevailing market rate at the time of agreement.*

**Monthly Salary:** €7,000

**Total Potential Compensation:** €84,000 (Annual Salary) + **6,000,000 GLM** (Milestones)

---

## Milestone Overview

| Phase | Name | Target | Status | Payout (GLM) |
|-------|------|--------|--------|--------------|
| ~~1~~ | ~~Discovery Service~~ | ~~Feb 2025~~ | ✅ Complete | — |
| ~~2~~ | ~~Provider API~~ | ~~Feb 2025~~ | ✅ Complete | — |
| ~~3~~ | ~~Requestor API~~ | ~~Feb 2025~~ | ✅ Complete | — |
| ~~4~~ | ~~Arkiv Integration~~ | ~~Feb 2025~~ | ✅ Complete | — |
| ~~5~~ | ~~Smart Contract Payments~~ | ~~Mar 2025~~ | ✅ Complete | — |
| 6 | Requestor GUI Marketplace | January 2026 | Planned | 95,238 |
| 7 | Verifier Network | March 2026 | Planned | 190,476 |
| 8 | Arkiv DNS | April 2026 | Planned | 380,952 |
| 9 | Provider GUI Desktop | June 2026 | Planned | 761,904 |
| 10 | Decentralized VPN dApp | October 2026 | Planned | 1,523,808 |
| 11 | Confidential Compute | December 2026 | Planned | 3,047,622 |

---

## Completed Phases

### ~~Phase 1: Discovery Service~~ ✅

**Completed:** February 2025
**Focus:** Centralized provider discovery

#### Description

Delivered a centralized discovery service enabling providers to register and advertise their resources, and requestors to query and find available providers.

#### Acceptance Criteria

- [x] FastAPI discovery server operational
- [x] Providers can register with resource specs (CPU, RAM, storage)
- [x] Providers can advertise pricing and availability
- [x] Requestors can list and filter available providers
- [x] Health check endpoints for service monitoring

---

### ~~Phase 2: Provider API~~ ✅

**Completed:** February 2025
**Focus:** Production-grade provider server

#### Description

Built the provider-side server enabling providers to manage VMs via Multipass, track resource allocation, expose REST APIs, and run reliably with auto-recovery.

#### Acceptance Criteria

- [x] Provider REST API operational (`/api/v1/vms` endpoints for create/list/get/delete)
- [x] VM lifecycle management via Multipass adapter
- [x] Resource tracking prevents over-allocation of CPU, RAM, and storage
- [x] SSH key generation and port management per VM
- [x] Provider node runs 24/7 with startup reconciliation
- [x] Health checks and status endpoints (`golem-provider status`)
- [x] VM access info endpoint returns IP and SSH port
- [x] Cloud-init configuration for VM provisioning

---

### ~~Phase 3: Requestor API~~ ✅

**Completed:** February 2025
**Focus:** Full requestor-side VM lifecycle management

#### Description

Developed the requestor-side CLI and API enabling users to provision VMs on providers, manage active rentals, and connect via SSH.

#### Acceptance Criteria

- [x] CLI supports full VM lifecycle (`golem vm create/list/info/destroy/start/stop`)
- [x] Provider discovery integration (`golem vm providers`)
- [x] Provider filtering by CPU, memory, storage, country, and platform
- [x] SSH key management and secure VM access (`golem vm ssh`)
- [x] Local database persistence of VM metadata (SQLite)
- [x] Async provisioning with timeout handling
- [x] Port allocation for SSH access (port range 50800-50900)

---

### ~~Phase 4: Arkiv Integration~~ ✅

**Completed:** February 2025
**Focus:** Decentralized provider discovery

#### Acceptance Criteria

- [x] Providers publish advertisements with live capacity and pricing to Arkiv
- [x] Requestors can filter and fetch provider advertisements

---

### ~~Phase 5: Smart Contract Payments~~ ✅

**Completed:** March 2025
**Focus:** Per-second streaming payments on L2

#### Description

Implemented on-chain streaming payment infrastructure enabling continuous per-second billing between requestors and providers using GLM tokens or native ETH on Ethereum L2.

#### Acceptance Criteria

- [x] StreamPayment smart contract deployed to L2 (Hoodi/Polygon)
- [x] Requestor can create streams with deposit and rate (`createStream`)
- [x] Per-second payment accrual based on `ratePerSecond`
- [x] Provider can withdraw vested funds (`withdraw`)
- [x] Requestor can top-up streams to extend runway (`topUp`)
- [x] Either party can terminate streams (`terminate`)
- [x] Stream verification validates recipient, deposit, and halted status
- [x] CLI commands for stream management (`golem vm stream open/topup/status/inspect/list`)
- [x] Auto-stream creation during VM provisioning with configurable hours
- [x] ERC20 token approval flow for GLM payments
- [x] StreamCreated events emitted and parseable on-chain

---

## Upcoming Phases

### Phase 6: Requestor GUI Marketplace

**Target:** January 2026
**Payout:** 95,238 GLM
**Focus:** Browser-based VM rental interface with wallet integration

#### Description

Deliver a production-ready web application that enables requestors to discover providers, provision VMs, and manage rentals entirely through a browser interface with MetaMask wallet integration.

#### Acceptance Criteria

1. **Wallet Integration**
   - [ ] MetaMask detection and connection flow
   - [ ] Automatic chain switching to payments L2 network
   - [ ] ERC20 allowance checking and approval flow for GLM
   - [ ] Transaction signing for stream creation and top-ups
   - [ ] Support for both native ETH and ERC20 (GLM) streaming

2. **Provider Discovery**
   - [ ] Dual discovery modes: Golem Base (decentralized) and Central (legacy)
   - [ ] Filter by vCPU, RAM, storage minimums
   - [ ] Filter by country, platform (x86_64/arm64), and max price
   - [ ] Price estimation display (USD/month and hourly rates)
   - [ ] Token pricing display (GLM when available)
   - [ ] Configurable discovery profiles in settings

3. **VM Provisioning**
   - [ ] Two-stage rent flow: provider selection → rent dialog
   - [ ] Editable resource specs (CPU, RAM, storage)
   - [ ] SSH key management (select saved keys, add new inline)
   - [ ] Stream deposit duration presets (1 week, 2 weeks, 30 days, custom)
   - [ ] Cost breakdown with per-unit pricing
   - [ ] Automatic stream creation with rate calculation
   - [ ] Background VM creation polling with job status tracking
   - [ ] SSH port discovery and connection info display

4. **Rental Management**
   - [ ] Project-scoped multi-workspace support
   - [ ] List active and terminated VMs with status badges
   - [ ] Real-time VM status polling (running, creating, error, terminated)
   - [ ] SSH connection info with copy-to-clipboard
   - [ ] Terminate/destroy VM actions with confirmation
   - [ ] Show/hide terminated VMs toggle
   - [ ] Individual VM details page with provider info

5. **Stream Operations**
   - [ ] List active and ended streams per project
   - [ ] Aggregate dashboard (active count, hourly spend, remaining balance)
   - [ ] Per-stream display: rate, remaining balance, countdown timer
   - [ ] Top-up flow with duration presets (1h, 1d, 7d) and custom input
   - [ ] Human-readable duration parsing (e.g., "1d 2h 30m")
   - [ ] On-chain stream inspection
   - [ ] USD price fetching for cost display (CoinGecko integration)

6. **Settings & Configuration**
   - [ ] Discovery profile management (mode, RPC/WS URLs, chain ID)
   - [ ] Payment contract address configuration
   - [ ] SSH key management (add, delete, set default)
   - [ ] Token/fiat currency display toggle
   - [ ] Settings persistence in localStorage

#### Definition of Done

- [ ] Web app builds successfully and runs locally without errors
- [ ] End-to-end rental flow demonstrated: wallet connect → provider select → VM provision → SSH access
- [ ] Stream operations verified: create, top-up, and terminate on testnet
- [ ] All acceptance criteria functional and manually tested

---

### Phase 7: Verifier Network

**Target:** March 2026
**Payout:** 190,476 GLM
**Focus:** Decentralized VM health attestation and payment protection

#### Description

Deploy a decentralized network of verifier nodes that monitor VM health and can halt payment streams for failed VMs, protecting requestors from paying for unavailable resources.

#### Acceptance Criteria

1. **Verifier Node**
   - [ ] Software that can join the verifier network
   - [ ] Automated VM health checking

2. **VM Health Verification**
   - [ ] Mechanism for verifiers to confirm VM is running and accessible
   - [ ] Resistant to spoofing by malicious providers

3. **Consensus & Coordination**
   - [ ] Multiple verifiers can agree on VM health status

4. **Payment Stream Integration**
   - [ ] Failed VMs trigger payment stream halt
   - [ ] Halted streams stop accruing for provider
   - [ ] Provider notified of halt

5. **Provider Response**
   - [ ] Provider automatically handles halted streams
   - [ ] VM cleanup on halt

#### Definition of Done

- [ ] Verifier network operational on testnet
- [ ] End-to-end: VM failure detected → stream halted → provider notified

---

### Phase 8: Golem Base DNS

**Target:** April 2026
**Payout:** 380,952 GLM
**Focus:** Decentralized dynamic DNS for providers with changing IPs

#### Description

Turn Golem Base into a decentralized Dynamic DNS layer for providers on residential or prosumer connections where public IPs can change. Domain owners delegate their authoritative name servers to Golem gateways, which answer DNS queries using real-time state from Golem Base instead of static zone files. Providers push IP updates on-chain, with ownership anchored in a smart contract—only the legitimate key holder can publish updates.

#### Acceptance Criteria

1. **DNS Gateway Infrastructure**
   - [ ] Public authoritative name servers that domain owners can delegate to
   - [ ] Gateways resolve DNS queries using real-time Golem Base state
   - [ ] Standard DNS record types supported (A, AAAA, TXT)

2. **On-Chain Domain Registry**
   - [ ] Smart contract maps domain ownership to Ethereum keys
   - [ ] Only authorized key holder can publish updates (prevents hijacking)

3. **Dynamic IP Updates**
   - [ ] Providers can push IP updates to Golem Base when address changes
   - [ ] Updates reflected in DNS resolution within seconds

4. **Provider Integration**
   - [ ] Provider software automatically detects IP changes and pushes updates

#### Definition of Done

- [ ] DNS gateways operational and delegatable
- [ ] End-to-end: provider IP changes → pushes update → DNS resolves to new IP
- [ ] Domain ownership verified on-chain

---

### Phase 9: Provider GUI Desktop

**Target:** June 2026
**Payout:** 761,904 GLM
**Focus:** Cross-platform desktop application for providers

#### Description

Deliver a desktop application for Windows, macOS, and Linux that allows providers to monitor and manage their node through a graphical interface. The GUI presents earnings, VM fleet, and configuration in a unified dashboard.

#### Acceptance Criteria

1. **Cross-Platform Support**
   - [ ] Application runs on Windows, macOS, and Linux
   - [ ] Installable packages for each platform

2. **Earnings Dashboard**
   - [ ] Display current earnings (pending and withdrawn)
   - [ ] View active payment streams and their status
   - [ ] Withdraw accumulated funds to provider wallet
   - [ ] Earnings history or summary view

3. **VM Fleet Management**
   - [ ] List all VMs with resource usage and status
   - [ ] VM lifecycle controls (stop, destroy)
   - [ ] View VM details (requestor, stream, uptime)

4. **Provider Configuration**
   - [ ] Edit pricing (per CPU, memory, storage)
   - [ ] Pause/resume resource advertisements
   - [ ] View and manage network settings (ports, DNS)

5. **Node Status**
   - [ ] Provider node health and connectivity status
   - [ ] Resource availability (CPU, RAM, storage offered vs in use)

#### Definition of Done

- [ ] Application installable and functional on all three platforms
- [ ] Provider can view earnings, manage VMs, and configure pricing through GUI
- [ ] End-to-end: launch app → view dashboard → manage VM → withdraw funds

---

### Phase 10: Decentralized VPN dApp

**Target:** October 2026
**Payout:** 1,523,808 GLM
**Focus:** Consumer VPN application powered by VM on Golem

#### Description

Ship a user-friendly VPN application that provisions encrypted tunnels through Golem providers. Users connect their wallet, select a provider by region, approve a payment stream, and establish a VPN connection—all without manual configuration.

#### Acceptance Criteria

1. **Desktop Application**
   - [ ] Application for Windows, Mac and Linux
   - [ ] Simple user flow: connect wallet → select provider → connect VPN

2. **Provider Discovery**
   - [ ] List available VPN providers with location/region
   - [ ] Filter or sort by relevant criteria (location, price)

3. **Automatic Connection**
   - [ ] App provisions VPN endpoint on provider automatically
   - [ ] Tunnel established without manual configuration
   - [ ] User's internet traffic routed through VPN

4. **Session Management**
   - [ ] Display connection status and selected provider
   - [ ] Show session duration and payment runway
   - [ ] Disconnect and top-up controls

5. **Payment Integration**
   - [ ] Per-second billing via payment streams
   - [ ] Stream created on connect, stopped on disconnect

#### Definition of Done

- [ ] VPN app functional on Windows, Mac and Linux
- [ ] End-to-end: wallet connect → provider select → VPN active → traffic routed
- [ ] Payment stream tracks VPN session

---

### Phase 11: Confidential Compute

**Target:** December 2026
**Payout:** 3,047,622 GLM
**Focus:** Hardware-backed VM isolation where providers cannot access VM contents

#### Description

Enable confidential workloads using hardware-based trusted execution environments (AMD SEV, Intel TDX, or similar). VMs run in encrypted memory that the host cannot inspect, and disk contents are protected through attestation-based key release. Requestors can run sensitive workloads without trusting the provider.

#### Acceptance Criteria

1. **Hardware-Backed Isolation**
   - [ ] VMs run in hardware-protected encrypted memory
   - [ ] Host/provider cannot inspect VM memory while running

2. **Encrypted Storage**
   - [ ] VM disk contents encrypted and inaccessible to provider
   - [ ] Keys released only after successful attestation

3. **Remote Attestation**
   - [ ] Mechanism to verify VM is running in genuine trusted environment
   - [ ] Requestor can validate VM integrity before releasing secrets

4. **Provider Support**
   - [ ] Provider software detects confidential compute capability
   - [ ] Capability advertised in provider listings

5. **Requestor Experience**
   - [ ] Requestor can request confidential VM during provisioning
   - [ ] Clear indication that VM is running in confidential mode

#### Definition of Done

- [ ] End-to-end: requestor provisions confidential VM → attestation passes → VM runs with protected memory/disk
- [ ] Demonstrated that provider cannot access VM contents
- [ ] At least one provider offering confidential compute on testnet

