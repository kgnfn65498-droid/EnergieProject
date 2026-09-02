# v32.3.22 Report Reliability Design

## Goal
Make the August 2026 production report internally consistent, source-grounded, and safe to freeze in Crash Recovery.

## Scope
- Fix central SMP coverage validation so summarized daily records are not misinterpreted as missing interval records when the month workflow has already produced valid daily month summaries.
- Keep report publication in the canonical `Data/02_Output/Rapportages/YYYY_MM` location only.
- Page 1: remove stale 8-day/July footer and page-count errors; preserve real August measurements and current financial offer summary.
- Page 2: populate supplier/offer-backed financial summary and annual forecast fields; do not claim unknown observed all-in monthly costs. Remove unsupported weather/graaddagen claims.
- Pages 3-13: remove demo/juli wording and hard-coded simulation values; drive visible values from adapter data and mark unavailable source-dependent values explicitly rather than inventing them.
- Use one consistent battery scenario output across pages where battery guidance appears.
- Dynamic source/quality labels must reflect actual configured/validated sources; EPEX may not be claimed when not configured.
- UI report back navigation should resolve immediately through ingress without artificial delay.
- Workflow status must distinguish successful report publication from unrelated optional/source validation faults and must not mark a successfully published P1-based report failed for the known SMP daily-summary representation.

## Non-goals
- No new external supplier API integration.
- No fabricated August all-in energy invoice amount.
- No broad architecture refactor outside the report/validation/UI paths required for this release.

## Acceptance
- Targeted regression tests cover every listed report inconsistency.
- Generated adapter data contains no July/demo fixture leakage.
- Source labels do not say EPEX unless configured.
- Page 1 and Page 2 finance show €150 current term, €153/month offer projection, €1,836/year projection, €1,800 expected annual payments, and -€36 expected balance.
- Pages 3-13 contain no phrases indicating fabricated/demo data or stale July actions.
- Report workflow can publish to the canonical folder without recreating `Data/01_Input/02_Output`.
