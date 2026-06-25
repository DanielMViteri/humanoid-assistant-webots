import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // This project lives inside a OneDrive-synced folder. Turbopack's on-disk
    // FileSystem cache (default in Next 16.1+) gets corrupted when OneDrive
    // syncs the rapidly-rewritten .next/cache files mid-build, producing
    // "turbo-persistence ... range start index out of range" panics. Keep the
    // dev cache in memory so there's nothing on disk for OneDrive to race.
    turbopackFileSystemCacheForDev: false,
  },
};

export default nextConfig;
