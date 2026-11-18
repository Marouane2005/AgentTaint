import { LegalPage } from "@/components/site/LegalPage";
import { PRO_PRICE_LABEL, SUPPORT_EMAIL } from "@/lib/site";

export const metadata = { title: "AgentTaint · Refund Policy" };

export default function RefundsPage() {
  return (
    <LegalPage title="Refund Policy" updated="18 November 2026">
      <p>
        AgentTaint Pro ({PRO_PRICE_LABEL}) is sold through Paddle, our merchant of record, which
        processes all refunds.
      </p>
      <h2>14-day refunds</h2>
      <p>
        If you are not satisfied, you can request a full refund of any subscription payment within
        14 days of that payment. No reason is required. Refunds go back to the original payment
        method; Paddle typically processes them within a few business days, and your bank may take
        longer to show them.
      </p>
      <h2>How to request one</h2>
      <ul>
        <li>Reply to your Paddle receipt or use the support link on it, or</li>
        <li>
          email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with the email address
          used for the purchase.
        </li>
      </ul>
      <h2>Cancelling</h2>
      <p>
        You can cancel anytime to stop future renewals. After 14 days, a payment is not refunded,
        and access continues until the end of the period already paid for.
      </p>
      <p>
        This policy does not limit any rights you have under applicable consumer protection law.
      </p>
    </LegalPage>
  );
}
