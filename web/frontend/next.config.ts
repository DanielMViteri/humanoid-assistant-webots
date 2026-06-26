import type { NextConfig } from "next";

// Where the FastAPI backend is reachable from the Next.js server process.
// Browser calls go to the SAME origin as the page (relative /api/*), and Next
// proxies them here server-side. This keeps the app working identically on
// localhost, over an ngrok https tunnel, and on a phone on the LAN — no mixed
// content, no CORS, and only port 3000 needs to be tunneled.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Allow the dev server (and its HMR/_next resources) to be reached through
  // ngrok tunnels and the local network, e.g. for showing the patient portal on
  // a phone during the demo. Without this, Next 16 blocks cross-origin requests
  // to /_next/* and the app hangs on the loading screen.
  allowedDevOrigins: [
    "unnationalistic-nonbacterially-myong.ngrok-free.dev",
    "*.ngrok-free.dev",
    "*.ngrok-free.app",
    "*.ngrok.io",
    "192.168.0.16",
  ],
  async rewrites() {
    // Proxy all API calls to the FastAPI backend so the browser only ever talks
    // to the same origin it loaded from.
    return [
      { source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` },
    ];
  },
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
