import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/rfp-intake",
        destination: "http://127.0.0.1:8000/rfp-intake",
      },
      {
        source: "/api/rfp-intake/:path*",
        destination: "http://127.0.0.1:8000/rfp-intake/:path*",
      },
    ];
  },
};

export default nextConfig;