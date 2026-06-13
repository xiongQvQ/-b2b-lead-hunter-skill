# Contact Discovery from PDF Brochures & Industry Directories

Supplemental technique for the LinkedIn/Tavily approach in `references/decision-maker-discovery.md`. Sometimes the best contact info is hiding in plain sight — in a company's own marketing materials.

## Technique 1: Official Company Brochures/PDFs

Many companies publish PDF brochures with executive contact info directly on their website.

### Steps
1. Check for PDFs on the company website: `site:company.com filetype:pdf`
2. Common PDF names: `brochure`, `catalog`, `company-profile`, `about-us`, `product-guide`
3. Download and extract text:
   ```bash
   curl -sL "https://company.com/brochure.pdf" -o /tmp/brochure.pdf
   pdftotext /tmp/brochure.pdf - | grep -iE 'email|phone|contact|vice|president|director'
   ```
4. If `pdftotext` is unavailable, search the PDF URL via web search instead — Google/other engines often index the text content

### Example (from this session)
A. Lyons & Co., Inc. published a brochure at `https://alyons.com/wp-content/uploads/2019/08/A.Lyons-2019-Brochure.pdf`
It contained:
```
Contact: Rick Fine. Vice President Industrial Products. Rick.Fine@alyons.com. Cell: 334-722-0098.
```
This was not discoverable via LinkedIn or general web search — the PDF was the only source.

## Technique 2: Industry Trade Directories

Trade magazines and industry associations often maintain buyer's guides with verified executive contacts.

### Where to look
| Directory | Vertical | Example |
|-----------|----------|---------|
| ASSEMBLY Magazine Buyers Guide | Manufacturing/Assembly | `assemblymag.com/directories/...` |
| ThomasNet | Industrial suppliers | `thomasnet.com` |
| Fastener News Desk | Fastener industry | `fastenernewsdesk.com` |
| Kompass | Global B2B | `kompass.com` |
| Europages | European B2B | `europages.com` |

### Search pattern
```bash
site:assemblymag.com "company name" OR "product category" "vice president" OR "contact"
```

### Example (from this session)
Searching `site:assemblymag.com "A. Lyons"` returned a listing with:
- Rick Fine, V.P.-Industrial Products
- Direct phone: (334) 722-0098
- Email: rick.fine@alyons.com

## Technique 3: Company Website Contact Pages (unexpected locations)

Sometimes contact info is on pages you wouldn't expect:
- `/imprint` or `/impressum` (German companies — legally required contact info)
- `/privacy-policy` or `/datenschutz` (often lists company representative)
- Career/job pages (`/career`, `/jobs`, `/karriere`) — often have HR contact but also management names
- `/about-us` or `/company` PDF downloads
- `/suppliers` page (some companies have a dedicated suppliers/vendors page with procurement contact)

### German companies specifically
German law requires an `Impressum` page with:
- Full company legal name
- Managing directors (Geschäftsführer) by name
- Commercial register number
- VAT ID
- Phone/fax/email

This is often the single best source for German B2B leads.

## When to Use PDF/Directory Approach

Use this **before** LinkedIn/Tavily searches when:
- The company is small/medium (2-50 employees) — less likely to have LinkedIn presence
- The company is old-fashioned (founded before 2000, brochure-style website)
- LinkedIn search returned no relevant results
- You need a **confirmed** email (not inferred) for initial outreach
