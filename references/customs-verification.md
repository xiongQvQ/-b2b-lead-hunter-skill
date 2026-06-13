# Customs Verification

Use customs/trade data as post-qualification evidence. This stage checks whether a plausible lead appears to import relevant products or source from Asia/China. It should strengthen or explain a lead; it should not replace company website research.

## When To Run

Run this after company research when:

- The company is already a plausible importer, distributor, wholesaler, OEM, integrator, or industrial buyer.
- The user asks for customs information, import records, shipment evidence, or China/Asia sourcing signals.
- A high or strong medium lead needs extra buying-intent evidence.

Do not run it for obvious rejects, directory-only records, or companies with no buyer-role evidence.

## Search Sources

Use public web search first. Useful queries:

```text
"Company Name" panjiva import shipment China
"Company Name" importgenius customs
"Company Name" import record supplier
"Company Name" shipment HS code
"Company Name" "importer" China
```

Common public sources include Panjiva snippets, ImportGenius snippets, customs directory pages, company self-descriptions, exhibitor pages, and public supplier/customer mentions.

## What To Extract

Capture only source-backed facts:

- Company name variant used by the customs source.
- Shipment count or frequency, if visible.
- Supplier names and supplier countries.
- Origin ports or origin countries.
- HS code or product description clues.
- Last visible shipment date.
- Source URL.
- Whether the visible evidence suggests Asia/China sourcing.
- Whether the product category appears relevant.

## Scoring Impact

- Confirmed relevant Asia/China imports: strong positive fit signal.
- Confirmed import activity from any origin: moderate positive fit signal.
- Stale or unrelated imports: weak signal; keep as note only.
- No customs data found: no penalty by itself.

European distributors, smaller private companies, agents, and companies buying through intermediaries may not appear in free customs tools. Do not downgrade them only because no record is found.

## Script Use

After collecting normalized search results for one company, run:

```bash
python scripts/customs_verify.py lead-runs/<slug>/customs-search-results.jsonl \
  --company "Company Name" \
  --output lead-runs/<slug>/customs-company-name.json
```

Then validate:

```bash
python scripts/validate_artifact.py customs-verification lead-runs/<slug>/customs-company-name.json
```

## Output Rules

Customs evidence must include source URLs. If the source is only a search snippet, mark confidence lower and keep the raw query/source in the run artifacts.

Do not claim a company imports a product unless the source supports that product category. If the source only proves import activity, say "import activity visible" rather than "imports this product."
