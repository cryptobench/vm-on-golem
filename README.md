# VM on Golem

Rent a VM on a decentralized network of computers with just 3 simple commands, or rent out your own machine to requestors and earn money for the resources you provide.

---

## Table of contents

* [Vision](#vision)
* [Install](#install)
* [Quick Start (Requestor)](#quick-start-requestor)
* [Common Commands (Requestor)](#common-commands-requestor)
* [Example: Filtered Provider List + Price](#example-filtered-provider-list--price)
* [Host as a Provider (Optional)](#host-as-a-provider-optional)
* [Develop From Source (Optional)](#develop-from-source-optional)
* [Questions](#questions)

---

## Vision

Most DePIN projects overcomplicate cloud. I believe cloud computing doesn’t have to be difficult — it should be simple. **VM on Golem** is built on the idea that anyone can get started, even without reading documentation. Commands and visuals should be self-explanatory.

With **VM on Golem**, it takes just 3 commands to launch or rent out a VM.

---

## Install

For requestors:

```
pip install request-vm-on-golem
```

For providers (optional):

```
pip install golem-vm-provider
```

---

## Quick Start (Requestor)

1. Find a provider that fits your spec:

```
golem vm providers --cpu 2 --memory 4 --storage 40
```

2. Create a VM (funding handled in the background):

```
golem vm create my-vm \
  --provider-id 0xYOURPROVIDER \
  --cpu 2 --memory 4 --storage 40
```

3. Connect over SSH:

```
golem vm ssh my-vm
```

That’s it — a full Ubuntu VM in 3 commands.

---

## Common Commands (Requestor)

* Show providers (with optional filters):
  `golem vm providers --cpu 4 --memory 8 --storage 60`
* Create a VM:
  `golem vm create my-vm --provider-id 0x... --cpu 4 --memory 8 --storage 60`
* Connect:
  `golem vm ssh my-vm`
* Info and list:
  `golem vm info my-vm`
  `golem vm list`
* Start/stop/destroy:
  `golem vm start my-vm`
  `golem vm stop my-vm`
  `golem vm destroy my-vm`

### About filters on `vm providers`

* With a full spec (`--cpu/--memory/--storage`): shows estimated monthly/hourly cost per provider.
* Without filters: lists all providers, their inventory, and per-unit prices.
* With filters: table includes “Est. \$/mo” and “\~\$/hr” for your spec.
* Add `--json` for machine-readable output. Each provider includes an `estimate` object when a full spec is given.

Tip: run `golem --help` and `golem vm --help` for more options.

---

## Example: Filtered Provider List + Price

Command:

```
golem vm providers --cpu 2 --memory 4 --storage 40
```

Sample output (simplified):

| Provider ID | Country | CPU | Mem | Disk | USD/core/mo | USD/GB RAM/mo | USD/GB Disk/mo | Est. \$/mo |
| ----------- | ------- | --- | --- | ---- | ----------- | ------------- | -------------- | ---------- |
| 0xabc...123 | US      | 8   | 32  | 500  | 8.00        | 2.00          | 0.08           | 40.64      |
| 0xdef...456 | DE      | 16  | 64  | 1000 | 10.00       | 2.50          | 0.10           | 50.80      |

Notes:

* The CLI prints a formatted table with estimated costs.
* With `--json`, providers include:
  `estimate = { usd_per_month, usd_per_hour }`.

---

## Host as a Provider (Optional)

Earn by running VMs for others. Quick start:

```
pip install golem-vm-provider
golem-provider start --network testnet
```

Set prices in USD:

```
golem-provider pricing set \
  --usd-per-core 5 \
  --usd-per-mem 2 \
  --usd-per-disk 0.1
```

### Pricing model

* CPU: per core, per month
* RAM: per GB, per month
* Disk: per GB, per month

Requestors see both per-unit prices and estimated monthly/hourly costs.

Check your pricing:

```
golem-provider pricing show
```


---

## Develop From Source (Optional)

```
make install   # install Poetry deps
make local     # run the full local stack: discovery, provider, APIs, requestor web
make test      # run tests
```

### Local full stack on ARM macOS

For local end-to-end development on Apple Silicon, use:

```
make local
```

This starts local central discovery, the provider API, requestor API, provider
desktop, port-checker, and requestor web with one supervisor process. The
requestor web app opens in your browser by default so MetaMask and other browser
wallets are available.
It uses central discovery intentionally so local provider/requestor/web checks do
not depend on Arkiv discovery RPC/WS availability. Arkiv remains the default
product discovery backend outside this deterministic local workflow.

Streaming payments use the Ethereum Hoodi profile by default. `make local`
loads `contracts/deployments/hoodi.json`, injects the StreamPayment address into
provider, requestor, and frontend processes, and verifies the contract has bytecode
on `https://rpc.hoodi.ethpandaops.io` before startup. For offline UI-only
smoke checks, use `make local LOCAL_STACK_ARGS="--no-open --skip-chain-check"`.

Requestor wallets need Hoodi ETH for gas and Hoodi tGLM for stream deposits.
The GLM token is `0x55555555555556AcFf9C332Ed151758858bd7a26`; mint test tGLM
through the Hoodi minter documented in `contracts/README.md`.

Useful variant for smoke checks:

```
make local LOCAL_STACK_ARGS=--no-open
```

Requirements: Poetry, Node/npm, and Multipass.

Service READMEs:

* Provider: `provider-server/README.md`
* Requestor: `requestor-server/README.md`
* Discovery architecture: `docs/discovery.md`
* Central discovery backend: `central-discovery-server/README.md`
* Port checker: `port-checker-server/README.md`

---

## Questions

* CLI help: `golem --help`, `golem vm --help`, `golem-provider --help`
* Open an issue if something is unclear or slow — simplicity is the goal.
