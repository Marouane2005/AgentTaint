"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { joinWaitlist } from "@/lib/api";

export function WaitlistForm({ source = "landing" }: { source?: string }) {
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setState("busy");
    try {
      setMessage(await joinWaitlist(email.trim(), website, source));
      setState("done");
      setEmail("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
      setState("error");
    }
  }

  return (
    <form className="waitlist" onSubmit={onSubmit} aria-label="Join the hosted support waitlist">
      <div className="waitlist-row">
        <input
          type="email"
          required
          maxLength={254}
          autoComplete="email"
          placeholder="you@company.com"
          aria-label="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button className="btn" type="submit" disabled={state === "busy"}>
          {state === "busy" ? "Joining…" : "Join waitlist"}
        </button>
      </div>
      {/* Honeypot for bots; hidden from people and screen readers. */}
      <input
        className="hp"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        name="website"
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
      />
      {message ? (
        <p className={state === "error" ? "form-msg error" : "form-msg"} role="status">
          {message}
        </p>
      ) : null}
      <p className="fine">We store only your email to notify you about AgentTaint releases and optional hosted support. No spam.</p>
    </form>
  );
}
