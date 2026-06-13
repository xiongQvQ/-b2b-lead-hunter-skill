# Query Lanes

Use multiple lanes. Do not let one lane dominate unless pilot data proves it works.

Default provider rule:

- Organic, platform, competitor, association, and contact-discovery search should use Hermes native web search or whatever web-search provider Hermes has enabled.
- Do not require Serper for ordinary web search.
- Maps/local place search may use `scripts/serper_maps.py` when `SERPER_API_KEY` is available.
- If Maps is unavailable, skip Maps and continue with other lanes.

## Organic Search

Purpose: find importers, distributors, wholesalers, and company pages.

Templates:

- `{product} importer {country}`
- `{product} distributor {country}`
- `{product} wholesaler {country}`
- `{product} agent {country}`
- `{application} equipment distributor {country}`
- `site:.{tld} {product} distributor`

## B2B Platform and Directory

Purpose: discover company profiles, then resolve official websites.

Templates:

- `site:europages.com {product} distributor {country}`
- `site:kompass.com {product} importer {country}`
- `site:wlw.de {product} Großhändler`
- `site:thomasnet.com {product} distributor`

Rule: platform pages are sources, not final truth. Try to find the official website before assigning high priority.

## Maps and Local Channel

Purpose: physical dealers, installers, wholesalers, showrooms, local branches.

Templates:

- `{product} distributor {city}`
- `{product} dealer {city}`
- `{category} wholesaler {city}`
- `{local_product_term} {local_distributor_term} {city}`

Maps should skew local language in non-English markets.

## Competitor Channel

Purpose: find companies already selling adjacent or competitor products.

Templates:

- `{competitor_brand} distributor {country}`
- `{competitor_brand} dealer {country}`
- `{competitor_brand} reseller {country}`
- `{competitor_brand} authorized distributor {country}`

Fields to set:

- `source_lane=competitor_channel`
- `related_brand`
- `channel_risk=exclusive_dealer|multi_brand|unknown`

Do not auto-reject competitor-product resellers. Reject only clear same-core-product manufacturers when they match negative criteria.

## Association and Exhibitor

Purpose: trade-fair and association member lists.

Templates:

- `{product} exhibition exhibitors {country}`
- `{industry} association members {country}`
- `{trade_fair_name} exhibitors {product}`
- `{application} suppliers association {country}`

## Brand Distributor Networks (High-ROI Lane)

Purpose: find pre-qualified distributors from official brand partner lists. These companies are already authorized to sell switch/component products — they are proven buyers with established supply chains.

Major switch and component brands publish their distributor/reseller lists publicly. Read the list page with Jina first, extract company names, then search each company's contact/email separately.

**Key brand distributor pages to mine:**

| Brand | Distributor List URL | Region |
|---|---|---|
| Cherry (switches & peripherals) | `cherry.de/en-us/distributors-resellers` | Global — Austria, Belgium, Germany, Czech, etc. |
| Honeywell (sensors & switches) | `sps-support.honeywell.com/s/article/Honeywell-Authorized-Distributors` | Global |
| ITW Switches | `itwswitches.com/distributors-emea` | EMEA |
| Omron (switches & relays) | `components.omron.com/eu-en/about/corporate/global-network/eu/distributor` | Europe |
| Comus International | `comus-intl.com/distributors/stocking-distributors` | Global |

**Workflow:**
1. Read the brand's distributor page with Jina: `python3 scripts/read_jina.py "<brand_distributor_url>"`
2. Extract company names (filter out IT resellers, B2C shops, and tiny retailers)
3. For each qualified company, search Tavily: `"{company_name}" email contact`
4. Look up decision makers via LinkedIn search: `"{company_name}" purchasing manager site:linkedin.com/in`
5. Infer email from company's known format, or use the generic contact

**Example from this session (Cherry → Austrian distributors):**
- `cherry.de/en-us/distributors-resellers` → Littlebit Technology GmbH (Austria), e-tec electronic GmbH (Austria)
- `components.omron.com/eu-en/...` → multiple European distributors
- Honeywell authorized list → Nicom Distribution (Italy)

**Filtering rules:**
- Keep: distributors, importers, wholesalers of electronic/electrical components
- Reject: PC/IT-only resellers (Bechtle, Ingram Micro IT), keyboard-only gaming shops, B2C consumer retailers
- Reject: companies already in your leads list (dedupe)
