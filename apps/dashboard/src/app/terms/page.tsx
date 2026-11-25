import Link from "next/link";
import { LegalPage } from "@/components/site/LegalPage";
import { SELLER, SELLER_COUNTRY, SUPPORT_EMAIL, SUPPORT_PRICE_LABEL } from "@/lib/site";

export const metadata = { title: "AgentTaint · Terms of Service" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" updated="25 November 2026">
      <p>
        These terms govern your use of the AgentTaint website, the public demo, and optional paid
        hosted support or services (together, the &quot;Service&quot;). AgentTaint software itself
        is free, open-source software licensed under the Apache License 2.0 (see{" "}
        <code>LICENSE</code> in the repository); no commercial license is needed to use, modify, or
        self-host it. The Service is provided by {SELLER}, an individual developer based in{" "}
        {SELLER_COUNTRY} (&quot;we&quot;, &quot;us&quot;). By using the Service or subscribing to
        optional hosted support you agree to these terms.
      </p>
      <h2>1. Payments and merchant of record</h2>
      <p>
        Payments for optional hosted support are processed by Paddle.com, our online reseller and
        merchant of record. Paddle handles payment, billing, invoices, sales tax/VAT and
        payment-related customer service, and Paddle&apos;s own terms apply to your purchase.
      </p>
      <h2>2. Optional Hosted Support subscription</h2>
      <ul>
        <li>Price: {SUPPORT_PRICE_LABEL}, plus any taxes Paddle is required to collect.</li>
        <li>
          The subscription renews automatically each month until you cancel. You can cancel at any
          time from the link in your Paddle receipt or by emailing us; cancellation stops future
          renewals and hosted support at the end of the paid period, without affecting your rights
          to use the software under the Apache License 2.0.
        </li>
        <li>
          While subscribed you receive email support and setup assistance on a best-effort basis;
          no response-time guarantee is offered.
        </li>
        <li>
          Use of the AgentTaint software is governed solely by the Apache License 2.0 included with
          it.
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
        You may not use the Service to break the law or to attack systems you are not authorized to
        test. Use and redistribution of the AgentTaint software are governed by the Apache License
        2.0.
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
