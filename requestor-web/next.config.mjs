import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  outputFileTracingRoot: repoRoot,
  reactStrictMode: true,
  experimental: { externalDir: true },
  transpilePackages: ["@golem/ui", "@golem/design-system"],
};

export default nextConfig;
