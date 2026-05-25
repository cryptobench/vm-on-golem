# VM on Golem

VM on Golem lets requestors rent virtual machines from providers on the Golem
Network.

## Why This Exists

After being around Golem for years, seeing what people have requested, and
seeing the challenges users have faced, this project explores a different vision
of how Golem could work.

The key difference is that everything is based around a simple VM. Requestors do
not need to understand Golem-specific SDKs, tasks, payloads, or execution
models. If they have used a cloud provider before, they already understand the
concept: request a VM, connect to it, and run software.

This makes workloads easier to migrate from traditional cloud providers. Instead
of rewriting software around a Golem-specific model, requestors can run the same
kind of workloads they already run elsewhere.

For requestors, there is no software to install and no need to keep their own
machine online while a VM is running. They use the web UI, rent a VM, go offline,
and come back later while the VM keeps running.

For providers, capacity can be split across multiple VMs for multiple requestors
at the same time, as long as enough CPU, memory, and storage are available.
Providers can use either a graphical desktop app or a headless CLI, and payments
are streamed live on-chain while VMs run.

This is a ground-up implementation built from a fresh architecture rather than
existing Golem components. The current version runs on testnet, so funds have no
real value.

## Quick Start

Requestors do not need to install anything. Use the deployed requestor UI:

[https://golem-requestor.vercel.app/](https://golem-requestor.vercel.app/)

The UI lets requestors discover providers, connect a browser wallet, use the
Funding tab to acquire testnet funds, open payment streams, rent VMs, and manage
running sessions.

Providers can run either the desktop app or the headless CLI.

## Provider Install Options

### Provider Desktop

Use Provider Desktop when you want the graphical provider experience. Download
the latest Provider Desktop installer from
[GitHub Releases](https://github.com/cryptobench/vm-on-golem/releases), install
it, then start the provider from the app.

### Headless Provider CLI

Use the CLI on machines without a visual desktop:

```bash
curl -fsSL https://raw.githubusercontent.com/cryptobench/vm-on-golem/main/install/provider-cli.sh | sh
golem-provider start
```

On Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/cryptobench/vm-on-golem/main/install/provider-cli.ps1 | iex
golem-provider start
```

One-command install and start:

```bash
curl -fsSL https://raw.githubusercontent.com/cryptobench/vm-on-golem/main/install/provider-cli.sh | sh -s -- --start
```

The CLI installer downloads the matching standalone binary from GitHub Releases,
verifies its checksum, installs or validates Multipass, and runs a host
requirements check. `golem-provider start` then runs the provider in the
foreground. Keep that terminal open, or run the command under your preferred
service manager.

Provider networking heads-up: public providers need inbound ports `80`, `443`,
and `50800-50900` forwarded from the router/firewall to the provider machine.
`golem-provider start` checks this during startup.

Optional inspection commands:

```bash
golem-provider status
golem-provider summary
golem-provider watch
```

Resource and pricing defaults work out of the box. Tune them later if needed:

```bash
golem-provider settings resources set --cpu 8 --memory 32 --storage 200
golem-provider settings pricing set --cpu 12 --memory 4 --storage 0.1
```

## Local Development

Use the Makefile workflows from the repository root.

Install service dependencies:

```bash
make install
```

Run the local development stack:

```bash
make local
```

`make local` starts local central discovery, the provider API, provider desktop,
and requestor web through one supervisor process.

Test the production-mode build/run path:

```bash
make prod
```

Run tests:

```bash
make test
```

Useful local-stack variant:

```bash
make local LOCAL_STACK_ARGS="--no-open --skip-chain-check"
```

Requirements: Go, Poetry, Node.js, Python 3.11, and Multipass.

## Project Structure

- `requestor-web/`: requestor web app.
- `provider-server/`: provider API and provider command surface.
- `apps/provider-desktop/`: provider desktop shell.
- `central-discovery-server/`: Go central discovery backend with bundled provider port verification.
- `packages/design-system/`: shared design tokens.
- `packages/ui/`: shared React UI components.

See `docs/discovery.md` for discovery architecture.
