# Sprint 13 UX Audit

## Scope

Sprint 13 should make the existing V1 product feel like a strategic advisor with receipts, not a generated-object workspace.

## Page Audit

| Page | Primary user question | Current primary CTA | Above-the-fold risk | Sprint 13 action |
|---|---|---|---|---|
| Home / Projects | What does this product do and where should I start? | New Project / Seed Demo | Reads like an admin list with unreliable workspace-level object counts | Lead with product promise, use "Investigate New Idea", show project verdict/next action/evidence state |
| Project Header | What is the current state everywhere I go? | None | Stage and system health exist, but the verdict is not persistent enough | Add compact Verdict Bar under the header across all tabs |
| Overview | What is the current verdict and what should I do next? | Next Best Action | Good information exists, but "Current State" is softer than the product promise | Rename to Strategic Verdict, emphasize why, next action, and riskiest assumption |
| Research | What did the app investigate and conclude? | Run Research Sprint / Generate Research Memo | Process details, candidates, quality checks, and history can compete with conclusions | Lead with Research Result, collapse research run inspection and run-new-research details |
| Evidence | What sources support the analysis? | Add/retrieve evidence | Source list and retrieval can dominate supported findings/open questions | Lead with Evidence Summary, Supported Findings, Open Questions |
| Competitors | Who or what am I really competing against? | Analyze / add competitors | Competitor grouping is useful but strategic implication needs to be stronger | Add landscape summary, emphasize substitutes, remove unreliable metrics |
| Assumptions | What must be true for this idea to work? | Create validation plan | Strong page, but percentages and repeated CTAs need clearer labels | Put riskiest assumption first, use qualitative confidence/evidence labels |
| Validation | What should I test next and how? | Generate plan / log result | Assets can become a long generated-content wall | Show objective, step-by-step test plan, one expanded asset, prominent result logging |
| Decisions | What should I decide and why? | Record decision | Can feel like a blank form | Add suggested decision, rationale, missing evidence, and warning before premature build decisions |

## Terminology Cleanup

Replace primary UX labels where visible:

- Source candidate -> Source found
- Competitor candidate -> Competitor found
- Source-grounded memo -> Research memo
- Cited claims -> Supported findings
- Unsupported claims -> Open questions
- Research quality -> Trust checks
- Memory update -> Project update
- Workflow -> Research activity

## Metric Consistency Checks

- Remove workspace-level evidence/artifact/decision counts from home until accurate rollups exist.
- Use project overview counts for project cards.
- Explain when source count and supported-finding count differ.
- Avoid unexplained confidence percentages in primary page copy.

## First Implementation Slice

1. Add persistent project Verdict Bar.
2. Rename Overview "Current State" to "Strategic Verdict."
3. Add Riskiest Assumption to Overview.
4. Refactor Home / Project List around product promise and project cards.
5. Keep further tab refactors behind existing data and progressive disclosure.
