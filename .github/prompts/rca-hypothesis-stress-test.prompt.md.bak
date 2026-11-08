---
name: "RCA Hypothesis Stress-Test"
description: "Challenge all RCA hypotheses against the full evidence set, reject weak candidates with explicit rationale, and produce a ranked final hypothesis list with confidence scores ready for root cause determination."
argument-hint: "Provide: hypothesis list and full evidence streams from deep investigation output."
agent: "RCA"
---

# RCA Hypothesis Stress-Test

Use this prompt during Phase 3 (Synthesis and Challenge) to rigorously test each hypothesis before selecting a root cause.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@RCA, stress-test the following hypotheses against all available evidence.

Hypotheses under test:
<Paste hypothesis list from correlation output, one per line:>
- H1: <statement>
- H2: <statement>
- H3: <statement>

Evidence streams available:
- New Relic log forensics: <summary or "see investigation output">
- ServiceNow mining: <summary or "see investigation output">
- Jira lifecycle: <summary or "see investigation output">
- Confluence context: <summary or "see investigation output">
- AzureGit attribution: <summary, confidence level, or "deferred/unverified">
- Similar incidents: <recurrence_risk and top pattern or "not available">

For each hypothesis, apply the following rejection criteria:
1. Does contradicting evidence outweigh supporting evidence?
2. Does the hypothesis fail to explain the timing of the first observed symptom?
3. Does the hypothesis require assuming facts NOT present in the evidence?
4. Is the confidence score below 0.3 (normalized)?

For each hypothesis, return:
- hypothesis_id
- statement
- supporting_evidence (list with source references)
- contradicting_evidence (list with source references)
- confidence (high / medium / low — justify the score)
- outcome: Accepted / Rejected
- rejection_reason (required if rejected)
- root_cause_category (code_defect / config_drift / dependency_failure / operational_process)

Final output:
- Ranked list of ACCEPTED hypotheses by confidence (descending)
- Rejected hypotheses list with rationale
- If top two accepted hypotheses are within 0.1 confidence of each other, flag as "ambiguous" and present both for human review
- Identify: trigger, amplifiers, detection_gaps from accepted hypothesis evidence
```

## Execution Requirements

- Do not accept a hypothesis without at least one supporting evidence reference
- Do not reject a hypothesis without stating the specific contradicting evidence
- Do not present a rejected hypothesis as a candidate root cause
- If all hypotheses are rejected, report that state explicitly and request additional evidence streams
- Log all assumptions made during stress-testing in `assumptions_log`
