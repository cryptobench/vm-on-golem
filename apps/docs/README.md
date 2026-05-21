# VM on Golem Docs

Fumadocs documentation app for a separate Vercel project/domain.

## Development

```sh
npm --workspace @golem/docs run dev
```

## Build

```sh
npm --workspace @golem/docs run build
```

## Vercel

Create a separate Vercel project for the docs domain from the same Git
repository.

Recommended settings:

- Root Directory: repository root
- Build Command: `npm --workspace @golem/docs run build`
- Install Command: `npm install`
- Framework Preset: Next.js

Then attach the docs domain to that Vercel project.
