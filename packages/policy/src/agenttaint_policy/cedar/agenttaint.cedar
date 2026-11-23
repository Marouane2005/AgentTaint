// AgentTaint authorization policy (Cedar).
//
// The gateway computes deterministic facts about a tool call (risk tier,
// provenance status, structured-grant coverage, untrusted influence, ...)
// and passes them as the request context. These policies decide.
//
// Two actions are evaluated in order:
//   1. Action::"execute"               permitted  -> ALLOW
//                                      forbidden  -> BLOCK (named forbid)
//   2. Action::"execute_with_confirmation"
//                                      permitted  -> CONFIRM (human approval)
//   anything else                                 -> BLOCK (fail closed)
//
// Every policy carries an @id equal to the policy_id recorded in the audit
// log. When several policies match, the one that appears first in this file
// wins, which mirrors the ordered rules of the Python reference policy
// (agenttaint_policy.adapter.ProvenanceAwarePolicy).

// ---------------------------------------------------------------- hard blocks
@id("fail-closed-registry-unavailable")
forbid (principal, action, resource)
when { context.tier == "HIGH" && !context.registry_available };

@id("denylist-tool")
forbid (principal, action, resource)
when { context.denylisted };

// --------------------------------------------- bound human confirmation
@id("confirmation-bound-allow")
permit (principal, action == Action::"execute", resource)
when { context.confirmation_validated };

@id("blocked-recipient")
forbid (principal, action, resource)
when { context.recipient_blocked && !context.granted && !context.confirmation_validated };

// ------------------------------------------------------------------- HIGH
@id("allow-high-authorized")
permit (principal, action == Action::"execute", resource)
when { context.tier == "HIGH" && context.granted };

@id("confirm-inferred-untrusted-influence")
permit (principal, action == Action::"execute_with_confirmation", resource)
when {
  context.tier == "HIGH" && !context.granted && !context.confirmation_validated &&
  context.untrusted_influence && context.influence_inferred_only &&
  context.cfg_confirm_untrusted_influence
};

@id("block-inferred-untrusted-influence")
forbid (principal, action, resource)
when {
  context.tier == "HIGH" && !context.granted && !context.confirmation_validated &&
  context.untrusted_influence && context.influence_inferred_only &&
  !context.cfg_confirm_untrusted_influence
};

@id("confirm-untrusted-influence")
permit (principal, action == Action::"execute_with_confirmation", resource)
when {
  context.tier == "HIGH" && !context.granted && !context.confirmation_validated &&
  context.untrusted_influence && !context.influence_inferred_only &&
  context.cfg_confirm_untrusted_influence
};

@id("block-untrusted-influence")
forbid (principal, action, resource)
when {
  context.tier == "HIGH" && !context.granted && !context.confirmation_validated &&
  context.untrusted_influence && !context.influence_inferred_only &&
  !context.cfg_confirm_untrusted_influence
};

@id("block-unknown-high-risk")
forbid (principal, action, resource)
when {
  context.tier == "HIGH" && !context.granted && !context.confirmation_validated &&
  !context.untrusted_influence && context.provenance_unknown_or_partial &&
  context.cfg_fail_closed_unknown_high
};

@id("confirm-unknown-high-risk")
permit (principal, action == Action::"execute_with_confirmation", resource)
when {
  context.tier == "HIGH" && !context.granted && !context.confirmation_validated &&
  !context.untrusted_influence && context.provenance_unknown_or_partial &&
  !context.cfg_fail_closed_unknown_high
};

@id("confirm-high-risk")
permit (principal, action == Action::"execute_with_confirmation", resource)
when {
  context.tier == "HIGH" && !context.granted && !context.confirmation_validated &&
  !context.untrusted_influence && !context.provenance_unknown_or_partial
};

// ----------------------------------------------------------------- MEDIUM
@id("allow-medium-authorized")
permit (principal, action == Action::"execute", resource)
when {
  context.tier == "MEDIUM" && context.untrusted_influence &&
  context.granted && !context.influence_inferred_only
};

@id("confirm-medium-inferred-untrusted")
permit (principal, action == Action::"execute_with_confirmation", resource)
when {
  context.tier == "MEDIUM" && !context.confirmation_validated &&
  context.untrusted_influence && context.influence_inferred_only &&
  (context.cfg_confirm_medium_untrusted || context.cfg_confirm_untrusted_influence)
};

@id("confirm-medium-untrusted-influence")
permit (principal, action == Action::"execute_with_confirmation", resource)
when {
  context.tier == "MEDIUM" && !context.confirmation_validated &&
  context.untrusted_influence && !context.influence_inferred_only && !context.granted &&
  (context.cfg_confirm_medium_untrusted || context.cfg_confirm_untrusted_influence)
};

@id("block-medium-untrusted-influence")
forbid (principal, action, resource)
when {
  context.tier == "MEDIUM" && !context.confirmation_validated &&
  context.untrusted_influence && !(context.granted && !context.influence_inferred_only) &&
  !(context.cfg_confirm_medium_untrusted || context.cfg_confirm_untrusted_influence)
};

@id("block-medium-undeclared-lineage")
forbid (principal, action, resource)
when {
  context.tier == "MEDIUM" && !context.confirmation_validated &&
  !context.untrusted_influence && context.cfg_scrutinize_medium_undeclared &&
  !context.lineage_declared && context.session_untrusted_seen && !context.granted &&
  context.cfg_fail_closed_unknown_medium
};

@id("confirm-medium-undeclared-lineage")
permit (principal, action == Action::"execute_with_confirmation", resource)
when {
  context.tier == "MEDIUM" && !context.confirmation_validated &&
  !context.untrusted_influence && context.cfg_scrutinize_medium_undeclared &&
  !context.lineage_declared && context.session_untrusted_seen && !context.granted &&
  !context.cfg_fail_closed_unknown_medium
};

@id("allow-medium")
permit (principal, action == Action::"execute", resource)
when {
  context.tier == "MEDIUM" && !context.untrusted_influence &&
  !(context.cfg_scrutinize_medium_undeclared && !context.lineage_declared &&
    context.session_untrusted_seen && !context.granted)
};

// -------------------------------------------------------------------- LOW
@id("allow-low")
permit (principal, action == Action::"execute", resource)
when { context.tier == "LOW" };
