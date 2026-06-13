# Design Decisions

Source of truth for the current design:

- Workspace decision log: `docs/b2b-lead-hunter-decisions.md`

Operational summary:

- Optimize for physical-product export B2B channel discovery.
- Prioritize importers, distributors, wholesalers, and agents.
- Use organic and B2B/platform search as primary lanes; use Maps as auxiliary.
- Require company reality, buyer-role evidence, contact channel, and source URL before strict CSV inclusion.
- Export strict and full CSV separately.
- Pilot before full run.
- Keep scripts deterministic; keep business judgment in Hermes.
- Quality gates override target count.

