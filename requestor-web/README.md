Requestor Web (Next.js)

Client-side only Next.js app (static export) to discover providers, open payment streams with MetaMask, and rent/manage VMs via the port-checker proxy.

Quick start

- cd requestor-web
- cp .env.example .env.local and fill values
- npm install
- npm run dev
- npm run build && npm run start (or deploy the `out/` folder as static site)

Data fetching (SWR)

- SWR is used for client-side fetching, caching and polling. A global `SWRConfig` is set in `app/layout.tsx`.
- Prefer hooks in `hooks/useApiSWR.ts` over ad‑hoc `fetch` calls:
  - `useProviderInfo(providerId, { refreshInterval })`
  - `useVmAccess(providerId, vmId, { refreshInterval })`
  - `useVmStatusSafe(providerId, vmId, { refreshInterval })`
  - `useVmStreamStatus(providerId, vmId, { refreshInterval })`
- Pages that display VM status poll at intervals and use skeletons for content loading, per the Loading UX guidelines.

Price cache (USD)

- A centralized background poller runs in the global layout and refreshes ETH/GLM USD prices at most once every 5 minutes.
- Results are stored in localStorage under `requestor_prices_v2` and broadcast via a `requestor_prices_updated` event. The old `requestor_prices_v1` key is read only as a compatibility fallback.
- Price lookups use one shared in-flight request and source-level backoff. Components must not fetch price APIs directly.
- Source order is Binance, DEX Screener, CoinGecko, then CoinPaprika. This keeps normal traffic far below published public limits and reserves lower-quota sources for fallback.
- Use helpers in `lib/prices.ts`:
  - `startPricePolling()` to start/stop the poller (already wired in `app/layout.tsx`).
  - `getPriceUSD(symbol)` and `usdToToken(symbol, usd)` for display-only cached conversions.
  - `ensurePricesUSD()` and `usdToTokenAsync(symbol, usd, { maxAgeMs })` for payment flows that need a fresh quote.
  - `onPricesUpdated(cb)` to subscribe to changes.
- Rent/payment creation prefers provider-advertised token pricing. If a provider only advertises USD pricing, the UI requires a price refreshed within 10 minutes before opening a stream.

Styling

- Tailwind CSS is used for styling. Config files: `tailwind.config.ts`, `postcss.config.js`.
- Global utilities and small component classes live in `app/globals.css` and are imported by `app/layout.tsx`.
- No extra CSS build step is required; Next.js runs PostCSS automatically in dev/build.

SSH Keys

- Settings allows storing multiple named SSH public keys. These are saved to localStorage and can be selected in the Rent modal.
- The top “SSH public key” field remains as a quick default; the list below supports adding, renaming, and deleting multiple keys.

Env vars (public)

- NEXT_PUBLIC_DISCOVERY_API_URL: discovery service base, e.g. http://localhost:9001/api/v1
- NEXT_PUBLIC_DISCOVERY_MODE: default profile mode, `arkiv` or `central`
- NEXT_PUBLIC_PORT_CHECKER_URL: port-checker proxy base, e.g. http://localhost:9000
- NEXT_PUBLIC_PORT_CHECKER_TOKEN: shared proxy token (exposed to users)
- NEXT_PUBLIC_PROVIDER_API_PORT: provider HTTP API port used by the port-checker proxy; defaults to `7466`
- NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS: default StreamPayment contract (can be overridden in Settings or provider info)
- NEXT_PUBLIC_GLM_TOKEN_ADDRESS: GLM token address for stream deposits (Ethereum Hoodi tGLM is `0x55555555555556AcFf9C332Ed151758858bd7a26`)
- NEXT_PUBLIC_EVM_CHAIN_ID: hex chain id for MetaMask (Ethereum Hoodi is `0x88bb0`)
- NEXT_PUBLIC_EVM_CHAIN_NAME: wallet display name for the payments chain
- NEXT_PUBLIC_EVM_RPC_URL: wallet RPC URL for the payments chain
- NEXT_PUBLIC_EVM_EXPLORER_URL: block explorer URL for the payments chain
- NEXT_PUBLIC_GOLEM_ENVIRONMENT: set to `development` to switch defaults to the Arkiv dev RPC/WS
- NEXT_PUBLIC_ARKIV_DEV_RPC_URL / NEXT_PUBLIC_ARKIV_DEV_WS_URL: dev Arkiv endpoints used when environment=development

Payment chain values can also be overridden in Settings -> Payments. Wallet
connection, stream reads, stream creation, and top-ups all use the same payment
chain configuration. The `make local` supervisor and Makefile web helper targets
pass the StreamPayment, token, chain ID, RPC, and explorer values into the web
app so local development uses the same payment metadata as the Python services.

For Ethereum Hoodi, connected wallets need Hoodi ETH for gas and Hoodi tGLM for
stream deposits. Use Hoodi faucet links from `https://www.hoodi.dev/` for gas
ETH and the tGLM minter documented in `../contracts/README.md`.

Notes and alignment with backend

- Discovery can use Arkiv (default decentralized backend) or central discovery.
- By default, provider IP resolution for proxy calls uses Arkiv (`X-Proxy-Source: arkiv`) plus RPC/WS configuration. You can switch the profile to `central` in Settings to use the centralized backend.
- Provider access goes through port-checker /proxy/provider/{provider_id}/... with X-Proxy-Token.
- Only HTTP is proxied; SSH is shown as host:port for your terminal client.
- Streams use the same StreamPayment ABI as requestor (createStream, streams, topUp, terminate). MetaMask signs transactions.
- Pricing estimate logic computes GLM stream rates from provider USD pricing and current GLM/USD.

Limitations

- VM ownership isn’t globally queryable; the app tracks “your rentals” in localStorage.
- Streaming payments are GLM-only; native ETH is still required for gas.
- The proxy token is public in a static site; use a token suitable for public use and rely on the port-checker’s IP/port allowlist and timeouts. Consider rate limiting.
- Provider listing should use the selected discovery backend.
