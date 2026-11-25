import type { NextConfig } from "next";

const apiOrigin = process.env.AGENTTAINT_API_ORIGIN || "http://127.0.0.1:8080";

// AGENTTAINT_STATIC_EXPORT=1 builds a static bundle (out/) that the control
// plane serves itself (same origin, no Node server needed in production).
const staticExport = process.env.AGENTTAINT_STATIC_EXPORT === "1";

// Paddle client-side tokens are public by design; map the deploy env var in.
// Checkout stays closed unless NEXT_PUBLIC_PADDLE_CHECKOUT_ENABLED is exactly
// "true" at build time (same inlining path as the client token).
const env = {
  NEXT_PUBLIC_PADDLE_CLIENT_TOKEN: process.env.PADDLE_CLIENT_TOKEN || "",
  NEXT_PUBLIC_PADDLE_CHECKOUT_ENABLED: process.env.NEXT_PUBLIC_PADDLE_CHECKOUT_ENABLED || "",
};

const nextConfig: NextConfig = staticExport
  ? { env, output: "export", trailingSlash: true, images: { unoptimized: true } }
  : {
      env,
      async rewrites() {
        return [
          {
            source: "/api/v1/:path*",
            destination: `${apiOrigin}/api/v1/:path*`,
          },
        ];
      },
    };

export default nextConfig;
