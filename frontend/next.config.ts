import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    // Old marketing pages now live as sections of the home page.
    return [
      { source: "/features", destination: "/#product", permanent: true },
      { source: "/how-it-works", destination: "/#how-it-works", permanent: true },
      { source: "/solutions", destination: "/", permanent: true },
      { source: "/resources", destination: "/", permanent: true },
      { source: "/desktop", destination: "/download", permanent: true },
      { source: "/dashboard/history/:id", destination: "/dashboard/history", permanent: false },
    ];
  },
};

export default nextConfig;
