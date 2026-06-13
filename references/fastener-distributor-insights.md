# Fastener Distributor Lead Hunt — Domain Insights

Captured from a real lead hunt for Hebei Qianke E-Commerce (Alibaba seller: bolts, self-drilling screws, hollow wall anchors, chemical anchors, nuts) targeting Germany, France, and USA.

## Jina Reader + Alibaba

Alibaba main shop pages (`index.html`) read fine via `read_jina.py`. **Subpages return 451 (Unavailable For Legal Reasons):**
- `/company_profile.html`
- `/contactinfo.html`
- `/productlist.html`

**Workaround:** The main page already contains product categories and company name — that's sufficient to build a brief. Don't retry subpages.

## Large-Scale Contact Extraction (20+ Companies)

The skill's standard workflow (read each website via `read_jina.py`, extract contacts) **times out** when the target list is 15+ companies. The `execute_code` script running sequential Jina reads across 21 companies was killed at 300s.

**Fast alternative discovered:** Instead of reading each company's website, use **targeted web_search queries** per company:
```
# For each company, search:
"Company Name" email contact [city]
"Company Name" purchasing manager procurement
```

This is:
- Faster (single search instead of full page load)
- More productive (search snippets often include phone/email directly)
- More structured (Google/Bing surface contact pages with snippets)

**Sequence for large hunts:**
1. First pass: web_search for each company → collect all found contacts → fill spreadsheet
2. Second pass: read_jina only on companies where search found nothing or info is ambiguous
3. Third pass (high-priority only): read_jina contact page + LinkedIn search

## German Market — "Ansprechpartner" Shortcut

Many German fastener distributors **explicitly list employees with direct emails** on dedicated "Ansprechpartner" (contact persons) pages. This bypasses the generic email entirely.

**Common URL patterns:**
- `/ansprechpartner/`
- `/ansprechpartner`
- `/kontakt/` (often includes employee list in the body)
- `/unternehmen/team/`

**What to search:**
```
"Company Name" Ansprechpartner site:company.de
"Company Name" Einkauf site:company.de
"Company Name" Geschäftsführer site:company.de
```

**Example finds from this session:**
- Halfmann Schrauben: `/ansprechpartner/` had Edis Civic (GM), Anid Sahman (Purchasing), Dean Günther (Purchasing) — all with @halfmann-schrauben.de emails
- Fuchs+Sanders: Tobias Langemeyer as "Leiter Einkauf" (Head of Purchasing) found via XING

**Decision-maker role keywords:**

| Role | German | Region |
|------|--------|--------|
| Purchasing | Einkauf / Einkäufer | DE |
| Head of Purchasing | Leiter Einkauf / Einkaufsleiter | DE |
| CEO/Managing Director | Geschäftsführer | DE |
| Sales/Export | Vertrieb / Export | DE |
| Procurement | Beschaffung / Supply Chain | DE |

## French Market — Europages + SIRET

Europages (`europages.fr`) is the most reliable source for French fastener distributors. It surfaces company name, city, employee count, and a "Contacter le fournisseur" button.

**Search pattern:**
```
site:europages.fr "boulonnerie" "visserie" distri|grossiste
site:europages.fr "boulonnerie" "France" distributeur
```

**Key French fastener terms:**
- Boulonnerie = bolts/bolting
- Visserie = screws/screw shop
- Grossiste = wholesaler
- Distributeur = distributor
- Quincaillerie = hardware store

French SMEs often have minimal website contact info — the contact form or Europages contact is the primary channel.

## US Market — Thomasnet + ZoomInfo hints

**Thomasnet** (`thomasnet.com`) is the strongest single source for US fastener distributors. Key companies found via:
- `site:thomasnet.com "fastener" "distributor" "imported"`
- `site:thomasnet.com "bolt" "screw" "wholesale"`

**ZoomInfo/LeadIQ** snippets in web search results often reveal decision-maker names and titles without a paid subscription (search snippets from `leadiq.com`, `zoominfo.com`, `dnb.com`).

**Top-returning companies for US fastener importers:**
| Company | Location | Key Fact |
|---------|----------|----------|
| A. Lyons & Co. | Manchester, MA | Since 1933, imports from Asia/Europe |
| CDE Fasteners | Brick, NJ | Since 1995, 40K+ SKU |
| Fastener Solutions | Nationwide | 100M+ fasteners |
| American Bolt | New Berlin, WI | Since 1962 |
| K-J Fasteners | Eastlake, OH | Since 1975, ISO 9001 |
| QFC Industries | Arlington, TX | Since 1973 |

## Email Format Detection

For US companies where you know employee names (e.g. from ZoomInfo snippet) but not emails:

| Company | Inferred Format | Reasoning |
|---------|----------------|-----------|
| CDE Fasteners | `first.last@cdefasteners.com` | LeadIQ reports this pattern |
| A. Lyons | `info@alyons.com` (generic only) | No employee emails publicly found |
| Fastener Solutions | `info@fastenersolutions.com` (generic) | No employee emails publicly found |

For German companies, the "Ansprechpartner" pages give direct emails, so inference is unnecessary.

## Rate & Volume Management

- 20+ company target across 3 countries: allocate ~2 hours agent time minimum
- Jina reads: budget ~15s per URL, 4 URLs per company = ~20 min for 20 companies (too slow)
- web_search: budget ~1 query per company + 1 read for high priority = ~30 min for 20 companies
- Decision-maker search: ~5 queries per high-priority company = ~2.5 min each
