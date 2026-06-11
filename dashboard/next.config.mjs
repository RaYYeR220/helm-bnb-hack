/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static HTML export — `npm run build` produces an `out/` directory
  // servable anywhere (no Node server, no API routes). The dashboard reads
  // pre-computed JSON artifacts from /public/data at runtime via fetch.
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
