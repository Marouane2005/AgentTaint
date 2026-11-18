"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** The console lives at /overview; the server also redirects "/" (demo: /product). */
export default function RootRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/overview");
  }, [router]);
  return null;
}
