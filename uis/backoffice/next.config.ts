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
      {
        source: "/api/notifications/:path*",
        destination: "http://127.0.0.1:8000/notifications/:path*",
      },
    ];
  },
};

export default nextConfig;