# VM on Golem

Spin up a virtual machine on the Golem Network in minutes. Pick a provider, choose CPU/memory/storage, pay as you go, and connect. No clouds to learn. No dashboards to fight.


## Install

Most users (requestors):

```
pip install request-vm-on-golem
```

Optional — host capacity (providers):

```
pip install golem-vm-provider
```


## Quick Start (Requestor)

1) Find a provider that fits your spec:

```
golem vm providers --cpu 2 --memory 4 --storage 40
```

2) Create a VM (funding handled for you in the background):

```
golem vm create my-vm \
  --provider-id 0xYOURPROVIDER \
  --cpu 2 --memory 4 --storage 40
```

3) Connect over SSH:

```
golem vm ssh my-vm
```

That’s it — you now have a full Ubuntu VM running with just 3 simple commands.


## Common Commands

- Show providers (with optional filters):
  - `golem vm providers --cpu 4 --memory 8 --storage 60`
- Create a VM (name it and pick a provider):
  - `golem vm create my-vm --provider-id 0x... --cpu 4 --memory 8 --storage 60`
- Connect to your VM:
  - `golem vm ssh my-vm`
- Check details or list all:
  - `golem vm info my-vm`
  - `golem vm list`
- Start/stop or delete:
  - `golem vm start my-vm`
  - `golem vm stop my-vm`
  - `golem vm destroy my-vm`

About filters on `vm providers`:
- Purpose: pass a full spec with `--cpu/--memory/--storage` to see estimated pricing per provider for that exact VM.
- Without filters: you get all available providers, their inventory, and per‑unit prices (no per‑VM estimate).
- With filters: the table also shows “Est. $/mo” and “~$/hr” for your spec, making cost comparison trivial.
- Add `--json` for machine‑readable output; when a full spec is provided, each provider includes an `estimate` object.

Tips:
- Run `golem --help` and `golem vm --help` for more options.


## Example: Filtered Provider List + Price

When you include a full spec, `golem vm providers` computes the price for that VM on each provider and shows it alongside per‑unit pricing.

Command:

```
golem vm providers --cpu 2 --memory 4 --storage 40
```

Sample output (simplified):

| Provider ID        | Country | CPU | Mem | Disk | USD/core/mo | USD/GB RAM/mo | USD/GB Disk/mo | Est. $/mo | Est. GLM/mo |
|--------------------|---------|-----|-----|------|-------------|---------------|----------------|-----------|-------------|
| 0xabc...123        | US      | 8   | 32  | 500  | 8.00        | 2.00          | 0.08           | 40.64     | 123.456789  |
| 0xdef...456        | DE      | 16  | 64  | 1000 | 10.00       | 2.50          | 0.10           | 50.80     | 154.321000  |

Notes:
- The actual CLI prints a formatted table and also annotates Provider ID with approximate “~$/hr” when a spec is given.
- With `--json`, each provider includes: `estimate = { usd_per_month, usd_per_hour, glm_per_month }`.


## Host as a Provider (Optional)

Want to earn by running VMs for others? Keep it simple to start:

```
pip install golem-vm-provider
golem-provider start --network testnet
```

Set your price in USD (GLM auto‑converts)

Why USD? Crypto prices move. Most people think in fiat, so setting prices in USD keeps your mental model simple and stable. Under the hood, the provider converts your USD prices to GLM using the current GLM/USD rate and keeps those GLM unit prices up‑to‑date in the background.

```
golem-provider pricing set \
  --usd-per-core 5 \
  --usd-per-mem 2 \
  --usd-per-disk 0.1
```

What these mean
- CPU: price per CPU core per month.
- RAM: price per GB of memory per month.
- Disk: price per GB of storage per month.

Requestors see per‑unit prices and an estimated monthly/hourly cost for their chosen spec based on your settings.

Check your pricing and examples

```
golem-provider pricing show
```

Tips
- Start simple with the example numbers above; adjust later as you like.
- Use `--dev` to write to `.env.dev` while experimenting: `golem-provider pricing set ... --dev`.
- Streams and payouts: `golem-provider streams list`, `golem-provider streams withdraw --all`.

More details live in `provider-server/README.md`.


## Develop From Source (Optional)

```
make install   # install Poetry deps for core services
make start     # run discovery, provider (dev), requestor APIs
make test      # run tests across services
```

Service READMEs:
- Provider: `provider-server/README.md`
- Requestor: `requestor-server/README.md`
- Port checker (utility): `port-checker-server/README.md`


## Questions

- CLI help: `golem --help`, `golem vm --help`, `golem-provider --help`
- Open an issue if something is confusing or slow — simplicity is the goal.
