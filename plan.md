# VM on Golem: Milestone Plan

**Project:** VM on Golem
**Tagline:** A three-command path to plain virtual machines on the Golem Network
**Version:** 1.0
**Last Updated:** December 2025

---

## Executive Summary

This document outlines the complete milestone plan for VM on Golem across all phases. Each phase includes timeline, high-level acceptance criteria, and definition of done.

### Vision

Over the last seven years, Golem has explored multiple approaches to decentralized compute. One message has come through consistently from both the community and new users: they want something simple.

VM on Golem is a focused response to that feedback. It delivers standard Ubuntu virtual machines with the predictability developers expect from mainstream clouds, while retaining the advantages of an open, decentralized marketplace.

The goal is to make the first ten minutes on Golem effortless. A user should be able to discover a provider, create a VM, and connect via SSH with three self-explanatory commands:

```
golem vm providers                                              # List available providers
golem vm create --provider-id <id> --cpu 2 --memory 4 --disk 20 # Provision a VM
golem vm ssh <name>                                             # Connect instantly
```

This principle extends to providers as well. After installation, a provider can join the network with:

```
golem-provider start
golem-provider pricing set --cpu 12 --memory 4 --storage 0.1
```

No lengthy explanations needed. This is the user experience people expect.

### Why Virtual Machines Matter

Virtual machines are the foundation of the modern internet.

Almost everything we use today runs inside a VM: cloud servers, VPS instances, CI systems, databases, VPNs, bots, storage services, internal tools, and entire Kubernetes clusters. Whether it's VirtualBox on a laptop, Hyper-V in an enterprise, or a rented VPS from a cloud provider, the model is always the same: a general-purpose machine with predictable behavior.

That predictability is the key strength of VMs. Users know what they are getting before they log in. They know which tools work, how to deploy software, and how to debug problems. Years of shared knowledge, documentation, and muscle memory are built around this model.

### The Problem Golem Faces Today

Golem does not currently offer a standard VM.

Instead, it exposes a custom execution environment that looks capable from the outside, but reveals sharp limitations once users start building on it. This creates several problems:

* Users bring expectations shaped by normal VMs, then run into constraints they didn't anticipate.
* Common tools and workflows do not work out of the box.
* Learning Golem means learning a special case, not applying existing knowledge.
* The gap between "what it looks like" and "what it can actually do" leads to frustration and churn.

This is not a branding issue or a documentation issue. It is a foundational mismatch between what developers expect and what the platform provides.

As long as Golem is not a normal VM environment, it will continue to limit:

* what users can run,
* how easily they can get started,
* and how far the ecosystem can extend.

### Feature Comparison

| Feature | Golem | VM on Golem |
|---------|:-----:|:-----------:|
| Complex SDK to learn | ✅ | ❌ |
| 1:1 migration from existing infrastructure | ❌ | ✅ |
| Outbound networking | ⚠️ | ✅ |
| Inbound networking | ❌ | ✅ |
| Simple to use | ❌ | ✅ |
| Provider port forwarding | ⚠️ | ✅ |
| Payment streaming | ❌ | ✅ |
| Confidential compute | ❌ | ✅ |
| Offline requestor | ❌ | ✅ |
| Windows/Mac provider support | ❌ | ✅ |

*⚠️ Partial or limited support*

### What VM on Golem Changes

VM on Golem introduces something deliberately boring: a VM that behaves exactly like the VMs people already know.

A VM on Golem is the same concept you get from:

* VirtualBox or Hyper-V,
* a VPS from a cloud provider,
* a raw Ubuntu server rented by the hour.

Nothing new to learn. No custom execution model. No hidden constraints.

Once that foundation is in place, everything else becomes possible without special casing:

* Run scripts directly on a raw server
* Host long-running services
* Deploy containers or Docker-based stacks
* Build and operate a Kubernetes cluster across multiple Golem providers
* Host Discord bots or backend services
* Store files or build an S3-compatible service
* 1:1 migration of services running on other cloud infrastructure directly onto VM on Golem provider nodes.

The point is not to define what users should build. The point is to stop limiting what they *can* build.

### Groundwork, Not a Single Feature

This proposal is not about a single application or vertical.

It lays the groundwork that allows *anything* to exist on the network. Once standard VMs are available, higher-level services become straightforward compositions rather than special projects.

Later phases in this roadmap demonstrate that clearly. For example, a decentralized VPN becomes possible not because VPNs are special, but because VMs are versatile. The same applies to storage, compute clusters, private services, and future ideas that are not yet defined.

VM on Golem is the foundation that removes artificial ceilings from the network. Everything built on top benefits from that decision.

### Architecture Principles

VM on Golem is built on a dedicated architecture designed specifically for simplicity and reliability:

- **Providers** expose a stable API on the public internet. Requestors connect directly to rent machines. Providers must port-forward the necessary interfaces and prove their ports are reachable.
- **Discovery** uses Arkiv, a decentralized on-chain registry where providers advertise resources with live capacity and pricing.
- **Payments** use per-second streaming on L2. Requestors deposit funds into a payment stream; providers earn continuously as long as the VM runs.
- **Verification** through a verifier network ensures providers are only paid for live, accessible VMs.

This raises the bar on provider quality while filtering out low-reliability hosts, attracting operators who understand uptime, bandwidth, and service quality.

### Note on KPIs

While KPIs were initially requested, this document uses acceptance criteria and definition of done as the primary success measures for each milestone. KPIs are better suited for ongoing operational metrics (uptime, user adoption, performance SLAs) rather than one-time development milestones. Each milestone is binary: either the acceptance criteria are met and demonstrable, or they aren't. This approach aligns with similar internal Golem funding arrangements (e.g., Neti) where acceptance criteria serve as the verification standard.

---

## Funding Structure

This proposal combines a fixed monthly salary in EUR with milestone-based rewards paid in GLM tokens. The salary ensures sustained focus, while milestone rewards are unlocked in stages tied to clear, verifiable outcomes.

Milestone payouts are structured to **double at each phase**, concentrating the largest rewards at the end of the roadmap. This reduces early-stage risk: initial phases cost relatively little to evaluate, and significant payouts only unlock after consistent delivery has been demonstrated. If progress stalls, exposure remains limited.

Accepting payment in GLM reflects confidence that this work will drive adoption, rebuild community engagement, and ultimately increase the token's value. This creates direct alignment: if the product succeeds, both parties benefit from the appreciation.

*Note: All GLM token rewards are calculated at a reference rate of €0.21 per GLM. Final amounts may be adjusted to reflect the prevailing market rate at the time of agreement.*

**Monthly Salary:** €7,000

**Total Potential Compensation:** €84,000 (Annual Salary) + **6,000,000 GLM** (Milestones)

---

## Milestone Overview

| Phase | Name | Target | Status | Payout (GLM) |
|-------|------|--------|--------|--------------|
| ~~1~~ | ~~Discovery Service~~ | ~~Feb 2025~~ | Complete | - |
| ~~2~~ | ~~Provider API~~ | ~~Feb 2025~~ | Complete | - |
| ~~3~~ | ~~Requestor API~~ | ~~Feb 2025~~ | Complete | - |
| ~~4~~ | ~~Arkiv Integration~~ | ~~Feb 2025~~ | Complete | - |
| ~~5~~ | ~~Smart Contract Payments~~ | ~~Mar 2025~~ | Complete | - |
| 6 | Requestor GUI Marketplace | January 2026 | Planned | 95,238 |
| 7 | Verifier Network | March 2026 | Planned | 190,476 |
| 8 | Arkiv DNS | April 2026 | Planned | 380,952 |
| 9 | Provider GUI Desktop | June 2026 | Planned | 761,904 |
| 10 | Decentralized VPN dApp | October 2026 | Planned | 1,523,808 |
| 11 | Confidential Compute | December 2026 | Planned | 3,047,622 |

---

## Completed Phases

### ~~Phase 1: Discovery Service~~

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

### ~~Phase 2: Provider API~~

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

### ~~Phase 3: Requestor API~~

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

### ~~Phase 4: Arkiv Integration~~

**Completed:** February 2025
**Focus:** Decentralized provider discovery

#### Acceptance Criteria

- [x] Providers publish advertisements with live capacity and pricing to Arkiv
- [x] Requestors can filter and fetch provider advertisements

---

### ~~Phase 5: Smart Contract Payments~~

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

Deliver a browser-native marketplace that brings the full VM lifecycle into a MetaMask-enabled dashboard. Instead of bootstrapping with CLI tooling, requestors open a single page, connect their wallet, and step through discovery, provisioning, and management without leaving the browser.

The experience translates the "three commands" promise into a point-and-click workflow: land on the dashboard, launch the rent wizard, approve the payment stream, receive SSH details, and monitor runtime from the same tab.

#### High-Level Acceptance Criteria

1. **Wallet Integration**
   - [ ] MetaMask detection and connection flow
   - [ ] Automatic chain switching to payments L2 network
   - [ ] ERC20 allowance checking and approval flow for GLM
   - [ ] Transaction signing for stream creation and top-ups
   - [ ] Support for both native ETH and ERC20 (GLM) streaming

2. **Provider Discovery**
   - [ ] Dual discovery modes: Arkiv (decentralized) and Central (legacy)
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
**Focus:** VM health attestation and payment protection

#### Description

Deploy a network of verifier nodes that monitor VM health and can halt payment streams for failed VMs, protecting requestors from paying for unavailable resources.

Verifier nodes act as oracles: they independently check whether a VM is actually running and can halt the payment stream if the VM is proven to be down. Multiple verifiers perform checks, and their results are aggregated into a consensus verdict. If the verifier network confirms the VM is running, the payment stream continues. If the VM fails attestation or stops responding, the consensus triggers the contract to halt payments.

This ensures providers are only paid for live, verifiable machines, and requestors never fund dead VMs.

#### High-Level Acceptance Criteria

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

### Phase 8: Arkiv DNS

**Target:** April 2026
**Payout:** 380,952 GLM
**Focus:** Decentralized dynamic DNS for providers with changing IPs

#### Description

Turn Arkiv into a decentralized Dynamic DNS layer for providers on residential or prosumer connections where public IPs can change. Domain owners delegate their authoritative name servers to Arkiv gateways, which answer DNS queries using real-time on-chain state instead of static zone files. Providers push IP updates on-chain, with ownership anchored in a smart contract. Only the legitimate key holder can publish updates.

#### High-Level Acceptance Criteria

1. **DNS Gateway Infrastructure**
   - [ ] Public authoritative name servers that domain owners can delegate to
   - [ ] Gateways resolve DNS queries using real-time Arkiv state
   - [ ] Standard DNS record types supported (A, AAAA, TXT)

2. **On-Chain Domain Registry**
   - [ ] Smart contract maps domain ownership to Ethereum keys
   - [ ] Only authorized key holder can publish updates (prevents hijacking)

3. **Dynamic IP Updates**
   - [ ] Providers can push IP updates to Arkiv when address changes
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

Deliver a desktop application for Windows, macOS, and Linux that serves as the provider's control room. The GUI presents live earnings, resource utilization, and VM health at a glance, with controls to manage VMs, ports, listings, and payouts.

Providers need three things in one place: a truthful view of what's running, simple controls to change it, and confidence that payments are flowing. The application connects directly to the local provider node and displays verified state so what operators see on screen matches what the marketplace sees.

#### High-Level Acceptance Criteria

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

Ship a user-friendly VPN application that provisions encrypted tunnels through Golem providers. Users connect their wallet, select a provider by region, approve a payment stream, and establish a VPN connection, all without manual configuration.

VPNs are a proven consumer service with clear demand, but today they require centralized operators, subscription lock-ins, and opaque trust models. A decentralized VPN on Golem replaces that with open discovery, transparent provider metadata, and pay-as-you-go economics.

The application abstracts all complexity: connect wallet, pick a node, click connect. By reducing the flow to something as simple as a consumer app, we open the door for mainstream users to engage with Golem infrastructure for everyday privacy and security.

#### High-Level Acceptance Criteria

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

Opening the network to commercial workloads means assuming the host is untrusted. Technologies such as AMD SEV and Intel TDX protect VM memory while running, but they do not shield the disk when the VM shuts down. To close that gap, we combine hardware-backed confidential compute with full disk encryption and attestation-driven key release, ensuring the VM stays protected in every state.

**What the host can see:**
- **While running:** only encrypted memory guarded by hardware isolation
- **While stopped:** only an encrypted disk image
- **At boot:** keys are released only if attestation proves the VM is genuine

This layered model delivers a zero-trust lifecycle: secrets remain private while the VM runs, when it pauses, and even when it is powered off.

#### High-Level Acceptance Criteria

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

