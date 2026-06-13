# Decision-Maker Discovery & Email Inference

Phase-two enrichment for high and strong medium leads. After verifying a company's buyer role (Steps 1-5), find actual decision-makers (procurement managers, buyers, product managers) and their contact channels.

**For Chinese AI/tech startup founders and Asian decision-makers, see `references/chinese-founder-contact-discovery.md`** — the strategies below target Western B2B procurement roles and may not apply to Chinese founders.

This stage is required before outreach when the user asks for employee-level contacts. The target is not `info@` or `sales@`; the target is named public business contacts such as procurement, purchasing, sourcing, product, management, or owner/operator contacts.

## Prerequisites

- Tavily API key configured in environment or local config, if Tavily is used. Search via `POST https://api.tavily.com/search` with `{"api_key":"...","query":"...","search_depth":"basic","max_results":8}`. Do not assume any hardcoded fallback exists.
- Company name and domain verified from Step 5.
- Region code for role-language mapping (DE, PL, AE, or GLOBAL).

## Workflow

### Deterministic Script Flow

Generate a search plan from qualified leads:

```bash
python scripts/enrich_decision_makers.py \
  --leads lead-runs/<slug>/leads.jsonl \
  --query-plan lead-runs/<slug>/decision-maker-search-plan.jsonl
```

Execute those queries with Hermes native web search. The pattern is:

```text
role + company -> person profile/name
person + company/domain -> public email, phone, profile, or directory contact
```

Then normalize and merge:

```bash
python scripts/enrich_decision_makers.py \
  --leads lead-runs/<slug>/leads.jsonl \
  --search-results lead-runs/<slug>/decision-maker-search-results.jsonl \
  --decision-makers-output lead-runs/<slug>/decision-makers.jsonl \
  --enriched-leads-output lead-runs/<slug>/leads.enriched.jsonl
```

Validate:

```bash
python scripts/validate_artifact.py decision-makers lead-runs/<slug>/decision-makers.jsonl
python scripts/validate_artifact.py leads lead-runs/<slug>/leads.enriched.jsonl
```

### Step 0: Direct Website Harvesting (Highest ROI — Do this FIRST)

Before LinkedIn or third-party databases, harvest the company's OWN website. This is BY FAR the most productive source of verified contact info.

**Target pages in order:**
1. /contact, /kontakt, /contacto, /about/contact
2. /team, /management, /ansprechpartner, /our-team, /leadership
3. /about, /about-us, /unternehmen
4. /impressum, /imprint, /legal-notice (German companies: REQUIRED by law — always check)
5. /careers, /jobs

**Real example — Halfmann Schrauben (Germany):**
The /ansprechpartner/ page had a complete table:
- Edis Civic | Geschaeftsleitung/Prokurist | edis.civic@halfmann-schrauben.de
- Anid Sahman | Einkauf (Purchasing) | anid.sahman@halfmann-schrauben.de
- Dean Guenther | Einkauf (Purchasing) | dean.guenther@halfmann-schrauben.de
This beats any LinkedIn search. Always check first.

**German role keywords for identifying decision-makers:**
- Einkauf / Einkaeufer = Purchasing/Buyer
- Leiter Einkauf = Head of Purchasing
- Geschaeftsfuehrer = Managing Director/CEO
- Prokurist = Authorized Officer
- Vertrieb = Sales

### Step 0.5: Company Brochure / PDF Harvesting

Many companies host PDF brochures containing contact cards. These are public marketing materials.

**Search:**
web_search(f"site:{domain} filetype:pdf brochure OR catalog OR contact")

**Real example — A. Lyons & Co. (USA):**
Brochure on their website contained:
- Rick Fine | VP Industrial Products | rick.fine@alyons.com | Cell: 334-722-0098
Also cross-listed in ASSEMBLY Magazine directory. Confirmed public info.

### Step 0.75: Industry Directory & Supplier Directory Listings

Industry-specific directories often have richer contact info than LinkedIn because companies PAY to be listed. Additionally, **supplier linecard directories** (where manufacturers list their distributors) often publish office-level email contacts.

**Best directories:**
- **US:** ThomasNet, Wholesale Central, ASSEMBLY Magazine directory
- **Europe:** Europages, Kompass, WLW (Wer Liefert Was)
- **UK:** esources.co.uk
- **Global:** TradeWheel, Go4WorldBusiness
- **Supplier linecard directories:** ThePartsDirect.com, Zago.com/manufacturers

**ThePartsDirect.com is especially valuable for distributor contacts.** When a manufacturer lists their distributors on ThePartsDirect, it includes per-office email addresses — not just generic info@. This was the most productive source for Bisco Industries (8 regional office emails found in one search).

Search:
```
web_search(f'"{company_name}" site:thepartsdirect.com OR site:assemblymag.com OR site:europages.com')
web_search(f'"{company_name}" "purchasing" OR "contact"')
```

**Real example (2026-05):** Bisco Industries
```
Search: "Bisco Industries" site:thepartsdirect.com
Found on: thepartsdirect.com/biscoindustries/linecard
Result: 8 regional offices each with named contact and email (nzech@biscoind.com, hdaffin@biscoind.com, etc.)
Value: Direct email access to local decision-makers across the US and Canada
```

Search for employees at the company by role, filtering for LinkedIn `/in/` profiles.

**Method (do this inline with execute_code, no script required):**

```python
# For each company, search Tavily with role keywords:
queries = [
    f'"{company_name}" Einkauf site:linkedin.com/in',        # German: purchasing
    f'"{company_name}" Vertrieb site:linkedin.com/in',       # German: sales
    f'"{company_name}" Geschäftsführer site:linkedin.com/in', # German: managing director
    f'"{company_name}" purchasing manager site:linkedin.com/in',
    f'"{company_name}" procurement site:linkedin.com/in',
]

# For Poland:
#   f'"{company_name}" zakupy site:linkedin.com/in'
#   f'"{company_name}" kierownik site:linkedin.com/in'
# For UAE:
#   f'"{company_name}" purchase manager site:linkedin.com/in'
#   f'"{company_name}" general manager site:linkedin.com/in'
```

**Parse results:**
- Filter URLs containing `linkedin.com/in/`
- Verify company name appears in title or snippet (avoid namesakes — "Eve Smith" ≠ EVE GmbH employee)
- Extract name from "Name – Title | LinkedIn" format: split on ` – ` or ` - `, take first part
- Rate-limit: 0.3s between Tavily calls

**Role keywords by region:**

| Region | Keywords |
|--------|----------|
| Germany | Einkauf, Einkäufer, Vertrieb, Geschäftsführer, Produktmanager, Purchasing Manager, Procurement, Supply Chain, Sourcing |
| Poland | zakupy, zaopatrzenie, kierownik zakupów, dyrektor, Prezes Zarządu (CEO), Purchasing Manager, Procurement, Product Manager, Co-owner |
| UAE | Purchasing Manager, Procurement Manager, Supply Chain, Sourcing, General Manager, Import Manager, Buyer |
| GLOBAL | Purchasing Manager, Procurement Manager, Supply Chain Manager, Sourcing Manager, Buyer, Import Manager, Product Manager |

### Step 2: Email Format Detection

Detect the company's email naming pattern from any known employee emails.

**Method (do inline):**

```python
# Search Tavily for known emails at the domain
results = tavily_search(f'"@{domain}" email')

# Extract emails and detect format:
# first.last@domain.com → format = "first.last"
# first_last@domain.com → format = "first_last"
# flast@domain.com     → format = "flast"

# SKIP generic prefixes: info, sales, vertrieb, contact, support, office
```

**Common formats:**
| Format | Pattern | Example |
|--------|---------|---------|
| first.last | `john.doe@company.com` | Rutronik, SOS electronic |
| first_last | `john_doe@company.com` | Some German companies |
| flast | `jdoe@company.com` | Smaller companies |
| f.last | `j.doe@company.com` | UK/US companies |
| first | `john@company.com` | Small companies |

### Step 3: Email Inference

Given a person's name from LinkedIn + detected email format, generate their likely email.

**Method (do inline, no script required):**

```python
def infer_email(name, domain, format_hint=None):
    parts = name.strip().split()
    first = parts[0].lower()
    last = parts[-1].lower()
    # Handle umlauts: ä→ae, ö→oe, ü→ue, ß→ss
    # Handle Polish: ą→a, ć→c, ł→l, ń→n, ó→o, ś→s, ź→z, ż→z
    fi, li = first[0], last[0]
    
    formats = {
        "first.last": f"{first}.{last}@{domain}",
        "first_last": f"{first}_{last}@{domain}",
        "flast": f"{fi}{last}@{domain}",
        "f.last": f"{fi}.{last}@{domain}",
        "first": f"{first}@{domain}",
    }
    
    if format_hint and format_hint in formats:
        return [formats[format_hint]]
    return [formats[k] for k in ["first.last", "first_last", "flast", "first", "f.last"]]
```

**German name handling:** Replace umlauts before generating emails:
- `Jörg Ißleib` → first=`joerg`, last=`issleib` → `joerg.issleib@domain.com`
- `Wolfgang Flügge` → `wolfgang.fluegge@domain.com`

### Step 4: Optional — Xing.com for German Companies

For German companies, Xing (xing.com) often has more employee profiles than LinkedIn.

```python
# Search Xing profiles
query = f'"{company_name}" einkauf site:xing.com/profile'
```

Xing profile URLs follow the pattern `xing.com/profile/First_Last` and often include job titles in search snippets.

### Step 5: Compile into Lead Schema

Add discovered decision-makers to the lead record:

```json
{
  "decision_makers": [
    {
      "name": "Rene Drechsler",
      "title": "Einkauf",
      "email": "rdrechsler@schukat.com",
      "linkedin": "https://de.linkedin.com/in/rene-drechsler-398687172",
      "email_confidence": "inferred",
      "source": "linkedin_search"
    }
  ],
  "emails": [
    {
      "email": "vertrieb@schukat.com",
      "type": "generic",
      "source_url": "tavily_search",
      "domain_relation": "same_domain",
      "verification": "format_only",
      "confidence": 0.85
    },
    {
      "email": "rdrechsler@schukat.com",
      "type": "inferred",
      "source_url": "linkedin_profile",
      "domain_relation": "same_domain",
      "verification": "format_only",
      "confidence": 0.6
    }
  ]
}
```

Mark inferred emails with `type: "inferred"` and lower confidence (0.5-0.7). Inferred emails are auxiliary — a lead cannot be `high` with ONLY inferred emails.

## Optional Scripts

Two helper scripts exist for convenience but are NOT required — Hermes can do all of this inline with `execute_code` + Tavily API calls:

- `scripts/linkedin_dm_search.py` — wraps the entire LinkedIn search + email inference pipeline. `python3 scripts/linkedin_dm_search.py --company "Schukat" --domain schukat.com --region DE`
- `scripts/infer_email.py` — detect format from known emails, or infer emails for names. `python3 scripts/infer_email.py detect jozef.jarabek@soselectronic.com` or `python3 scripts/infer_email.py infer --name "Georg Schukat" --domain schukat.com`

Use scripts when you want a one-shot result. Do it inline when you want to customize the search logic per company.

## Rate & Cost Limits

- Tavily free tier: 1000 searches/month
- Each company: ~5-10 Tavily calls (5-6 role keyword queries + 1 email format query)
- Target: 5-10 decision-makers per high-priority lead
- Skip decision-maker search for medium/low leads unless user explicitly requests

## Pitfalls

1. **Namesake noise.** "EVE GmbH" → LinkedIn returns "Eve Smith" (not an employee). Always verify the company name appears in the profile snippet, not just the person's name.
2. **Wrong format detection.** `info@company.com` looks like format "first" but isn't. Skip generic prefixes.
3. **Umlaut handling.** `Jörg` at `company.com` might be `joerg@` or `jorg@` or `j.issleib@`. Try both.
4. **Xing vs LinkedIn.** German SMEs often have zero LinkedIn presence. Try Xing.com first for DE companies.
5. **Tavily rate limiting.** Space calls 0.3s apart minimum. Don't batch 20 companies at once.
