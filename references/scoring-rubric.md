# Scoring Rubric

Scores must be evidence-driven. If the source only implies a claim, lower the score and write the uncertainty in `notes`.

Quality gates override `target_count`. Do not raise priority or relax required evidence to hit a numeric target.

## Fit Score

`fit_score` measures whether the company could plausibly buy, import, distribute, specify, integrate, resell, or use the seller's product.

- `0.85-1.00`: Exact ICP. The source explicitly shows the company distributes/imports/wholesales/uses the target product category.
- `0.65-0.84`: Strong adjacent fit. They sell or use close complementary products and have a clear buying path.
- `0.40-0.64`: Plausible but incomplete. Industry matches, but buyer role or product overlap is indirect.
- `0.15-0.39`: Weak. Related industry but no clear buying path.
- `0.00-0.14`: Reject or near reject. Wrong entity, no plausible need, direct competitor, or explicit negative criterion.

## Contactability Score

- `0.85-1.00`: Direct person email or strong generic sales/export email plus phone/contact form.
- `0.65-0.84`: Generic company email plus phone/contact page/social profile.
- `0.40-0.64`: Contact form, phone, LinkedIn/company social, or partial contact data.
- `0.15-0.39`: Website only, weak contact route.
- `0.00-0.14`: No usable contact channel.

## Evidence Score

- `0.85-1.00`: Official website or authoritative profile confirms product, role, and contact.
- `0.65-0.84`: Official website confirms most claims; some contact data comes from snippets or directories.
- `0.40-0.64`: Directory/profile evidence with limited official confirmation.
- `0.15-0.39`: Search snippets only or weak secondary sources.
- `0.00-0.14`: Unverifiable.

## Priority

Derive priority conservatively:

- `high`: `fit_score >= 0.70`, `contactability_score >= 0.55`, and `evidence_score >= 0.60`.
- `medium`: `fit_score >= 0.50` and at least one reachable contact channel.
- `low`: plausible but weak evidence or weak contactability.
- `reject`: no buying path, direct competitor, wrong entity, or explicit negative criteria.

## CSV Policy

- `leads.csv`: high + medium only.
- `leads_all.csv`: high + medium + low.
- `low` requires `review_required=true`, `uncertainty_reason`, and `missing_evidence`.

Do not put a lead into strict `leads.csv` unless real company evidence, buyer-role evidence, at least one contact channel, and source URLs are present.

## Competitor Rule

Only reject as competitor when evidence clearly shows the company manufactures or owns a brand of the same core product. Do not reject distributors, importers, OEMs, or integrators just because they sell similar products.
