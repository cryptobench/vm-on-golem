# Funding & Milestone Plan

## Executive Summary
For the past 8 years , golem network has been trying to create a successful cloud computing product, but has not succeeded. The barrier of entry for developers has simply
▌ been tooo high. The user experience has been neglected and in order to get started with golem, you must learn golem specific domain knowledge thats not mappable to anywhere else, youre limited in what you can
▌ do, and you cant just migrate existing workloads from one cloud into golem network. With my project codenamed VM on Golem, I want to take a completely different approach to cloud computing that I haven't seen
▌ in golem nor anywhere else in DePIN. I want to make it simple, because its much simpler than people make it. Vm on Golem is built on the vision that even a 12 year old should be able to use the product without
▌ having to read any kind of documentation to get started.
▌
▌ The idea is that you still have requestor and providers, but providers rent out customizable plain virtual machines, just as if it was a VPS rented on some cloud provider like AWS, Digital Ocean or Google
▌ cloud. All it takes is 3 simple commands (list the commands from our readme), and now you have access to a full normal VM, just like with any other cloud. What this means is that your workload is 1:1
▌ migrateable, you dont need to worry about limitations with Golem that can cause your workload to fail because the environment is different. Its 1:1 the same thing, you can use it exactly like how youre used to
▌ everywhere else.
▌
▌ VM's are the backbone of everything we do online. VM's allows people to setup clusters like kubernetes on top of it, you can run your monolithic server for your business, or deploy some third. If you have
▌ access to a plain normal VM, then you can build whatever you want on top of it. FOr example AWS fargate is based on EC2 instances (AWS equavalent of VM offerings), and the same kind of solution could be built
▌ with VM on Golem.

over the last many years, ive seen countless of people come into our Discord, and what they wanted was just to run a few commands and have access to a machine running ubuntu. Thats it. Anyone looking to deploy a large data pipeline isn't going to invest countless hours into golem's unique specific libraries and risk that if the network goes down or somethimng breaks, then they cant just migrate it to some other cloud. We see the exact same thing happening with Golem DB right now. We want to be able to spin up our whole infrastructure on another cloud if hetzner decides to drop us, and thats no different from everyone else. 

With VM on Golem being a simple normal VM, then that would mean our own Golem DB kubernetes infrastructure could be spun up on it, and I think thats a great benchmark for the project that it's 1:1 migrateable.

## Introduction
*Summarize what the project does today, the vision for the product, and why this matters in one or two paragraphs.*

VM on Golem makes decentralized cloud compute feel as intuitive as the best Web2 Cloud providers. In three terminal commands a developer can discover a provider, launch a VM, and connect over SSH. If you've bought a VPS from a central cloud provider before, then i'm confident you'll be able to rent a VM here, all without reading any kind of documentation or having to learn anything new.



## Problem & Opportunity
*Explain the pains for users, quantify the market size, and describe why now is an ideal moment.*

### Current Pain Points
- **Fragmented UX keeps DePIN niche.** Web3-native infrastructure often forces builders to learn new paradigms, gating adoption behind steep onboarding. Golem Network is powerful but historically required bespoke stacks that do not map to familiar VM workflows.
- **Developers still need elastic VMs.** Industry analysts estimate global cloud infrastructure spend now exceeds $250B annually with >18% YoY growth, while compute-hungry AI and edge workloads demand geographic diversity and cost flexibility.
- **Providers lack a trustable marketplace.** Node operators need pricing transparency, assured payouts, and diagnostics to keep ports reachable. Without this, capacity sits idle.

### Opportunity Snapshot
- **Timing is shifting in our favor.** DePIN projects attracted billions in 2024, yet most focus on storage or AI acceleration. A simple, general-purpose VM layer that reuses existing tooling is still missing.

These gaps point to a clear opportunity: package Golem’s incentives and global footprint into a developer-first experience that competes with traditional VPS providers on convenience, not ideology.

## Solution (How It Works)
*Describe how the product solves the problems, focusing on user experience and technical differentiators.*

### Key Components
- **Requestor CLI (`golem`).** Ships an intuitive workflow (discover → create → SSH) with JSON outputs for automation. It manages SSH keys, stores VM metadata locally, and integrates with the StreamPayment contract for usage-based billing in native ETH.
- **Provider Node (`golem-provider`).** Automates VM lifecycle via Multipass, advertises capacity to the discovery service, verifies ports continuously, and exposes pricing expressed in USD for clarity while auto-converting to GLM for settlements.
- **Discovery & Port Checker services.** FastAPI microservices index available providers, enforce network readiness, and expose health endpoints so requestors only see reachable machines.
- **Streaming payments (EIP-1620 inspired).** Contracts in `contracts/` unlock second-by-second vesting, top-ups, halts, and withdrawals. Providers can terminate or withdraw dynamically; requestors always know runway.
- **UX-first roadmap.** Upcoming Provider GUI and Requestor Web dashboards mirror the CLI functionality with high-polish Tesla-inspired visuals (`VM-on-Golem-VISION/VISUALS.md`), supporting both dark and light modes.

## Product Architecture & Technology
*Detail high-level system diagrams, scalability plans, dependencies, and security posture. Mention any proprietary IP or defensible technology.*

### Architecture Overview
*Add simplified diagrams and explain how services (requestor, provider, discovery, port checker, contracts) interconnect.*

### Scalability & Reliability
*Describe infrastructure choices, performance targets, and failover mechanisms.*

### Security & Compliance
*Summarize key security practices, audits, and compliance considerations relevant to investors.*

## Business Model & Revenue Streams
*Clarify who pays, how much, and how revenue scales over time.*

### Current Thesis
Business model leans on a dual-sided marketplace: small protocol fees on active streams, premium automation (e.g., managed verifier services), and enterprise onboarding packages once decentralized discovery ships.

### Pricing & Margins
*Add detailed pricing, margin assumptions, expected take rate, and unit economics.*

### Expansion Opportunities
*Outline future monetization (e.g., managed services, SLA tiers, data products).* 

## Market & Timing
*Quantify the TAM/SAM/SOM and explain macro trends that make the moment compelling.*

### Market Drivers
- **Cloud to DePIN bridge.** A huge share of AI and edge workloads cannot leave virtual machines. VM on Golem enables cost arbitrage versus hyperscalers (providers compete in USD) while serving developers who already trust Unix workflows.
- **Sovereign & resilient architectures.** Enterprises increasingly seek multi-region options that avoid single points of failure. Our decentralized footprint, plus verifier network plans, offers a compliance-friendly story.
- **Crypto-native payments.** Native ETH streams remove reliance on credit cards and unlock new pay-as-you-go models for DAO treasuries or on-chain agents needing elastic compute.

### Why Now
- **Momentum inside Golem.** Two core phases were delivered in rapid sprints (see below), creating first-mover advantage in a resurging Golem ecosystem hungry for polished UX.

## Competitive Landscape
*Outline primary centralized and decentralized competitors, compare features/pricing, and highlight defensibility.*

### Direct Competitors
*List similar DePIN or decentralized compute offerings and their strengths/weaknesses.*

### Indirect Competitors
*Identify traditional cloud providers and explain switching barriers.*

### Differentiation & Moats
*Summarize why VM on Golem wins (UX, payments, community, data, etc.).*

## Traction & Proof Points
*Share quantitative metrics, user testimonials, pilots, or major releases that validate momentum.*

### Completed Milestones
- **Phase 1 – Core infrastructure (completed Feb 20, 2025).** Requestor CLI, Provider Node, Discovery, SSH key management, and monitoring shipped in 24 hours (see `VM-on-Golem-VISION/ROADMAP.md`).
- **Phase 2 – Port verification (completed Feb 21, 2025).** Automated external port checks, diagnostics, and provider readiness gating added the next day.

### In-Flight Initiatives
- **Phase 3 – Smart contract payments (in progress Feb–Mar 2025).** Contracts deployed across Holesky L2/Kaolin testnets with ABI-guarded clients in both provider and requestor services; CLI already abstracts stream creation and top-ups.

### Narrative Highlights
- **Ecosystem alignment.** Documentation across `README.md`, `provider-server/README.md`, and `requestor-server/README.md` demonstrates consistent messaging (“Airbnb for servers”) and positions the product as a 3-command experience.

## Go-To-Market Strategy
*Detail customer personas, acquisition channels, activation flows, and retention tactics.*

### Target Segments
*List priority customer groups (e.g., AI startups, Web3 projects, developers) and their needs.*

### Acquisition Plan
*Explain channels (community, partnerships, paid campaigns) and success metrics.*

### Retention & Expansion
*Describe support, community programs, upsells, and land-and-expand motions.*

## Milestones & Roadmap
*Lay out phased deliverables, expected completion dates, and success criteria.*
| Phase | Timeline | Status | Key Deliverables |
| --- | --- | --- | --- |
| Core Infrastructure | Feb 2025 | ✅ Completed | Requestor CLI, Provider Node, Discovery service, SSH automation |
| Port Verification | Feb 2025 | ✅ Completed | Local & external port checks, diagnostics, readiness gating |
| Smart Contract Payments | Feb–Mar 2025 | 🚧 In Progress | StreamPayment contract, CLI stream tooling, automated withdrawals |
| Provider GUI | Feb–Apr 2025 | 🚧 In Progress | Web dashboard with resource analytics, revenue tracking, pricing insights |
| Verifier Network | Mar–May 2025 | 🔒 Planned | Decentralized integrity proofs, uptime monitoring, reputation scoring |
| Requestor Web Interface | Mar–May 2025 | 🔒 Planned | Browser-based VM marketplace with wallet auth and cost tracking |
| Decentralized Discovery | May–Jun 2025 | 🌐 Future | On-chain provider registry, open filtering APIs |

### 12-Month Success Metrics
*Track quantitative goals that indicate product-market-fit progress.*
- 1,000+ concurrently advertised CPU cores with verified external reachability.
- <60s median VM provisioning time from CLI/web request.
- $250k annualized GMV flowing through StreamPayment contracts with <2% settlement disputes.
- 100+ active providers using the GUI weekly and <5% churn.

## Team & Contributors
*Introduce the project owner, track record inside Golem, and any future hiring intentions.*

### Builder Profile
- **Phillip – Founder & Sole Developer.** Seven-year veteran of the Golem Network who has shipped core components across discovery, provider tooling, and requestor UX. Currently owns every code path in this monorepo, ensuring rapid iteration and coherent architecture.

### Community Support
- **Golem Ecosystem Collaboration.** Regularly syncs with Golem Network maintainers for roadmap alignment, testing support, and discovery infrastructure insights. Contributions remain open-source and invite feedback via GitHub discussions.

### Future Hiring Outlook
- **Selective Scaling.** No immediate hiring; funding will unlock the option to contract specialized security reviewers or frontend support once smart-contract payments and GUIs reach mainnet parity.

Advisory input will continue coming from long-standing Golem peers, keeping governance lightweight while leveraging ecosystem expertise when needed.

## Organizational Plan
*Describe how the team operates, decision-making processes, and company culture.*

### Operating Model
*Explain day-to-day workflows, use of remote vs. in-person collaboration, and tooling.*

### Governance & Legal
*Outline corporate structure, board setup, and any token/equity considerations.*

### Culture & Values
*List core values and practices that will guide hiring and execution.*

## Funding Needs
*Clarify how much capital is required, for what duration, and what milestones it unlocks.*
We are opening a **$1.8M USD pre-seed round** to fund 18 months of runway through Phase 5 and early revenue experimentation.

| Allocation | Amount | Use of Funds |
| --- | --- | --- |
| Product & Engineering Execution | $1,050,000 | Sustain full-time development by Phillip, fund short-term contracts for security research and frontend polish, and cover tooling/infrastructure for rapid iteration. |
| Security & Audits | $200,000 | External smart contract audits, penetration testing for discovery/port checker services, bug bounty fund. |
| Network Incentives & Community | $300,000 | Provider liquidity rewards, hackathon grants, co-marketing with Golem ecosystem, documentation sprints. |
| Go-to-Market & Partnerships | $150,000 | Enterprise pilots, compliance advisory, targeted demand generation for AI/startup communities. |
| Operations & Contingency | $100,000 | Legal, accounting, infrastructure, and 3-month cash buffer. |

The raise enables a focused solo build to complete the roadmap, fund external audits, run verification pilots with early enterprise partners, and prepare for a seed round tied to GMV milestones without diluting execution velocity.

## Financial Projections & Capital Efficiency
*Insert revenue projections, expense breakdown, burn vs. runway analysis, and KPI targets.*

### Revenue Forecast
*Model best/worst/base cases tied to GMV and protocol fees.*

### Expense Plan
*Break down major cost centers (team, infrastructure, incentives) over time.*

### Efficiency Metrics
*Track CAC, LTV, payback, and other ratios relevant to investors.*

## Risk Mitigation & Contingencies
*Enumerate key risks and how the team will mitigate or respond to each.*

### Technical Risks
*Note challenges like smart-contract exploits, uptime, or scaling limits and the mitigation steps.*

### Market & Regulatory Risks
*Address adoption uncertainty, competitive moves, or legal considerations plus contingency plans.*

### Operational Risks
*Highlight hiring, execution, or supply constraints and backup strategies.*

## Impact & ESG Considerations
*Describe how the project supports decentralization, responsible energy use, and inclusive governance.*

### Decentralization & Community
*Explain how the network empowers contributors globally and shares value.*

### Environmental Factors
*Discuss energy-efficiency initiatives, carbon reporting, or green partnerships.*

### Social & Governance
*Cover transparency practices, diversity goals, and alignment with broader ESG expectations.*

## Data Room & Appendices
*List supporting materials (metrics dashboards, case studies, audit reports) and how investors can access them.*

### Included Assets
*Enumerate specific documents, spreadsheets, demo videos, and audits available upon request.*

### Access Instructions
*Explain how to request access (e.g., email, shared drive, investor portal).* 

## Call to Action
*Provide clear next steps for interested investors or partners.*

We invite the Golem Ecosystem Fund and aligned DePIN backers to participate in diligence. Next steps:
- Review the live demos (`README.md` quick start) and roadmap visualizations in `VM-on-Golem-VISION/`.
- Schedule a technical deep dive and contract walkthrough with Phillip to validate architecture, payment flows, and budget deployment for a single-operator build.
- Align on co-marketing or network-incentive experiments that can launch alongside the Provider GUI beta (target April 2025).

Reach out through the project’s GitHub discussions or Discord to coordinate an investor briefing and access to the detailed data room.
