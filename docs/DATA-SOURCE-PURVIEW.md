# Data source: Microsoft Purview Compliance Manager

This document maps **Microsoft Purview Compliance Manager** concepts and values to the Compliance Advisor schema and API so that data reflects what you can pull from Purview.

## Two score types in this solution

| Source | What it is | Where in the app |
|--------|------------|------------------|
| **Microsoft Secure Score** (Graph API) | Security posture score from Microsoft Graph (`/security/secureScores`). Per-tenant, per-day; control categories (Identity, Data, Device, etc.). | `secure_scores`, `control_scores`, `control_profiles`; optional for benchmarks. |
| **Purview Compliance Manager** | Compliance score from **improvement actions** within assessments. Points per action, per assessment, and an overall compliance score. | `compliance_scores`, `assessments`, `assessment_controls`; dashboard “Compliance Score”, assessments, improvement actions. |

The **dashboard and advisor are built around Purview Compliance Manager**: assessments, controls, improvement actions, and the **compliance score** (points achieved vs. total possible from improvement actions). Secure Score can still be ingested for comparison or extra context.

---

## Purview Compliance Manager concepts

### Compliance score (Purview)

- **What it is:** Progress in completing **improvement actions** within controls. Calculated from points achieved vs. points possible.
- **Levels:** Improvement action → Assessment → **Overall compliance score**.
- **Initial score:** Based on the **Data Protection Baseline** assessment (NIST CSF, ISO, FedRAMP, GDPR).
- **Stored in:** `compliance_scores` (current_score, max_score, category e.g. overall).

Ref: [Compliance Manager scoring](https://learn.microsoft.com/en-us/purview/compliance-manager-scoring)

### Assessments

- **What they are:** Evaluations against a regulation, standard, or certification (e.g. NIST 800-53, ISO 27001, SOC 2). Each assessment contains **controls** and **improvement actions**.
- **Stored in:** `assessments` (assessment_id, display_name, regulation, status, compliance_score, passed_controls, failed_controls, total_controls, etc.).
- **Status:** e.g. active, expired, draft.

Ref: [Build and manage assessments](https://learn.microsoft.com/en-us/purview/compliance-manager-assessments)

### Improvement actions (controls in our schema)

- **What they are:** Specific steps to meet control requirements. Each has implementation status, test status, points, owner, and remediation guidance.
- **Stored in:** `assessment_controls` (one row per improvement action / control within an assessment).

#### Implementation status (Purview)

Use these values so exports and UI match Compliance Manager:

| Purview UI | Recommended value in DB / API |
|------------|-------------------------------|
| Not implemented | `notImplemented` |
| Planned | `planned` |
| Alternative implementation | `alternative` |
| Implemented | `implemented` |
| Out of scope | `outOfScope` |

Ref: [Working with improvement actions](https://learn.microsoft.com/en-us/purview/compliance-manager-improvement-actions) — “Implementation status” dropdown.

#### Test status (Purview)

| Purview UI | Recommended value in DB / API |
|------------|-------------------------------|
| Not assessed | `notAssessed` |
| None | `none` |
| In progress | `inProgress` |
| Partially tested | `partiallyTested` |
| To be determined | `toBeDetermined` |
| Could not be determined | `couldNotBeDetermined` |
| Out of scope | `outOfScope` |
| Failed low risk | `failedLowRisk` |
| Failed medium risk | `failedMediumRisk` |
| Failed high risk | `failedHighRisk` |
| Passed | `passed` |

Ref: [Working with improvement actions](https://learn.microsoft.com/en-us/purview/compliance-manager-improvement-actions) — “Test status” dropdown.

#### Improvement action categories (Purview)

Categories used in Compliance Manager for grouping:

- Control Access  
- Discover and Respond  
- Govern Information  
- Infrastructure Cloud  
- Manage Compliance  
- Manage Devices  
- Manage Internal Risks  
- Privacy Management  
- Protect Against Threats  
- Protect Information  

These can be stored in `control_category` or a dedicated category field when you have them from export or API.

#### Action type (Purview)

- **Technical** — Implemented in the solution (e.g. configuration).
- **Nontechnical** — Documentation or operational; managed by the organization.

Use where relevant for filtering or display (e.g. technical vs nontechnical).

---

## Schema mapping summary

| Purview concept | Table / view | Key columns |
|-----------------|-------------|-------------|
| Overall compliance score over time | `compliance_scores`, `v_compliance_trend` | current_score, max_score, category = 'overall' |
| Latest compliance score per tenant | `v_latest_compliance_scores` | compliance_pct, current_score, max_score |
| Assessments | `assessments`, `v_assessment_summary` | assessment_id, display_name, regulation, compliance_score, passed_controls, failed_controls, total_controls |
| Improvement actions (controls) | `assessment_controls`, `v_assessment_gaps`, `v_improvement_actions` | control_name, control_family, implementation_status, test_status, score, max_score, score_impact, implementation_details, test_plan |
| Regulation coverage | `v_regulation_coverage` | regulation, assessment_count, overall_pass_rate |
| Department rollup | `v_compliance_department_rollup` | department, avg_compliance_pct, total_failed_controls |

---

## How to get Purview data into the app

- **Export:** Compliance Manager supports **Export actions** (Excel). You can map that export into `assessments` and `assessment_controls` (and optionally `compliance_scores` if you derive or sync scores).
- **API:** When available, use Microsoft Graph / Purview compliance APIs for assessments and improvement actions; map responses to the same tables and status values above.
- **Sync:** Ensure implementation_status and test_status use the values in this doc so filters and labels match the Purview UI.

---

## Dashboard and API alignment

- **Compliance Score** in the dashboard = Purview **compliance score** (from `v_latest_compliance_scores`, `v_compliance_trend`).
- **Assessment Summary** = Purview **assessments** (from `v_assessment_summary`).
- **Improvement Actions** = Purview **improvement actions** (from `v_improvement_actions`); columns and filters use implementation_status and test_status as above.
- **Regulation coverage** = Pass rates per **regulation** across assessments (`v_regulation_coverage`).

Using these mappings ensures the data reflects what you can pull from **Microsoft Purview Compliance Manager**.
