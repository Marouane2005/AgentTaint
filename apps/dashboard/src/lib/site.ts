/**
 * Product site settings (read at build time: static export).
 *
 * Paddle: PADDLE_CLIENT_TOKEN (a Paddle client-side token, public by design)
 * is mapped in next.config.ts. When it is empty the Pro card falls back to the
 * waitlist. The price id below is the live "AgentTaint Pro $15.00 USD/month".
 */
export const PADDLE_CLIENT_TOKEN = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN || "";
export const PADDLE_PRICE_ID = "pri_01m7r7zmmk1g29rp2y6t6px3mq";

/** Optional plain checkout link (e.g. a hosted checkout); used only without Paddle.js. */
export const CHECKOUT_URL = process.env.NEXT_PUBLIC_CHECKOUT_URL || "";

export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "maroozi2018@gmail.com";
export const SELLER = "Marouane El Aasri";
export const SELLER_COUNTRY = "Morocco";

export const PRO_PRICE = "$15.00";
export const PRO_PRICE_LABEL = "$15.00 USD/month";
