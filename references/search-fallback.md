# Search Fallback Strategy

When Hermes native web search is unavailable or returns no results, use these fallbacks in order.

## Fallback 1: Mojeek via curl

Mojeek (mojeek.com) is a UK-based independent search engine that is less likely to block automated requests than Google/Bing/DDG. It returns usable HTML that can be parsed with regex.

```bash
# Search and parse results
curl -sL --max-time 20 \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  "https://www.mojeek.com/search?q=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("QUERY"))')"
```

Parse pattern for result titles and links:
```
<a class="title" href="URL">Title</a>
```

Mojeek supports site-specific search: `site:domain.com keyword`.

## Fallback 2: Browser with DuckDuckGo Lite

If Mojeek is blocked, use `browser_navigate` to `https://lite.duckduckgo.com/lite/?q=QUERY`. The lite version has no JS and rarely triggers CAPTCHAs. Extract results from `browser_snapshot`.

## Fallback 3: Direct B2B platform search

Skip general search engines entirely and go directly to:
- europages.com (may be WAF-protected — falls to 202 challenge)
- kompass.com
- industrystock.com

## Known Broken / Avoid

| Engine | Failure Mode |
|--------|-------------|
| Google (browser) | Redirects to CAPTCHA/sorry page |
| Google (curl) | Blocks immediately |
| DuckDuckGo (html.duckduckgo.com) | Returns JS CAPTCHA challenge |
| DuckDuckGo (browser) | Shows promo interstitial, no search results |
| Bing (browser) | Redirects to cn.bing.com, Chinese results only |
| Bing (curl, en-US) | May work with right headers but unreliable |
| Europages, WLW | AWS WAF challenge (HTTP 202, x-amzn-waf-action: challenge) |
| Startpage (curl) | Returns empty results for many queries |

## Shell Quoting Gotcha

URLs with `&`, `?`, `=` characters will be interpreted by bash. Always wrap URLs in single quotes when passing to terminal. For Python execute_code blocks, use `urllib.parse.quote()`.

Wrong: `curl "https://example.com?a=1&b=2"` — bash interprets `&b=2` as background job
Right: `curl 'https://example.com?a=1&b=2'`
