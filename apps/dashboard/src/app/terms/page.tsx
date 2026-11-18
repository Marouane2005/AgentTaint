import Link from "next/link";
import { LegalPage } from "@/components/site/LegalPage";
import { PRO_PRICE_LABEL, SELLER, SELLER_COUNTRY, SUPPORT_EMAIL } from "@/lib/site";

export const metadata = { title: "AgentTaint · Terms of Service" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" updated="18 November 2026">
      <p>
        These terms govern your use of the AgentTaint website, the public demo and the AgentTaint
        Pro subscription (together, the &quot;Service&quot;). AgentTaint is provided by {SELLER}, an
        individual developer based in {SELLER_COUNTRY} (&quot;we&quot;, &quot;us&quot;). By using the
        Service or buying a subscription you agree to these terms.
      </p>
      <h2>1. Payments and merchant of record</h2>
      <p>
        Orders are processed by Paddle.com, our online reseller and merchant of record. Paddle
        handles payment, billing, invoices, sales tax/VAT and payment-related customer service, and
        Paddle&apos;s own terms apply to your purchase.
      </p>
      <h2>2. AgentTaint Pro subscription</h2>
      <ul>
        <li>Price: {PRO_PRICE_LABEL}, plus any taxes Paddle is required to collect.</li>
        <li>
          The subscription renews automatically each month until you cancel. You can cancel at any
          time from the link in your Paddle receipt or by emailing us; cancellation stops future
          renewals and access to new versions and support at the end of the paid period.
        </li>
        <li>
          While subscribed you get download access to the self-hosted software, updates, and email
          support. Support is provided by email on a best-effort basis; no response-time guarantee
          is offered.
        </li>
        <li>
          Use of the software is governed by the AgentTaint Commercial License included with it.
          Versions you received while subscribed may keep being used under that license.
        </li>
        <li>We may change the price for future billing periods with at least 30 days&apos; notice.</li>
      </ul>
      <h2>3. Refunds</h2>
      <p>
        See the <Link href="/refunds">Refund Policy</Link>: you can request a refund within 14 days
        of a payment.
      </p>
      <h2>4. Public demo</h2>
      <p>
        The demo is free, runs synthetic scenarios against mock tools and may be rate-limited,
        reset, changed or taken offline at any time. Do not enter confidential information into
        it, and do not attempt to disrupt it or circumvent its limits.
      </p>
      <h2>5. Acceptable use</h2>
      <p>
        You may not use the Service to break the law, to attack systems you are not authorized to
        test, or to resell or redistribute the software outside the terms of its license.
      </p>
      <h2>6. No warranty</h2>
      <p>
        AgentTaint reduces some risks of software agents misusing tools; it does not guarantee that
        any attack will be detected or prevented. Its known limitations are listed on the{" "}
        <Link href="/limitations">Limitations</Link> page. The Service is provided &quot;as is&quot;
        without warranties of any kind, to the extent permitted by law.
      </p>
      <h2>7. Limitation of liability</h2>
      <p>
        To the extent permitted by law, we are not liable for indirect, incidental or consequential
        damages, or for lost data, profits or revenue. Our total liability is limited to the amount
        you paid for the Service in the 12 months before the claim. Nothing in these terms limits
        rights you have under mandatory consumer law.
      </p>
      <h2>8. Changes and termination</h2>
      <p>
        We may update these terms; material changes will be posted here with a new date. We may
        suspend access for breach of these terms. You may stop using the Service at any time.
      </p>
      <h2>9. Contact</h2>
      <p>
        {SELLER}, {SELLER_COUNTRY} · <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
      </p>
    </LegalPage>
  );
}
