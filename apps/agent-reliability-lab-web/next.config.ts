import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/lab-api/:path*",
        destination: "http://127.0.0.1:8010/api/:path*",
      },
    ];
  },
};

export default nextConfig;