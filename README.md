# VM on Golem

VM on Golem is a web-first product for renting and hosting virtual machines on
the Golem Network.

## Requestors

Requestors use the Next.js web app in `requestor-web/` to discover providers,
open payment streams with a browser wallet, rent VMs, and manage running
sessions through provider-advertised endpoints.

```bash
cd requestor-web
cp .env.example .env.local
npm install
npm run dev
```

The web app uses central discovery by default and can use Arkiv when configured
with `NEXT_PUBLIC_DISCOVERY_MODE=arkiv`.

## Providers

Providers run the provider server and optional desktop app to publish capacity,
manage VMs, and receive streaming payments.

```bash
pip install golem-vm-provider
golem-provider start --network testnet
```

Provider desktop development:

```bash
npm install
npm --workspace @golem/provider-desktop run dev
```

## Development

```bash
make install
make local
make test
```

`make local` starts central discovery, the provider API, provider desktop,
port-checker, and requestor web with one supervisor process.
The requestor web app opens in your browser by default so MetaMask and other
browser wallets are available.

Useful smoke-check variant:

```bash
make local LOCAL_STACK_ARGS="--no-open --skip-chain-check"
```

Requirements: Poetry, Node/npm, and Multipass.

## Project Structure

- `requestor-web/`: requestor web app.
- `provider-server/`: provider API and provider command surface.
- `apps/provider-desktop/`: provider desktop shell.
- `central-discovery-server/`: central discovery backend.
- `port-checker-server/`: provider port verification utility.
- `packages/design-system/`: shared design tokens.
- `packages/ui/`: shared React UI components.

See `docs/discovery.md` for discovery architecture.
