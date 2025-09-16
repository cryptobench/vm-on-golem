# VM on Golem
_A three-command path to plain virtual machines on the Golem Network_

**Applicant(s):**  
Phillip – Founder & Sole Developer (Discord: @phillip | GitHub: github.com/golemgrid)

**Date:**  
03/02/2025

---

## 1. Executive Summary
For eight years the Golem Network has explored decentralized cloud products, yet builders still face steep onboarding, constrained runtimes, and non-portable workloads. Over seven years inside the ecosystem I have consistently heard the same request: “Just let me rent a normal VM in a couple commands.” VM on Golem fulfills that request by exposing customizable Ubuntu virtual machines that behave exactly like the VPS instances developers use on AWS or DigitalOcean.

Requestors list providers, create a VM, and access it in up to three familiar CLI commands (`golem vm providers`, `golem vm create …`, `golem vm ssh …`). Providers price standard compute units and are paid via streaming contracts already integrated with Golem tooling. Funding from the Golem Ecosystem Fund will finalize UX polish, harden payment flows, and launch a dependable VM marketplace that finally meets community expectations.

---

## 2. Problem Statement
Over the last 7 years i've been using Golem Network, i've built probably the most advanced infrastructure around Golem Network, and i've helped and spoken with people in the community about everything. The problem with Golem Network right now is that its so hard to get started with it. You can't just come from one cloud and into Golem and expect things to work, no. You need to read tons of documentation, acquire funds from our testnet faucet (which btw often has issues and we have no monitoring on, so the #1 entrypoint for developers is often not working and hasnt for multiple years). Next to that you need to learn our SDK's, and I have yet to see one single person just state ah okay, looks simple. No, everyone has questions, the same bug that was found 4 years ago are still present and people are still hitting it. Now, once you finally figure out how to use Golem Network, you quickly find out oh, theres a limitation here, theres a limitation there, you caaaaan do this but it requires a workaround. All the time you need to invent hacky solutions because it simply doesn't work.

And finally, the thing that nobody has talked about the last 5 years: User experience. There has been absolutely 0 thought into developing some software thats simple to use for users. There's been to much faith in developers only being able to understand what a user wants.


---

## 3. Proposed Solution
Over the years i've come to conclusion that people want something simple. People expect that when they find Golem they can just run a few commands and now they have rented a virtual machine, but thats not the case. With my project codenamed VM on Golem, I believe that we've vastly overcomplicated what people want from a platform like Golem. People want a basic VM they can do stuff inside, and thats it, and thats what VM on Golem is. An exact clone 1:1 virtual machine just as if you rented a VM from another other cloud provider like AWS, DigitalOcean or Google Cloud. What this means is that people have the full freedom to build whatever they want on top. You can migrate your existing workloads from any other cloud on the internet to VM on Golem and it will just work out the box. 

How to get started with VM on Golem is incredibly simple. To rent a machine you would need to type 3 commands; `golem vm providers` to list all available providers and specs, `golem vm create --provider-id ... --cores 2 --memory 2 --disk 10` and once it has been provisioned you can type `golem vm ssh vm_name` to gain instant access to it. Thats it. The commands are self-explanatory and doesn't need any explanations. Thats what people want.

### Overview

### Key Features

### Integration with Golem Network
VM on Golem is its own custom architecture. There's nothing connected to the existing golem network (yagna). Yagna is a failed platform, and it doesn't make sense to re-use. It's vastly overengineered and suffering from tons of bugs, ux issues and much more. 

VM on Golem is its own fresh architecture.

### Differentiation

---

## 4. Objectives & Impact

### Project Goals

### Expected Outcomes

### Benefits to Golem & Ethereum

### Community Impact
The concept of VM on Golem has been shared internally within our discord, and multiple people has come out and said that they support this idea, and this is what they expect from Golem Network.

One example quote "Yes, definitely interested to use it. I dont want to read through lot of docs to rent rigs lol. I prefer something simple like few lines of copy paste or UI to rent machines."

"I'd agree on that. Well I'm in the phase of reading whatever I can find on your web page. But yes, if you plan to make it more available to regular/non-coding-ninja experts, that would work for me as well 🙂 Or even a couple of links "dear user, first learn how to write code here XYZ, then here's a video on how to rent machines". @Phillip_golem you have my vote! 🙂
"

"@Phillip_golem I think that your VM on Golem project can be a big hit!! Good luck 🤞🏿🤞🏿"

Sources: https://discord.com/channels/684703559954333727/773872812091768852/1412856551492030485
https://discord.com/channels/684703559954333727/773872812091768852/1412857516898910413
https://discord.com/channels/684703559954333727/773872812091768852/1341446378890461288

---



## VM on Golem – Architecture & Workflow

The architecture of VM on Golem is deliberately simple. Providers expose a stable API on the public internet, and requestors connect directly to rent machines. We don’t attempt NAT punching or home-router workarounds. Instead, providers must port-forward the necessary interfaces, prove their ports are reachable, and keep them open.

This sets a clear expectation: if you want to earn as a provider, you need a proper setup. On Golem, supply has always been far greater than demand, so raising the bar does not threaten the marketplace. It filters out low-reliability hosts while attracting providers who understand uptime, bandwidth, and service quality—the people we want powering VM on Golem.

---

## Provider Node

Providers install a dedicated node built around **Multipass**, our launch hypervisor because it runs on macOS, Linux, and Windows out of the box. The node is responsible for presenting the host to the network, advertising capacity, and delivering VM instances on demand.

When the node starts it reserves the portion of CPU, memory, and storage dedicated to Golem workloads. A local agent tracks these resources in real time and exposes a secure HTTPS API to requestors. Whenever free capacity changes—after a VM is created or destroyed—the node publishes an updated advertisement to **Golem Base (Golem DB)** so the marketplace always sees accurate numbers.

Each advertisement includes the provider’s public identifier, live resource availability, supported CPU architecture, country of operation, pricing in both USD and GLM, and the payments network the provider accepts. Because listings live on Golem Base, requestors can independently verify that the provider exists and is keeping their information fresh. Providers retain full control: they can adjust metadata, pause their listing, or change prices.

Onboarding also includes an automated **port verification** step. The node coordinates with a port-checker service to confirm that the provider’s public IP and forwarded SSH range are reachable from multiple regions. Nodes that fail this check remain invisible until the operator fixes their routing, keeping the pool limited to operators with reliable connectivity.

Once verified, the node publishes its open port inventory alongside compute resources. Requestors can allocate these ports to expose services from their VMs, with a built-in firewall interface (CLI first, GUI later) that mirrors the simplicity of cloud dashboards like Hetzner. Requestors will be able to toggle ports on or off, apply preset rules, and audit activity while the provider software enforces those decisions at the edge.

---

## Dynamic DNS Backed by Golem Base

Raising the bar on networking introduces another reality: many community operators rely on residential or prosumer connections where the public IP can change. A traditional DNS record pointed straight at the host will eventually fail—`play.ourgame.com` suddenly resolves to the wrong place and the service goes dark.

To solve this, we plan to turn **Golem Base into a decentralized Dynamic DNS layer** that absorbs IP changes in seconds.

The domain owner still buys `ourgame.com` through their registrar. The only difference is that they delegate their authoritative name servers to Golem gateways (e.g. `ns1.golembase.net`, `ns2.golembase.net`). These gateways answer DNS queries using real-time state pulled from Golem Base instead of flat zone files.

Providers push IP updates into Golem Base whenever their address changes, with authority anchored in a **Golem Base L2 smart contract** that maps domain ownership to Ethereum keys. Only the legitimate key holder can publish updates, making hijacking impossible. When a user queries DNS, the gateway fetches the current record from Golem Base L3, wraps it in a valid DNS response, and sends it back.

The result is resilient DNS that works even for providers on dynamic IPs—without breaking the requestor’s expectation of stable, human-readable domains.

---

## Payments

Before a rental starts, requestors deposit funds into an on-chain payment stream (based on **EIP-1620 style streaming**). Providers earn continuously—paid by the second—as long as the VM runs. If the stream stops, the VM stops.

When a VM is first rented, the requestor must deposit a minimum amount of funds into the contract. This deposit defines the “runway” for how long the VM can stay alive. If more runtime is needed, the requestor can top up the stream to extend the lease.

To prevent abuse, we are designing a **verifiable execution layer** powered by verifier nodes. These nodes act as decentralized oracles: they independently check whether a VM is actually running and can halt the payment stream if the VM is proven to be down.

### How the Check Works

Each VM runs with a **virtual Trusted Platform Module (vTPM)**, provided by tools like **swtpm** when using QEMU/KVM. Inside the VM, an agent (based on **Keylime**) continuously measures the VM’s state (boot sequence, configuration, integrity) and exposes an attestation API.

* **Verifier nodes** periodically send cryptographic challenges to the VM’s Keylime agent.
* The agent signs responses with the vTPM, proving they come from the correct, untampered VM.
* The verifier nodes validate the signatures and compare the measurements against a **“golden baseline”**—a reference fingerprint of what a healthy, trusted VM should look like.

Multiple verifiers perform this check, and their results are aggregated into a **consensus verdict** (e.g. through a Chainlink Decentralized Oracle Network).

### Smart Contract Integration

* If the verifier network confirms the VM is running, the on-chain payment stream continues.
* If the VM fails attestation or stops responding, the consensus report triggers the contract to halt payments and optionally refund unused funds to the requestor.

This ensures providers are only paid for live, verifiable machines, and requestors never fund dead VMs. By combining continuous payment streaming with cryptographic attestation, VM on Golem becomes a self-policing, decentralized compute marketplace.

---

## Confidential Compute & Secure Storage

Opening the network to commercial workloads means assuming the host is untrusted. Technologies such as **AMD SEV** and **Intel TDX** already protect the VM’s memory while it runs, but they do not shield the disk when the VM shuts down. To close that gap we combine hardware-backed confidential compute with **full disk encryption** and **attestation-driven key release**, ensuring the VM stays protected in every state.

### The Workflow

1. The tenant builds the VM image with **LUKS full disk encryption** enabled. Without the key, the image is unreadable.
2. The image includes a minimal `initramfs` containing the tools to unlock the disk and a lightweight attestation agent (e.g. a Keylime client).
3. The provider boots the VM under SEV/TDX. The `initramfs` runs inside the hardware-encrypted enclave, while the main disk stays locked.
4. The attestation agent requests a signed measurement from the CPU and forwards it to a remote **Key Server** controlled by the workload owner.
5. The Key Server verifies the signature and measurements. If they match the golden baseline, it releases the LUKS key; otherwise it refuses.
6. The `initramfs` unlocks the volume and hands control to the OS. The key never touches disk and only exists briefly in protected memory.

### What the Host Can See

* **While running:** only encrypted memory guarded by SEV/TDX.
* **While stopped:** only an encrypted disk image (LUKS).
* **At boot:** keys are released only if attestation proves the VM is genuine.

This layered model delivers a zero-trust lifecycle: secrets remain private while the VM runs, when it pauses, and even when it is powered off.

---

## Requestor Workflow

The requestor experience stays true to the **“three commands to a VM”** promise:

1. `golem vm providers` — query Golem Base for available providers, filter by resources or location.
2. `golem vm create --provider-id <id> --cores <n> --memory <gb> --disk <gb>` — the CLI deposits funds into the stream, shares the ID with the provider, and triggers provisioning once confirmed.
3. `golem vm ssh <name>` — connect directly to the machine through the provider’s forwarded port.

Connection details are stored locally, so reconnecting or tearing down later takes just one command.

---

## End-to-End Flow

* Providers install the node, port-forward, and publish their listing.
* Requestors browse listings, fund a stream, and start provisioning.
* Providers boot the VM, inject SSH keys, and expose the port.
* Golem Base keeps advertisements accurate and verifiable.
* Payment streams ensure that if funding ends, the VM shuts down gracefully.





### Dependencies & Integrations

### Feasibility & Rationale

### Risks & Mitigation

---

## 6. Roadmap & Milestones
| Phase | Deliverables | Timeline | Success Criteria |
|-------|--------------|----------|------------------|
| Phase 1 – Core Infrastructure | Requestor CLI, Provider Node, Discovery service, SSH automation | Completed (Feb 2025) | CLI provisioning works end-to-end on testnet |
| Phase 2 – Port Verification | Automated external port checks, diagnostics, readiness gating | Completed (Feb 2025) | Providers validated before listing; reduced connection failures |
| Phase 3 – Smart Contract Payments | StreamPayment integration, CLI stream tooling, automated withdrawals | Feb–Mar 2025 | Stable per-second billing on Holesky L2 with <2% settlement errors |
| Phase 4 – Provider GUI | Resource dashboard, revenue tracking, analytics | Mar–Apr 2025 | 50+ providers using GUI weekly; telemetry shows active engagement |
| Phase 5 – Verifier Network | Decentralized integrity proofs, uptime monitoring, reputation scoring | Apr–May 2025 | Verifier reports reduce false-positive provider listings |
| Phase 6 – Requestor Web Interface | Browser-based VM marketplace with wallet auth and cost tracking | Apr–May 2025 | Web users launch VMs with parity to CLI; conversion metrics established |
| Phase 7 – Decentralized Discovery | On-chain provider registry, open filtering APIs | May–Jun 2025 | Providers self-advertise on-chain; requestors resolve via trust-minimized index |

---

## 7. Budget

### Total Funding Requested

### Breakdown by Phase / Milestone

### Resource Allocation

### Payment Schedule Suggestion

---

## 8. Team

### Member Profiles

### Relevant Track Record

---

## 9. Open Source Commitment

### Licensing

### Components to be Open-Sourced

### Documentation Plans

---

## 10. Community Engagement

### Engagement Strategy

### Communication Channels

### Community Programs

---

## 11. Sustainability Plan

### Maintenance & Ownership

### Long-Term Vision

### Future Funding or Revenue Model

---

## 12. Evaluation & Metrics

### Key Performance Indicators

### Reporting Cadence & Format

---

## 13. Appendices (Optional)

### Technical Diagrams

### Visual Assets

### Extended Background & Support Letters
