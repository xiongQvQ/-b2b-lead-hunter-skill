# Workflow

## Default Flow

1. Build `brief.json`.
2. Write `search-plan.md`.
3. Run pilot search.
4. Inspect candidates and decide continue/adjust/stop.
5. Run full search if pilot quality is acceptable.
6. Research company websites using homepage, product, about, contact, and supporting pages.
7. Use Jina or Browser/Camofox selectively to collect page text/DOM evidence.
8. Extract contacts with helper scripts when useful.
9. Score and split into strict leads, all leads, review, and rejected.
10. Write `run-report.md`.

## Pilot Rules

For a new product or region, run pilot first:

- 5-8 queries.
- 5-10 results per query.
- Inspect first 20-40 candidates.
- Estimate wrong-type rate.
- Identify best and worst lanes.

Do not continue to full run if direction is bad.

## Acceptance Gate

A strict accepted lead needs all four:

- Real company evidence.
- Buyer-role evidence.
- At least one contact channel.
- Source URL for every key claim.

If one of these is weak, the lead may go to `leads_all.csv` or `review.jsonl`, but not strict `leads.csv`.

## Stop Conditions

Stop and ask before spending more API calls when:

- Over 60% of pilot candidates are wrong customer type.
- Results are mostly direct manufacturers or competitors.
- Results are mostly B2C-only shops or local services.
- Results are mostly directories without official contact paths.
- Region drift is severe.
- Contactability is poor across most candidates.
- API failures, rate limits, or costs are abnormal.

## Round Feedback

After each round, record:

- Accepted count.
- High/medium/low/reject counts.
- Email coverage.
- Any-contact coverage.
- Official-site coverage.
- Best queries.
- Bad queries.
- Noise patterns.
- Next-round recommendations.

## Company Website Research

For each promising candidate, follow `references/company-website-research.md`:

- Homepage for identity and navigation.
- Products/Solutions/Applications for product fit.
- About/Company/Factory/Quality for legitimacy and role.
- Contact/Impressum/Footer for public contact channels.
- Team/News/Downloads/Catalog/Dealers for high-value enrichment.

Use Jina for clean markdown when it works. Use Browser/Camofox only when needed: Jina failure, JS-rendered pages, hidden contact widgets, language switchers, or visual official-site checks.
