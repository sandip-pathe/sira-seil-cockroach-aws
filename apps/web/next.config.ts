import type { NextConfig } from "next";

const apiBaseUrl = (process.env.SIRA_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@sira/api-client"],
  async rewrites() {
    return [
      {
        source: "/health",
        destination: `${apiBaseUrl}/health`,
      },
      {
        source: "/v1/:path*",
        destination: `${apiBaseUrl}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
