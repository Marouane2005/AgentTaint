import type { NextConfig } from "next";

const apiOrigin = process.env.AGENTTAINT_API_ORIGIN || "http://127.0.0.1:8080";

// AGENTTAINT_STATIC_EXPORT=1 builds a static bundle (out/) that the control
// plane serves itself (same origin, no Node server needed in production).
const staticExport = process.env.AGENTTAINT_STATIC_EXPORT === "1";

const nextConfig: NextConfig = staticExport
  ? { output: "export", trailingSlash: true, images: { unoptimized: true } }
  : {
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
