# **VM on Golem: A Funding Proposal**

**Project Codename:** VM on Golem  
**Slogan:** A three-command path to plain virtual machines on the Golem Network

**Applicant(s):**

-   **Phillip** – Founder & Sole Developer
-   **Discord:** @phillip
-   **GitHub:** github.com/cryptobench

**Date of Submission:** Sep 16, 2025

---

### **1. Introduction: A Clearer Path Forward**

Over the last seven years, Golem has explored multiple approaches to decentralized compute and built up a wealth of knowledge. Along this journey, one message has come through consistently from both the community and new users: they want something simple.

When newcomers open the documentation, many feel overwhelmed. They often expect to begin with a few straightforward commands, but instead face a steep learning curve. I’ve seen this sentiment repeated time and again in conversations over the years.

VM on Golem is a focused response to that feedback. It delivers standard Ubuntu virtual machines with the predictability developers expect from mainstream clouds, while retaining the advantages of an open, decentralized marketplace.

At present, onboarding requires navigating extensive documentation and complex SDK examples. Our Python SSH sample alone runs over 130 lines for something as fundamental as a login. Limited requestor activity reflects what we hear from the market: developers want a simpler, more direct approach.

With this approach of provisioning a plain, standard VM, people get exactly what they expect when they try Golem: a normal Ubuntu server they can use however they like. It behaves like any VPS, which means workloads that run elsewhere will run here. That makes one-to-one migration of services and Kubernetes clusters possible without modification.

This principle also guides our own operations. Our Golem DB infrastructure currently runs on Hetzner, and we are actively testing other clouds to ensure we can bring our systems online quickly if Hetzner ever changes its policies. What matters most to us, and to other builders, is the ability to move workloads directly onto new infrastructure without adapting to a bespoke stack. That is the exact challenge VM on Golem is built to solve.

The goal of this project is to make the first ten minutes on Golem effortless. A user should be able to discover a provider, create a VM, and connect via SSH with three self-explanatory commands. The flow is designed so most users can begin without reading documentation, keeping the focus on building rather than learning new concepts.

---

### **2. The Solution: Focused on Simplicity**

It has become clear that users expect a simple entry point to Golem: run a few commands and get a virtual machine. VM on Golem is designed to meet this expectation directly by providing an exact 1:1 clone of a virtual machine, just as if it were rented from any other cloud provider.

This commitment to simplicity gives builders the freedom to run what they want, using the tools they already know. They are not locked into a specific SDK or a novel method of distributing work. Instead, they get a standard, reliable building block that the entire industry uses. Existing data pipelines, web servers, or Kubernetes clusters can be moved from any other cloud to VM on Golem and are expected to work out of the box.

Getting started is as simple as it should be. Install the CLI once, then rent a machine with three self-explanatory commands:

-   `pip install request-vm-on-golem` to install the requestor toolkit.

1.  `golem vm providers` to list all available providers and their specs.
2.  `golem vm create --provider-id ... --cores 2 --memory 2 --disk 10` to provision the machine.
3.  `golem vm ssh vm_name` to gain instant access once it's ready.

No lengthy explanations are needed. This is the user experience people expect.

#### **Provider Activation Walkthrough**

The provider experience mirrors this simplicity. After a one-time installation, a new host can join the network with two short commands:

```bash
# One-time install from PyPI
pip install golem-vm-provider

# Go live and publish pricing
golem-provider start --network testnet
golem-provider pricing set --usd-per-core 12 --usd-per-mem 4 --usd-per-disk 0.1
```

These two commands encapsulate the activation process: start the service, then publish pricing.

#### **A Focused Architecture for Simplicity**

To achieve the level of simplicity and reliability described above, VM on Golem is built on a dedicated architecture designed specifically for this purpose.

Rather than layering on top of the existing Yagna implementation, this project follows a clean-slate approach. This choice makes it possible to avoid the inherited complexity and limitations of the current system, while ensuring that the design is optimized around the single goal of provisioning and managing virtual machines.

The outcome is a streamlined and stable foundation, engineered from the ground up to do one thing exceptionally well: provide fast, straightforward, and reliable access to decentralized virtual machines. By narrowing the scope, VM on Golem can deliver on the long-standing promise of accessible decentralized compute without being constrained by earlier architectural decisions.

---

## **4. Architecture & Technical Workflow**

The architecture of VM on Golem is deliberately simple. Providers expose a stable API on the public internet, and requestors connect directly to rent machines. We don’t attempt NAT punching or home-router workarounds. Instead, providers must port-forward the necessary interfaces, prove their ports are reachable, and keep them open. This sets a clear expectation: if you want to earn as a provider, you need a proper setup. On Golem, supply has always been far greater than demand, so raising the bar does not threaten the marketplace. It filters out low-reliability hosts while attracting providers who understand uptime, bandwidth, and service quality—the people we want powering VM on Golem.

### **4.1. End-to-End Overview**

```mermaid
sequenceDiagram
    participant Req as "Requestor CLI / GUI"
    participant Wallet as "Wallet Client"
    participant GB as "Golem Base"
    participant Prov as "Provider API"
    participant PM as "Port Manager & Proxy"
    participant MP as "Multipass"
    participant VM as "Ubuntu VM"
    participant DNS as "Dynamic DNS"
    participant PC as "Port Checker"
    participant SC as "Stream Contract"
    participant Ver as "Verifier Nodes"

    Req->>GB: List providers
    GB-->>Req: Advertisements & pricing
    Req->>Wallet: Request stream funding
    Wallet->>SC: Create or top up stream
    SC-->>Prov: Funding event emitted
    Req->>Prov: Submit provision request
    Prov->>PM: Allocate ports & configure proxy
    PM->>PC: Verify reachability from edge nodes
    PM->>DNS: Publish dynamic DNS record
    Prov->>MP: Launch VM workload
    MP->>VM: Boot image & configure networking
    Req->>PM: SSH / service access via forwarded port
    SC->>Ver: Expose stream state for checks
    Ver->>VM: Issue attestation challenge
    VM-->>Ver: Return signed measurements
    Ver-->>SC: Verdict continue or stop
    SC-->>Prov: Stream GLM while VM healthy
    Prov->>GB: Update advertisement capacity
```

### **4.2. Provider Node**

Providers install a dedicated node built around **Multipass**, our launch hypervisor of choice because it runs on macOS, Linux, and Windows out of the box. The node is responsible for presenting the host to the network, advertising capacity, and delivering VM instances on demand.

When the node starts, it reserves the portion of CPU, memory, and storage dedicated to Golem workloads. A local agent tracks these resources in real time and exposes a secure HTTPS API to requestors. Whenever free capacity changes—after a VM is created or destroyed—the node publishes an updated advertisement to **Golem Base** so the marketplace always sees accurate numbers. Each advertisement includes the provider’s public identifier, live resource availability, supported CPU architecture, country of operation, pricing in both USD and GLM, and the payments network the provider accepts.

Onboarding also includes an automated **port verification** step. The node coordinates with a port-checker service to confirm that the provider’s public IP and forwarded SSH range are reachable from multiple regions. Nodes that fail this check remain invisible until the operator fixes their routing, keeping the pool limited to operators with reliable connectivity. Once verified, the node publishes its open port inventory alongside compute resources. Requestors can allocate these ports to expose services from their VMs, with a built-in firewall interface that mirrors the simplicity of cloud dashboards.

#### **Provider Node Components**

```mermaid
sequenceDiagram
    participant ProvSvc as "Provider Service"
    participant PortMgr as "Port Manager"
    participant PortCheck as "Port Checker"
    participant VMAdapter as "Multipass Adapter"
    participant Multipass as "Multipass CLI"
    participant ProxyMgr as "Proxy Manager"
    participant ResTracker as "Resource Tracker"
    participant AdvSvc as "Advertisement Service"
    participant Advert as "Golem Base Advertiser"
    participant GBase as "Golem Base"
    participant StreamMon as "Stream Monitor"
    participant StreamCon as "Stream Contract"

    ProvSvc->>PortMgr: initialize()
    PortMgr->>PortCheck: Verify provider + SSH ports
    PortMgr-->>ProvSvc: Verified port inventory
    ProvSvc->>VMAdapter: Sync existing VMs
    VMAdapter->>Multipass: Inspect running instances
    Multipass-->>VMAdapter: VM resource snapshot
    VMAdapter->>ProxyMgr: Ensure proxy mappings
    VMAdapter-->>ProvSvc: Multipass ready
    ProvSvc->>ResTracker: Register capacity updates
    ResTracker-->>AdvSvc: Trigger advertisement update
    AdvSvc->>Advert: Start broadcast loop
    Advert->>GBase: Publish resource advertisement
    ProvSvc->>StreamMon: Start stream reconciliation
    StreamMon->>StreamCon: Poll active streams
    StreamCon-->>StreamMon: Stream state & balances
    StreamMon->>ProvSvc: Flag unpaid or halted VMs
    ProvSvc->>VMAdapter: Terminate flagged VM
    VMAdapter->>ProxyMgr: Release port mapping
    VMAdapter->>ResTracker: Adjust resource totals
```

### **4.3. Payments**

Before a rental starts, requestors deposit funds into an on-chain payment stream (based on **EIP-1620 style streaming**). Providers earn continuously—paid by the second—as long as the VM runs. If the stream stops, the VM stops.

When a VM is first rented, the requestor must deposit a minimum amount of funds into the contract. This deposit defines the “runway” for how long the VM can stay alive. If more runtime is needed, the requestor can top up the stream to extend the lease.

To prevent abuse, we are designing a **verifiable execution layer** powered by verifier nodes. These nodes act as decentralized oracles: they independently check whether a VM is actually running and can halt the payment stream if the VM is proven to be down.

#### **Streaming Payments Flow**

```mermaid
sequenceDiagram
    participant R as Requestor CLI
    participant SC as Stream Contract (Polygon)
    participant PV as Provider Node
    participant VN as Verifier Nodes
    participant VM as Provisioned VM

    R->>SC: Create stream & deposit runtime
    SC->>PV: Emit funding event / allow provisioning
    PV->>VM: Launch via Multipass & proxy setup
    loop Continuous verification
        VN->>VM: Attestation challenge (Keylime/vTPM)
        VM-->>VN: Signed measurements
        VN->>SC: Verdict (continue or halt)
        SC->>PV: Stream GLM per second while healthy
    end
    R->>SC: Top up or close stream
    SC->>PV: Stop payments when funds exhausted
    PV->>VM: Shutdown & cleanup on stream stop
```

#### **How the Check Works**

Each VM runs with a **virtual Trusted Platform Module (vTPM)**, provided by tools like **swtpm** when using QEMU/KVM. Inside the VM, an agent (based on **Keylime**) continuously measures the VM’s state (boot sequence, configuration, integrity) and exposes an attestation API.

-   **Verifier nodes** periodically send cryptographic challenges to the VM’s Keylime agent.
-   The agent signs responses with the vTPM, proving they come from the correct, untampered VM.
-   The verifier nodes validate the signatures and compare the measurements against a **“golden baseline”**—a reference fingerprint of what a healthy, trusted VM should look like.

Multiple verifiers perform this check, and their results are aggregated into a **consensus verdict** (e.g., through a Chainlink Decentralized Oracle Network).

#### **Attestation & Oracle Flow**

```mermaid
sequenceDiagram
    participant Req as "Requestor"
    participant PV as "Provider Node"
    participant SC as "Stream Contract"
    participant Oracle as "Oracle Coordinator"
    participant VM as "VM Attestation Endpoint"
    participant TPM as "Sealed Signing Key"

    Req->>PV: Provision VM & publish attestation endpoint
    Req->>SC: Register VM public key & endpoint
    SC-->>Oracle: Emit verification job metadata
    loop Scheduled checks
        Oracle->>VM: Send random challenge nonce
        VM->>TPM: Sign challenge with sealed key
        TPM-->>VM: Signature (proof VM holds key)
        VM-->>Oracle: Return signature + state hash
        Oracle->>Oracle: Verify using registered public key
        alt Signature valid
            Oracle->>SC: Report VM healthy
            SC-->>PV: Maintain payment stream
        else Signature invalid or timeout
            Oracle->>SC: Report VM failed attestation
            SC-->>PV: Halt payments & flag VM
        end
    end
```

The oracle only accepts signatures that match the requestor-registered public key, so any deviation in the VM image or key material immediately fails attestation and halts payouts.

#### **Smart Contract Integration**

-   If the verifier network confirms the VM is running, the on-chain payment stream continues.
-   If the VM fails attestation or stops responding, the consensus report triggers the contract to halt payments and optionally refund unused funds to the requestor.

This ensures providers are only paid for live, verifiable machines, and requestors never fund dead VMs. By combining continuous payment streaming with cryptographic attestation, VM on Golem becomes a self-policing, decentralized compute marketplace.

---

### **4.4. Confidential Compute & Secure Storage**

Opening the network to commercial workloads means assuming the host is untrusted. Technologies such as **AMD SEV** and **Intel TDX** already protect the VM’s memory while it runs, but they do not shield the disk when the VM shuts down. To close that gap we combine hardware-backed confidential compute with **full disk encryption** and **attestation-driven key release**, ensuring the VM stays protected in every state.

#### **The Workflow**

1.  The tenant builds the VM image with **LUKS full disk encryption** enabled. Without the key, the image is unreadable.
2.  The image includes a minimal `initramfs` containing the tools to unlock the disk and a lightweight attestation agent (e.g., a Keylime client).
3.  The provider boots the VM under SEV/TDX. The `initramfs` runs inside the hardware-encrypted enclave, while the main disk stays locked.
4.  The attestation agent requests a signed measurement from the CPU and forwards it to a remote **Key Server** controlled by the workload owner.
5.  The Key Server verifies the signature and measurements. If they match the golden baseline, it releases the LUKS key; otherwise it refuses.
6.  The `initramfs` unlocks the volume and hands control to the OS. The key never touches disk and only exists briefly in protected memory.

#### **What the Host Can See**

-   **While running:** only encrypted memory guarded by SEV/TDX.
-   **While stopped:** only an encrypted disk image (LUKS).
-   **At boot:** keys are released only if attestation proves the VM is genuine.

This layered model delivers a zero-trust lifecycle: secrets remain private while the VM runs, when it pauses, and even when it is powered off.

---

### **4.5. Dynamic DNS Backed by Golem Base**

Raising the bar on networking introduces another reality: many community operators rely on residential or prosumer connections where the public IP can change. A traditional DNS record pointed straight at the host will eventually fail—`play.ourgame.com` suddenly resolves to the wrong place and the service goes dark.

To solve this, we plan to turn **Golem Base into a decentralized Dynamic DNS layer** that absorbs IP changes in seconds.

The domain owner still buys `ourgame.com` through their registrar. The only difference is that they delegate their authoritative name servers to Golem gateways (e.g., `ns1.golembase.net`, `ns2.golembase.net`). These gateways answer DNS queries using real-time state pulled from Golem Base instead of flat zone files.

Providers push IP updates into Golem Base whenever their address changes, with authority anchored in a **Golem Base L2 smart contract** that maps domain ownership to Ethereum keys. Only the legitimate key holder can publish updates, making hijacking impossible. When a user queries DNS, the gateway fetches the current record from Golem Base L3, wraps it in a valid DNS response, and sends it back.

The result is resilient DNS that works even for providers on dynamic IPs—without breaking the requestor’s expectation of stable, human-readable domains.

---

## **5. The Requestor Experience**

### **5.1. Requestor Workflow**

The requestor experience stays true to the **“three commands to a VM”** promise:

1.  `golem vm providers` — query Golem Base for available providers, filter by resources or location.
2.  `golem vm create --provider-id <id> --cores <n> --memory <gb> --disk <gb>` — the CLI deposits funds into the stream, shares the ID with the provider, and triggers provisioning once confirmed.
3.  `golem vm ssh <name>` — connect directly to the machine through the provider’s forwarded port.

Connection details are stored locally, so reconnecting or tearing down later takes just one command.

### **5.2. Command Journey**

```mermaid
sequenceDiagram
    participant User as "Developer"
    participant CLI as "golem CLI"
    participant GB as "Golem Base"
    participant SC as "Stream Contract"
    participant API as "Provider API"
    participant VM as "Provisioned VM"

    User->>CLI: Run `golem vm providers`
    CLI->>GB: Fetch provider advertisements
    GB-->>CLI: Return listings + pricing
    CLI-->>User: Present sorted providers
    User->>CLI: Run `golem vm create`
    CLI->>SC: Create or top up payment stream
    SC-->>API: Emit funding authorization
    CLI->>API: Submit VM specification
    API-->>CLI: Respond with VM ready details
    User->>CLI: Run `golem vm ssh`
    CLI->>VM: Establish SSH via provider proxy
    VM-->>CLI: Open shell session
    CLI-->>User: Interactive access
    User->>CLI: Optional `topup` or `stop`
    CLI->>SC: Adjust or close stream
```

### **5.3. Requestor Web Marketplace Plan**

We are building a browser-native marketplace that brings the full VM lifecycle into a MetaMask-enabled dashboard. Instead of bootstrapping with CLI tooling, requestors will open a single page, connect their wallet, and step through discovery, provisioning, and management without leaving the browser.

The experience is organized into a handful of focused surfaces:

-   A **project dashboard** gives requestors an immediate view of live machines, stream health, and per-project activity.
-   The **provider marketplace** lists advertisements with filters for vCPU, RAM, storage, geography, platform, and budget caps so requestors can zero in on the right host before they stake funds.
-   A guided **rent wizard** walks newcomers through region selection, resource sizing, and SSH key validation before handing off to a MetaMask-powered rent dialog that opens the payment stream and provisions the VM.
-   The **rentals command center** keeps track of running and terminated machines, streaming live status updates, ready-to-copy SSH commands, and safe termination controls.
-   A dedicated **streams console** exposes hourly spend, remaining runway, and preset or custom length top-ups.
-   The **settings workspace** stores discovery profiles, contract overrides, currency display preferences, and SSH keys so the web client stays in sync with the rest of the stack.
-   A detailed **VM page** consolidates provider metadata, access information, stream state, and lifecycle actions for each instance.

Together, these surfaces translate the "three commands" promise into a point-and-click workflow: land on the dashboard, launch the wizard, approve the payment stream, receive SSH details, and monitor runtime from the same tab.

---

## **6. The Provider Experience: The "Battlestation" GUI**

The Provider GUI is the operator’s control room. It presents live supply, revenue, and health at a glance, with one-click actions to manage VMs, ports, listings, and payouts. The goal is a Grafana-style dashboard—dark theme, dense but readable panels—while keeping every control self-explanatory.

#### **Purpose**

Providers need three things in one place: a truthful view of what’s running, simple controls to change it, and confidence that payments are flowing. The GUI connects directly to the local Provider Node (Multipass adapter, Port Manager, Advertiser, Stream Monitor) and pulls verified state from Golem Base so what you see on screen matches what the marketplace sees.

#### **Home Dashboard**

The landing screen is a high-signal overview that updates in real time:

-   **Revenue today / this week / month** with a tiny sparkline and a “pending vs. withdrawn” split.
-   **Active VMs** and **utilization gauges** (vCPU, RAM, storage) against the reserved Golem capacity.
-   **Stream health** showing running streams, average runway left, halted streams, and auto-shutdowns triggered.
-   **Port status** with counts for open/closed ports.
-   **Alerts** for anything actionable: low balance in the provider wallet, failing attestation, or disk pressure.

Every card links to a deeper view and exposes a single safe action (e.g., “Withdraw,” “Pause listings,” “Open Port Manager”).

#### **VM Fleet**

A table and detail pane for all instances running under Multipass on this host:

-   **Per-VM metrics** (CPU %, RAM %, disk IO, network throughput, load average, TPS if it’s a known service like Minecraft).
-   **Lifecycle controls** (start, stop, reboot, snapshot, destroy) with confirmations and guardrails if a stream is still active.
-   **SSH keys & access** showing injected keys, and the exact endpoint presented to the requestor.
-   **Tags & notes** so operators can annotate long-running tenants or internal SKUs.

Behind the scenes the GUI reads from the Multipass adapter and the Resource Tracker, and writes back via the Provider API to keep state consistent.

#### **Port & Network**

A dedicated panel for everything on the wire:

-   **Mapping list** of external ports → VM:port, including protocol, status, last connection time, and byte counters.
-   **Dynamic DNS** records currently advertised via Golem Base, with expiry/TTL and the last on-chain update hash.

Changes here flow through the Port Manager; the GUI blocks any operation that would strand an active stream without a confirmation.

#### **Listings & Pricing**

Everything the marketplace sees in one page:

-   **Live advertisement** exactly as it appears in Golem Base: public identifier, region, CPU architecture, available cores/RAM/disk, accepted payment networks, and price in USD and GLM.
-   **Price editor** that lets operators set per-unit pricing (vCPU-hour, GB-RAM-hour, GB-storage-day) and an optional minimum deposit.
-   **Publish / pause** toggles with reason codes (maintenance, bandwidth cap reached, policy change).
-   **Templates** for common bundles (e.g., “2 vCPU / 4GB / 40GB”) to standardize offers and speed up updates.

When you hit **Save**, the Advertiser pushes an updated ad to Golem Base; the page shows the transaction/commit reference so operators can verify propagation.

#### **Streams & Payouts**

A payments view that’s easy to reconcile:

-   **Active streams** with per-second accrual, counterparty, start time, and estimated runway left based on current balance.
-   **Events** such as top-ups, halts (by verifier or by requestor), and auto-shutdowns mapped to VM lifecycle events.
-   **Withdrawals** for settled balances with fee estimates and a ledger of completed payouts.
-   **Wallet status** including network, addresses in use, and quick actions (copy, view in explorer).

If a stream halts or runs dry, the GUI can trigger a graceful VM stop with a note stored for audit.

#### **Health, Alerts, and Automation**

Operators shouldn’t need to babysit:

-   **Threshold alerts** for disk > 85%, RAM pressure, abnormal egress, or failing port checks.
-   **Policy automations** such as “pause listings if external RTT > 150ms for 5 minutes” or “refuse new VMs if free disk < 20GB.”
-   **Maintenance windows** to auto-pause advertisements and drain new requests, with an optional message shown in the marketplace.

Alert definitions are stored locally; summaries and key state changes are mirrored to Golem Base where relevant (e.g., listing pauses).

#### **Audit & History**

Every important action is logged:

-   **Operator actions** (who paused a listing, who opened a port, who destroyed a VM).
-   **System actions** (verifier halt, auto-shutdown, DNS updates).
-   **External signals** (advertisement commits, stream events) with their IDs.

Logs are filterable, exportable, and include enough context to reproduce a timeline during support.

---

## **7. Adoption Strategy: Requestor Growth Concepts**

### **7.1. Minecraft Server dApp**

<img width="1080" height="607" alt="image" src="https://gist.github.com/user-attachments/assets/add7f0b8-9f0d-4369-abd0-f38d025c8245" />
<img width="1080" height="606" alt="image" src="https://gist.github.com/user-attachments/assets/578f4a96-378d-4cb4-be83-0a4d74fc0226" />
<img width="1080" height="606" alt="image" src="https://gist.github.com/user-attachments/assets/1773a9e6-d333-4e98-a45e-e1705ad23042" />

Minecraft hosting is a natural proving ground for browser-first VM rentals. The audience is mostly younger players who are already used to the idea of running their own servers for friends. Many of them have also experimented with crypto wallets or tokens, which lowers the barrier to trying a service that relies on MetaMask for payments. Because Minecraft servers are relatively inexpensive and not mission-critical, they are an ideal first use case to showcase VM on Golem.

#### **Provisioning Flow**

The dApp translates the “three commands” promise into a browser-native workflow. A requestor connects their MetaMask wallet, chooses a server profile, and confirms the payment stream. From there, the system provisions the VM automatically: resources are allocated from a provider, the correct ports are opened, a Minecraft image is deployed, and a stable DNS record is published through Golem Base. Within minutes the requestor receives a hostname such as `play.username.golem.host` that can be shared directly with friends.

#### **Management Experience**

The management panel mirrors what players already expect from commercial Minecraft hosting services. The goal is to give users the same visual comfort they are used to, while abstracting away the underlying VM. Key elements include:

-   **Live console logs** streamed directly in the browser, showing chat messages, plugin activity, and server events.
-   **File browser** with upload/download support for editing `server.properties`, uploading worlds, and managing resource packs.
-   **World management** tools for backups, restores, and scheduled saves.
-   **Plugin and mod handling** with drag-and-drop uploads for Forge and Fabric servers.
-   **Performance metrics** such as CPU, RAM, ticks per second (TPS), and player count.

The design draws inspiration from the ultra-minimal dashboards popular in the Minecraft hosting community. Interfaces are visually lightweight, with clear buttons and no clutter—players should feel instantly at home.

#### **Payment & Control**

Streaming payments keep the experience aligned with the underlying economics of VM on Golem. The dApp displays current spend and remaining runway in real time, with a single button to top up the stream. If a server is left idle, requestors can enable an automatic pause policy that saves the world and stops the VM when no players are online, preventing unnecessary costs. If the verifier network reports that the VM is no longer running, the stream is halted to protect the requestor from paying for downtime.

#### **Why It Matters**

This flow creates a low-friction entry point into Golem. A player can go from connecting their wallet to running a Minecraft world in a single session, without touching cloud infrastructure or command-line tools. It taps into a community that is young, curious, and already experimenting with crypto, introducing them to Golem through an accessible and fun use case. From there, moving from a Minecraft server to a plain VM becomes trivial—the same provisioning flow, just without the Minecraft wrapper.

### **7.2. Decentralized VPN dApp**

<img width="1344" height="768" alt="image" src="https://gist.github.com/user-attachments/assets/b08ee5df-067d-4648-b297-81ad0a41f4d3" />

A decentralized VPN is the next natural step in showcasing VM on Golem. The idea is to ship a lightweight local installer with a graphical interface that makes connecting to the network as easy as launching a game client. Payments are handled through a Web3 wallet, keeping the model consistent with other requestor flows. Under the hood, the VPN will rely on **WireGuard**, chosen for its performance, simplicity, and strong cryptography.

#### **Provisioning Flow**

The application opens with a minimal panel inspired by the same design principles as the Minecraft dApp: clean layout, two or three obvious actions, and a focus on immediacy. A requestor connects their MetaMask wallet, browses available providers, and selects the endpoint they want to connect through. When the requestor confirms, the app provisions a VM from the chosen provider, configures WireGuard, and automatically establishes the tunnel. Within seconds the VPN is active, with no manual configuration files or command-line steps required.

#### **Provider Discovery**

The marketplace view is tailored for VPN-specific criteria. Instead of CPU or RAM, requestors see:

-   **Bandwidth capacity** offered by each provider.
-   **Geolocation** options for region-specific browsing.
-   **Latency measurements** for selecting the fastest nodes.
-   **Policy flags** such as whether the provider allows torrenting or blocks certain traffic.

These parameters allow requestors to choose endpoints that match their needs—whether it’s streaming content abroad, protecting privacy on public Wi-Fi, or running traffic through high-bandwidth nodes for downloads.

#### **Management Experience**

Once connected, the application displays a clear dashboard showing:

-   Current VPN status (connected / disconnected).
-   Selected provider and endpoint location.
-   Real-time bandwidth usage and session runtime.
-   Remaining payment runway based on the active stream.

From here, the requestor can disconnect, switch providers, or top up their stream directly. The focus is on simplicity: one page that manages the entire VPN lifecycle without technical complexity.

#### **Payments & Control**

As with other VM on Golem workloads, billing is handled through **per-second payment streaming**. The requestor sees current spend and remaining balance, and can extend their session by topping up the stream. This approach keeps the incentives aligned: providers are rewarded fairly for uptime and throughput, while requestors only pay for the time they are actively connected. If the verifier network flags the endpoint as unhealthy, the stream halts automatically.

#### **Why It Matters**

VPNs are a proven consumer service with clear demand, but today they require centralized operators, subscription lock-ins, and opaque trust models. A decentralized VPN on Golem replaces that with open discovery, transparent provider metadata, and pay-as-you-go economics. The installer abstracts all the complexity: connect wallet, pick a node, click connect. By reducing the flow to something as simple as a music-streaming app login, we open the door for mainstream users to engage with Golem infrastructure—this time not for gaming, but for everyday privacy and security.

---

## **8. Community Impact & Support**

The concept of VM on Golem has been shared internally within our Discord, and multiple people have come out and said that they support this idea, and this is what they expect from Golem Network.

One example quote: _"Yes, definitely interested to use it. I dont want to read through lot of docs to rent rigs lol. I prefer something simple like few lines of copy paste or UI to rent machines."_

_"I'd agree on that. Well I'm in the phase of reading whatever I can find on your web page. But yes, if you plan to make it more available to regular/non-coding-ninja experts, that would work for me as well 🙂 Or even a couple of links "dear user, first learn how to write code here XYZ, then here's a video on how to rent machines". @Phillip_golem you have my vote! 🙂"_

_"@Phillip_golem I think that your VM on Golem project can be a big hit!! Good luck 🤞🏿🤞🏿"_

Sources:  
[https://discord.com/channels/684703559954333727/773872812091768852/1412856551492030485](https://discord.com/channels/684703559954333727/773872812091768852/1412856551492030485)  
[https://discord.com/channels/684703559954333727/773872812091768852/1412857516898910413](https://discord.com/channels/684703559954333727/773872812091768852/1412857516898910413)  
[https://discord.com/channels/684703559954333727/773872812091768852/1341446378890461288](https://discord.com/channels/684703559954333727/773872812091768852/1341446378890461288)

---

## **9. Funding Structure & Payment Scheme**

**Date:** Sep 16, 2025

This proposal seeks funding for Phases 6 through 11, building on the foundation already completed in Phases 1–5. The model combines a fixed monthly salary in EUR with milestone-based rewards paid in GLM tokens. The salary ensures sustained focus, while milestone rewards are unlocked in stages tied to clear, verifiable outcomes.

The aim of this funding is simple: to bring Golem to adoption. After more than eight years of development, users are still asking for the same thing — a standard VM they can rent in a few commands. VM on Golem is designed to deliver exactly that, removing unnecessary complexity and providing the entry point the community has been waiting for.

*Note: All GLM token rewards are calculated at a reference rate of €0.21 per GLM. Final amounts may be adjusted to reflect the prevailing market rate at the time of agreement.*

---

### **Proposed Model: Balanced Salary + Performance-Gated Milestones**

* **Monthly Salary:** €7,000

This provides baseline stability. The majority of rewards are tied to milestone delivery, so the larger upside only comes with continued progress.

**Milestone Rewards:**

| Phase        | Focus                         | Timeline     | Status        | Payout (GLM)      | Success Criteria                                                                                                                                                                                                                          |
| :----------- | :---------------------------- | :----------- | :------------ | :---------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 1**  | Core Infrastructure           | Feb 2025     | Complete      |                   | CLI can provision a VM on testnet (`golem vm create`) and connect via SSH (`golem vm ssh`); teardown works end-to-end.                                                                                                                    |
| **Phase 2**  | Provider API Hardening        | Feb 2025     | Complete      |                   | Provider node runs 24/7 without manual restarts; health checks and watchdog auto-recovery in place; readiness/liveness endpoints exposed.                                                                                                 |
| **Phase 3**  | Requestor API & Orchestration | Feb 2025     | Complete      |                   | API supports create/list/stop/destroy; audit events recorded immutably; flows match CLI parity; idempotent retries confirmed.                                                                                                             |
| **Phase 4**  | Golem DB Integration          | Feb 2025     | Complete      |                   | Providers publish ads with live capacity and pricing; requestors can filter and fetch ads; propagation < 10 seconds.                                                                                                                      |
| **Phase 5**  | Smart-Contract Payments       | Mar 2025     | Testnet-ready |                   | Per-second payment streaming live on testnet; top-up extends runway; closing stream halts accrual; events visible on-chain.                                                                                                               |
| **Phase 6**  | Requestor GUI Marketplace     | **Dec 2025** | Next          | **190,476 GLM**   | Public web app: wallet connect, provider search with filters, rent wizard (region, sizing, SSH key), rentals list with lifecycle actions, stream top-up/close. ≥10 unique requestors use it.                                              |
| **Phase 7**  | Verifier Network              | **Feb 2026** | Next          | **380,952 GLM**   | Verifier nodes deployed on public testnet; can challenge VMs via attestation; halt streams if consensus marks VM unhealthy. ≥25 providers integrated.                                                                                     |
| **Phase 8**  | Provider GUI Desktop          | **Apr 2026** | Next          | **761,905 GLM**   | Cross-platform desktop app (Win/Mac/Linux) showing provider revenue, utilization gauges, VM lifecycle controls (start/stop/reboot/snapshot), port management, pricing editor, payout withdrawals. ≥25 providers actively using it.        |
| **Phase 9**  | Requestor Minecraft dApp      | **Jun 2026** | Next          | **1,523,810 GLM** | Browser-native dApp: wallet connect, choose Minecraft profile, confirm payment stream, VM auto-provisioned with Minecraft image + DNS hostname; management panel with logs, file browser, backups, mod uploads. ≥100 servers provisioned. |
| **Phase 10** | VPN dApp                      | **Aug 2026** | Next          | **3,047,619 GLM** | Desktop VPN client: wallet connect, select provider by region/bandwidth, approve stream, auto-configured WireGuard tunnel; dashboard shows session runtime, bandwidth usage, remaining runway. ≥250 paying sessions provisioned.          |
| **Phase 11** | Confidential Compute          | **Oct 2026** | Next          | **6,095,238 GLM** | VM boots with AMD SEV/Intel TDX + full disk encryption; attestation-driven key release; verified demo showing keys only released after attestation passes. ≥3 independent teams run workloads.                                            |

* **Total Potential Compensation:** €84,000 (Annual Salary) + **12,000,000 GLM** (Milestones)

---

### **Rationale**

The funding request is ambitious because the vision is ambitious. VM on Golem is intended to be the product that finally matches what users have been asking for and creates the missing bridge to adoption. It represents a turning point — the chance to position Golem once again among the leading projects in the space, with the relevance and visibility we last had when Golem was ranked in the top 10 on CoinMarketCap back in 2017.

The milestone structure provides accountability. Rewards are tied to defined phases, and the larger amounts only unlock in later stages. This keeps progress measurable and ensures alignment between funding and delivery.

I have been part of Golem for more than seven years, and there is nobody else who carries that kind of continuity. In that time, I have seen team leader after team leader come and go. They arrived with new plans and good intentions, but none of them had the courage to make the radical decisions that could actually move Golem forward. Most avoided speaking directly with the community, which meant they were always building in a vacuum. They never really understood what users wanted, because they never asked.

I did. For me, this has not been a side project or a passing role. I have lived and breathed Golem every single day, through its toughest moments and its quietest years. I have spent thousands of hours listening to users, reading their frustrations, answering their questions, and understanding their needs. I carry seven years of accumulated knowledge, impressions, and unfiltered feedback. I have seen everything, I have heard everything, and I know exactly what the community has been asking for — because I have been there, listening, when others were not.

That experience is not replaceable. It is the reason I am confident in what I am building with VM on Golem, and why I know it will resonate with the people who matter most: the users.

This funding structure reflects how I work best: a steady salary for stability, with meaningful rewards tied directly to milestones. For Golem, it means resources are only committed if the work continues to move forward.
