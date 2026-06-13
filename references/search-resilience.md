# Search Infrastructure Resilience

## Problem

Automated search for B2B lead research is routinely blocked by CAPTCHA and bot detection. This is not a setup error — it's the default state of the modern web. Expect it and have fallback strategies ready before starting a run.

## Known Blockers (as of 2026-05)

| Engine / Platform | Blocker | Observed Behavior |
|---|---|---|
| **Google** | Google CAPTCHA | Redirects to `/sorry/index`, shows IP/time/URL block page |
| **DuckDuckGo** (HTML) | DDG Anomaly + CAPTCHA | Returns challenge page with "Select all squares containing a duck" |
| **DuckDuckGo** (API) | Rate limiting | Terminal gets `BLOCKED: User denied` after 1-2 calls |
| **Bing** | Likely CAPTCHA | Returns empty page, or redirects to `cn.bing.com` with no results |
| **Brave Search** | Brave CAPTCHA | "正在验证您不是机器人" with slider puzzle |
| **Yandex** | SmartCaptcha | "Please confirm that you are not a robot" with checkbox |
| **Kompass** | DataDome | Iframe "DataDome Device Check" — kills all content |
| **WLW** | Human Verification | "我们需要确认您是人类" with "开始" button |
| **Europages** | Unknown | Returns completely empty pages (no snapshot content) |
| **Distributor sites** | Cloudflare | "正在验证您不是机器人" / "Please wait..." (TME, Conrad) |
| **Distributor sites** | Cookie consent | Cookiebot/Usercentrics dialogs block content until dismissed |
| **Distributor sites** | Timeout / TCP reset | ERR_CONNECTION_CLOSED, operation timed out (various DE/AE sites) |

## Fallback Strategy (in priority order)

### 1. Wikipedia API (most reliable free option)

Wikipedia's API rarely blocks and returns JSON. Useful as a first-pass discovery tool:

```
https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json&srlimit=15&origin=*
```

Best queries: general industry terms ("electronics distributor Germany") rather than specific product searches. Wikipedia search quality is low for niche B2B — it returns encyclopedia articles, not company directories. Use it to discover well-known companies, then verify their distributor status by browsing their websites.

**Limitations**: Terminal-based `curl` calls may get blocked after 1-2 requests. Browser-based access (navigate to the API URL directly) works more reliably. Wikipedia results are encyclopedia articles, not B2B leads — you still need to verify each company.

### 2. Direct Website Reading + Domain Knowledge

When search is completely blocked, use industry knowledge to navigate directly to known distributor websites:

- **Germany**: endrich.com, buerklin.com, schukat.com, rutronik.com, codico.com, conrad.de, distrelec.de
- **Poland**: tme.eu, maritex.com.pl, micros.com.pl, soyter.pl, semicon.com.pl
- **UAE**: mitsumi.ae, eee.ae, jackys.com, alfuttaim.com, redingtongulf.com

How to execute:
1. Use `scripts/read_jina.py` on each site's homepage first.
2. Read likely product/about/contact pages with `scripts/read_jina.py`.
3. Use browser tools only when Jina returns empty content, a JS shell, 403/451, or you need interaction such as language switching or revealing hidden contact widgets.
4. For JS-rendered pages, use browser text extraction only after the Jina attempt is recorded as failed or unusable.
5. Look for: product categories containing the target product, "About" pages showing distributor/importer status, contact pages with emails/phones/people.
6. Record both successes and failures in `raw-search.jsonl` with `source: "jina"` or `source: "browser"` and appropriate `status`.

This approach yields fewer candidates but higher verification quality since you're reading official websites directly.

**Key insight for contact extraction**: When a contact page is JS-rendered and Jina is unusable, browser text extraction can recover footer/DOM contact details. Record that browser was a fallback, not the primary reader.

### 3. SearXNG Public Instances

Public SearXNG instances aggregate results from multiple engines and sometimes bypass CAPTCHAs. Try:

- `searx.tiekoetter.com`
- `search.sapti.me`
- `searx.be`

Format: `https://<instance>/search?q=<query>&format=json&language=en`

These are community-run and may be slow, rate-limited, or temporarily down. Do not hammer them.

### 4. Paid Search APIs (most reliable, costs money)

- **Google Custom Search JSON API**: $5 per 1000 queries, requires API key + CX
- **Serper.dev**: Google search API, free tier available
- **SerpAPI**: Google/Bing/Yandex/Yahoo, free tier 100 searches/month

These bypass CAPTCHAs entirely but require API key setup before the run.

## Pilot Decision Tree

When executing a pilot and search fails:

1. Try Wikipedia API via browser → if it works, extract company names
2. Supplement with direct Jina reads of 5-10 known distributors per region
3. If total verified candidates < 5, report honestly and recommend the user fix search infra
4. If total verified candidates > 5, evaluate quality and decide whether to continue
5. **Never** spend > 30 minutes fighting search blocks — document the failure and move to direct site reading

## Recording Failures

Always record failed search attempts in `raw-search.jsonl`:

```json
{"mode":"search","query":"micro switch distributor Germany","source_lane":"organic","source":"duckduckgo","status":"failed","error":"CAPTCHA block"}
{"mode":"direct_browse","query":"https://www.tme.eu/","source_lane":"organic","source":"browser","status":"blocked","error":"Cloudflare protection"}
```

This keeps the run report honest about coverage gaps and helps the user understand whether the search problem is systematic or one-off.
