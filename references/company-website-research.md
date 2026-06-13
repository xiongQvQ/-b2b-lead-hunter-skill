# Company Website Research

Use this workflow when enriching a known company website or deciding whether a candidate is a real B2B buyer/channel.

The goal is not just to scrape emails. The goal is to understand what the company is, whether it matches the ICP, and which contact channels are public and source-backed.

## Tool Priority

**`scripts/read_jina.py` is the primary tool for reading any company page. Always try it first.**

1. **Hermes native web/search snippets**
   - Use for quick company identity checks, external profiles, and search result context.
   - Good for finding alternate official domains and contact pages.

2. **Jina Reader via `scripts/read_jina.py`** — primary tool for reading any page
   - Use for every homepage, product page, about page, contact page, and directory page you want to inspect.
   - Call it explicitly: `python scripts/read_jina.py https://www.example.com`
   - Fast (5-15s), returns clean markdown, reliable for static content.
   - If Jina returns 403, empty content, a JS shell, or irrelevant content, do not keep retrying with Jina — fall back to browser.

3. **Browser/Camofox** — fallback when Jina fails
   - Use when `read_jina.py` failed or returned unusable content.
   - Also use when you need page interaction: click tabs, switch language, reveal hidden contact widgets, inspect DOM.
   - Do not bypass login, paywalls, CAPTCHA, or access controls.

## Page Order

### 1. Homepage

Collect:

- Official company name.
- Primary products/services.
- Language and market signals.
- Navigation structure.
- Obvious contact links in header/footer.
- Whether the site looks like a real company website.

Decision:

- If homepage is a directory, marketplace, article, school, media, government, or unrelated page, mark as reject/review before spending more effort.

### 2. Products / Solutions / Applications

Collect:

- Concrete product categories.
- Applications and target industries.
- Whether the company sells, distributes, imports, installs, integrates, manufactures, or uses the product.
- Certifications or standards.

Decision:

- Do not score high from broad industry relevance alone.
- A distributor/importer/wholesaler/agent signal is stronger than a generic product mention.

### 3. About / Company / Factory / Quality

Collect:

- Company history.
- Factory/trading/channel role.
- Certificates.
- Export markets.
- Customer types.
- Brands represented or distributed.

Decision:

- If the company clearly manufactures the same core product and the brief excludes competitors, reject or mark competitor risk.
- If it is a multi-brand reseller/distributor, keep as a potential lead.

### 4. Contact / Impressum / Footer

Collect:

- Emails.
- Phone numbers.
- Address.
- Contact form.
- WhatsApp/WeChat.
- LinkedIn/company social.
- Named people and titles.

Rules:

- Every contact channel needs `source_url`.
- Generic business emails are acceptable.
- Inferred personal emails are auxiliary only.
- Use `scripts/extract_contacts.py` on saved page text/markdown/html when useful.

### 5. Team / News / Downloads / Catalog / Dealers

Use selectively for high-value candidates.

Collect:

- Decision-maker names and titles.
- PDF/catalog product proof.
- Exhibitions/trade-fair participation.
- Dealer or distributor pages.
- Case studies or customer segments.

Decision:

- Decision-maker discovery is phase-two enrichment, not a hard gate for accepting a lead.

## External Search Follow-Up

Use Hermes native search after first-pass website review:

- `"{company_name}" email`
- `"{company_name}" contact`
- `"{company_name}" impressum`
- `"{company_name}" LinkedIn`
- `"{company_name}" purchasing manager`
- `"{company_name}" procurement manager`
- `"{company_name}" distributor`
- `"{company_name}" site:made-in-china.com`
- `"{company_name}" site:europages.com`
- `"{company_name}" site:kompass.com`

Use external results as supporting evidence, not automatic truth.

## Browser/Camofox Use Cases

Use Browser/Camofox when:

- Jina returns 403 or empty/irrelevant content.
- The page is JavaScript-rendered.
- Contact info appears in a popup, footer, tab, or floating widget.
- Language switching is needed.
- DOM links such as `mailto:` or `tel:` are present but not visible in markdown.
- Visual inspection is needed to confirm whether a page is official.

Suggested browser actions:

- Open homepage.
- Inspect header/footer links.
- Click Contact/About/Products language links.
- Capture visible emails/phones/contact forms.
- Extract `mailto:` and `tel:` links from DOM if available.
- Save useful page text/HTML before running `extract_contacts.py`.

Do not use Browser/Camofox to bypass authentication, CAPTCHA, paywalls, or access controls.

## Evidence Output

For each enriched company, write:

```json
{
  "company_name": "",
  "website": "",
  "official_site_found": true,
  "source_quality": "official|platform|directory|snippet|mixed",
  "business_type": [],
  "buyer_role_evidence": [
    {"claim": "", "source_url": ""}
  ],
  "product_fit_evidence": [
    {"claim": "", "source_url": ""}
  ],
  "emails": [],
  "phones": [],
  "social": {},
  "decision_makers": [],
  "missing_evidence": [],
  "uncertainty_reason": "",
  "review_required": false
}
```

## Acceptance Reminder

Strict `leads.csv` requires:

- Real company evidence.
- Buyer-role evidence.
- At least one contact channel.
- Source URL for each key claim.

If the site is hard to read but the company looks promising, put it in `review.jsonl` rather than forcing a high score.
