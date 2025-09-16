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

## 5. Technical Approach



### Architecture & Workflow

The architecture is rather simple. Vm on Golem takes the approach that the providers are exposing an API to the internet, which requestors must use to rent a VM. Now, the question that always comes up is; how will you do NAT punching for people with not public IP's, and the simply as is; We wont.

The number of providers available on the network has always been 10x what the amount of requestors has been, meaning theres no issues gathering supply of VM providers. Thats why we will be forcing providers to portforward their ports in order to join the network, and that might limit some people from becoming a provider, but the positive upside of this is that, I think this will result in more high-quality providers/ server hosts that has technical expertise, and my belief is that, those people will also be people that have a high uptime on their machine which is important for a platform like VM on Golem.


(list more information about the provider architecture here) (VM adapter, using multipass for initial launch, available on Mac, Linux nad windows.). 

Payments are using EIP..(figure out) payment streaming, meaning that providers are paid by the second as the requestor is depositing money into the contract before the rental is allowed to start. 

For advertising the providers we're employing Golem DB to submit advertisements from the providers and fetching via Golem DB RPC for the requestors.  (list more details about what were submitting)





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
