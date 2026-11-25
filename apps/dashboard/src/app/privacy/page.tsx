import { LegalPage } from "@/components/site/LegalPage";
import { SELLER, SELLER_COUNTRY, SUPPORT_EMAIL } from "@/lib/site";

export const metadata = { title: "AgentTaint · Privacy Policy" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="25 November 2026">
      <p>
        This policy explains what personal data the AgentTaint website, demo and optional hosted
        support subscription collect, and why. The data controller is {SELLER}, {SELLER_COUNTRY} (
        <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>).
      </p>
      <h2>What we collect</h2>
      <ul>
        <li>
          <strong>Waitlist:</strong> the email address you submit, the signup time and which form
          you used. Used only to tell you about AgentTaint releases and when optional hosted
          support is available. Kept until you ask us to delete it.
        </li>
        <li>
          <strong>Purchases:</strong> Paddle, our merchant of record, collects your name, email,
          billing address and payment details and processes them under its own privacy policy. We
          receive your name, email, country and subscription status from Paddle to provide optional
          hosted support. We never see your full card details.
        </li>
        <li>
          <strong>Support email:</strong> the messages you send us, kept as long as needed to help
          you.
        </li>
        <li>
          <strong>Demo and server logs:</strong> our hosting provider processes IP addresses and
          request logs to operate and protect the site. The demo keeps client addresses in memory
          only, briefly, for rate limiting. Scenarios you run are synthetic and are shared with
          other visitors until the demo resets.
        </li>
      </ul>
      <p>
        We use no advertising or analytics cookies and no tracking pixels. The self-hosted
        AgentTaint software sends no telemetry to us.
      </p>
      <h2>Legal bases</h2>
      <p>
        Performing our contract with you (optional hosted support), your consent (waitlist, which
        you can withdraw anytime), and our legitimate interest in running and securing the site.
      </p>
      <h2>Processors</h2>
      <p>
        Paddle (payments, merchant of record) and our hosting provider (Render, which runs the site
        and its database). Data may be processed outside your country by these providers under
        their safeguards.
      </p>
      <h2>Your rights</h2>
      <p>
        You can ask to access, correct, export or delete your data, or object to its use, by
        emailing <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>. You may also complain to
        your local data protection authority. We do not sell personal data.
      </p>
      <h2>Changes</h2>
      <p>Updates to this policy will be posted on this page with a new date.</p>
    </LegalPage>
  );
}
