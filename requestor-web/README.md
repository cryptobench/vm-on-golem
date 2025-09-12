Requestor Web (Next.js)

Client-side only Next.js app (static export) to discover providers, open payment streams with MetaMask, and rent/manage VMs via the port-checker proxy.

Quick start

- cd requestor-web
- cp .env.example .env.local and fill values
- npm install
- npm run dev
- npm run build && npm run start (or deploy the `out/` folder as static site)

Styling

- Tailwind CSS is used for styling. Config files: `tailwind.config.ts`, `postcss.config.js`.
- Global utilities and small component classes live in `app/globals.css` and are imported by `app/layout.tsx`.
- No extra CSS build step is required; Next.js runs PostCSS automatically in dev/build.

SSH Keys

- Settings allows storing multiple named SSH public keys. These are saved to localStorage and can be selected in the Rent modal.
- The top “SSH public key” field remains as a quick default; the list below supports adding, renaming, and deleting multiple keys.

Env vars (public)

- NEXT_PUBLIC_DISCOVERY_API_URL: discovery service base, e.g. http://localhost:9001/api/v1
- NEXT_PUBLIC_PORT_CHECKER_URL: port-checker proxy base, e.g. http://localhost:9000
- NEXT_PUBLIC_PORT_CHECKER_TOKEN: shared proxy token (exposed to users)
- NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS: default StreamPayment contract (can be overridden in Settings or provider info)
- NEXT_PUBLIC_GLM_TOKEN_ADDRESS: GLM token address (0x00.. means native)
- NEXT_PUBLIC_EVM_CHAIN_ID: hex chain id for MetaMask (e.g., 0x4268)
- NEXT_PUBLIC_GOLEM_ENVIRONMENT: set to `development` to switch defaults to the Golem Base dev RPC/WS
- NEXT_PUBLIC_GOLEM_BASE_DEV_RPC_URL / NEXT_PUBLIC_GOLEM_BASE_DEV_WS_URL: dev Golem Base endpoints used when environment=development

Notes and alignment with backend

- Discovery uses GET /advertisements from discovery-server (central).
- By default, provider IP resolution for proxy calls uses Golem Base (X-Proxy-Source: golem-base) and requires the proxy server to have Golem Base support (golem-base-sdk) and L3 RPC/WS configured. You can switch the profile to "central" in Settings to use legacy discovery instead.
- Provider access goes through port-checker /proxy/provider/{provider_id}/... with X-Proxy-Token.
- Only HTTP is proxied; SSH is shown as host:port for your terminal client.
- Streams use the same StreamPayment ABI as requestor (createStream, streams, topUp, terminate). MetaMask signs transactions.
- Pricing estimate logic mirrors requestor ProviderService (GLM/USD per month → ratePerSecond calculations).

Limitations

- VM ownership isn’t globally queryable; the app tracks “your rentals” in localStorage.
- ERC20 streaming is supported with a basic approve/allowance flow; native token mode also works.
- The proxy token is public in a static site; use a token suitable for public use and rely on the port-checker’s IP/port allowlist and timeouts. Consider rate limiting.
- Provider listing currently uses central discovery even when “Golem Base” is selected; only per-provider resolution switches to Golem Base. A future enhancement can add a Golem Base listing backend.
