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

| Provider ID | Country | CPU | Mem | Disk | USD/core/mo | USD/GB RAM/mo | USD/GB Disk/mo | Est. \$/mo | Est. GLM/mo |
| ----------- | ------- | --- | --- | ---- | ----------- | ------------- | -------------- | ---------- | ----------- |
| 0xabc...123 | US      | 8   | 32  | 500  | 8.00        | 2.00          | 0.08           | 40.64      | 123.456789  |
| 0xdef...456 | DE      | 16  | 64  | 1000 | 10.00       | 2.50          | 0.10           | 50.80      | 154.321000  |

Notes:

* The CLI prints a formatted table with estimated costs.
* With `--json`, providers include:
  `estimate = { usd_per_month, usd_per_hour, glm_per_month }`.

---

## Host as a Provider (Optional)

Earn by running VMs for others. Quick start:

```
pip install golem-vm-provider
golem-provider start --network testnet
```

Set prices in USD (auto-converted to GLM in the background):

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

### Tips

* Start simple with the example numbers, adjust later.
* Use `--dev` to save settings to `.env.dev`.
* Manage payouts:
  `golem-provider streams list`
  `golem-provider streams withdraw --all`

More details in `provider-server/README.md`.

---

## Develop From Source (Optional)

```
make install   # install Poetry deps
make start     # run discovery, provider (dev), requestor APIs
make test      # run tests
```

Service READMEs:

* Provider: `provider-server/README.md`
* Requestor: `requestor-server/README.md`
* Port checker: `port-checker-server/README.md`

---

## Questions

* CLI help: `golem --help`, `golem vm --help`, `golem-provider --help`
* Open an issue if something is unclear or slow — simplicity is the goal.

