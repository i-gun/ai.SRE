---
name: "RCA Executive Summary"
description: "Generate a standalone executive summary from a completed RCA report, suitable for leadership distribution. Concise, evidence-referenced, and action-oriented."
argument-hint: "Provide: completed RCA report or correlation/root cause output."
agent: "RCA"
---

# RCA Executive Summary

Use this prompt to produce a leadership-ready executive summary from a completed RCA investigation, as a standalone artifact or for inclusion at the top of the full report.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@RCA, generate an executive summary for the following completed investigation.

Source: <RCA report file path or "use correlation and root cause outputs from current session">
Incident: <INCIDENT_NUMBER>
Service: <SERVICE_NAME>
Audience: Engineering leadership and operations management

Produce a concise executive summary with the following structure:

---

## Executive Summary — <SERVICE_NAME> — <INCIDENT_NUMBER>

**Date:** <YYYY-MM-DD>  
**Severity:** <P1 / P2 / P3>  
**Root Cause Category:** <CODE DEFECT / CONFIG DRIFT / DEPENDENCY FAILURE / OPERATIONAL/PROCESS>  
**Confidence:** <High / Medium / Low>  

### What Happened
2–3 sentences describing the observable failure, when it started, and when it was resolved.

### Why It Happened
2–3 sentences stating the root cause with a brief supporting evidence reference. No jargon — translate technical findings to business terms.

### Business Impact
- User-facing impact: <qualitative description>
- Duration: <HH:MM>
- MTTD: <minutes>
- MTTR: <minutes>
- Peak error rate: <%>
- Throughput reduction: <%>

### What Was Done
1–2 sentences describing the mitigation and resolution action taken.

### Recurrence Risk
<HIGH / MEDIUM / LOW / UNKNOWN> — <one sentence rationale based on similar incident analysis>

### Top 3 Actions to Prevent Recurrence
| # | Action | Type | Priority |
|---|---|---|---|
| 1 | <action> | <Corrective / Preventive / Observability> | <P1/P2/P3> |
| 2 | <action> | <Corrective / Preventive / Observability> | <P1/P2/P3> |
| 3 | <action> | <Corrective / Preventive / Observability> | <P1/P2/P3> |

### Full Report Reference
<Link or file path to the complete RCA document>

---

Summary requirements:
- Maximum 1 page when rendered
- No unexplained technical acronyms
- Each claim must be traceable to the full report (reference section numbers)
- Avoid speculation — only state what evidence supports
```

## Execution Requirements

- Source must be either a completed RCA report file or the active session's correlation and root cause outputs
- Do not generate an executive summary if root cause determination has not been completed
- Do not include code attribution details in the executive summary — reference the full report instead
- Translate error rate, latency, and throughput metrics to business-impact language where possible
