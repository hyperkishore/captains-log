import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable source maps in production to reduce bundle size and prevent code exposure
  productionBrowserSourceMaps: false,

  // Enable React strict mode for better development experience
  reactStrictMode: true,

  // Optimize images
  images: {
    formats: ['image/avif', 'image/webp'],
  },
};

export default nextConfig;
