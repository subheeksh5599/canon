# Doctrine Specification — CANON

The doctrine is the venue's evolving economic law. This document formalizes its lifecycle.

## The lifecycle

```
observation            raw evidence attached to a transaction
   |                          |
   v                          v
case (RAW)            validated against a real venue transaction; standing checked
   |                          v
case (RESOLVED)       adjudicator (never a party) fixes outcome + loss
   |                          |
   v                          v
evidence confidence   HIGH (on-chain tx) / MEDIUM (attestation) / LOW (text)
   |                          |
   |        LOW can resolve a case but can NEVER seed doctrine
   v                          v
precedent candidate   pattern (normalized job class) + confirmed failure counted
   |                          |
   v                          v
signal levels         1 SIGNAL · 2 MONITOR · 3 CANDIDATE · 5 ACTIVATE
   |                          |
   v                          v
doctrine activation    vN -> vN+1: new Rule stored in REFERENCE tier with
                       provenance (created_by_case, supporting_case_ids, checksum)
   |                          |
   v                          v
doctrine supersession  older version archived (readable, byte-identical)
   |                          |
   v                          v
appeal                 challenger posts a bond -> rule frozen for new terms
   |                          |
   +--- rejected: bond forfeited to pool, doctrine unchanged
   |                          |
   +--- accepted: rule relaxed, provenance-linked to appeal -> vN+2
   |                          |
   v                          v
doctrine amendment      archive of the amended version; future terms use vN+2
   |                          |
   v                          v
decay                  rules age ACTIVE -> WEAKENING -> ARCHIVED (30/90 days)
                       unless refreshed by new supporting cases
```

## Determinism invariants

1. Same facts + same doctrine = same terms (pure function; no clock, no RNG, no LLM on the money path).
2. The most-specific matching rule wins (`specificity()` = number of active triggers).
3. Equal specificity with different rule ids raises `RuleConflictError` — the venue refuses arbitrariness.
4. Terms respect bounds at schema level: upfront ∈ [0, value], bond ratio ∈ [0,1], coverage ∈ [0,1], milestones ≥ 1 and > 0.
5. Funded terms are immutable for the life of the transaction (snapshot semantics, `test_t016`).

## Canonical rule template (what a doctrine rule looks like)

```json
{
  "rule_id": "CANON-001-research",
  "status": "ACTIVE",
  "job_classes": ["research"],
  "min_job_value_usd": 0,
  "require_new_counterparty": false,
  "require_failure_rate_ge": null,
  "min_supporting_cases": 5,
  "upfront_cap_ratio": 0.25,
  "milestone_count_min": 3,
  "bond_ratio": 0.2,
  "coverage_ratio": 0.8,
  "supporting_case_ids": ["case-…", "case-…", "case-…", "case-…", "case-…"],
  "evidence_confidence": "HIGH",
  "created_by_case": "case-…",
  "effective_at": "2026-09-08T…",
  "last_supported_at": null
}
```

## Evidence weighting

- HIGH: on-chain verified transaction (the venue's own executed transaction).
- MEDIUM: signed attestation / adjudicator record.
- LOW: uncorroborated text — resolves a case, never seeds a rule.

Only resolved cases with HIGH/MEDIUM confidence count toward the activation thresholds. Mirror-image claims (buyer failure + provider dispute) never resolve automatically and cannot seed doctrine.

## Why this is dynamic storage

The doctrine is not a settings file. Rules are born from case evidence, amended by appeals, refreshed by new supporting cases, and retired by decay. The stored rule — not the code — is what future transactions read. Removing Sibyl removes the rule, the evidence, and the ability to construct terms at all.
