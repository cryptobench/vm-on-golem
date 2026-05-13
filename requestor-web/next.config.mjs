/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  reactStrictMode: true,
  experimental: { externalDir: true },
  transpilePackages: ["@golem/ui", "@golem/design-system"],
};

export default nextConfig;
