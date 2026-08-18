import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/suppliers/:path*",
        destination:
          "https://probable-doodle-wrwr7wwqq46pcrqp-8000.app.github.dev/suppliers/:path*",
      },
    ];
  },
};

export default nextConfig;