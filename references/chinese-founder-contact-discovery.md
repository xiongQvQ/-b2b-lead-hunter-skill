# Chinese AI/Tech Founder & Decision-Maker Contact Discovery

Personal contact discovery for Chinese startup founders, executives, and key decision-makers. This supplements `decision-maker-discovery.md` which focuses on Western B2B procurement roles.

## Reality Baseline

Chinese founders rarely publish personal email, WeChat, or mobile numbers publicly. Set expectations accordingly:
- **Personal email**: ~10-15% find rate (academic founders, personal websites)
- **WeChat ID**: <1% find rate (essentially never publicly listed)
- **Personal mobile**: ~5% via 企查查 logged-in view; otherwise hidden
- **Company phone/HR email**: 60-70% find rate (already on most company websites)

## Source Priority (ranked by yield)

### Tier 1: Academic Footprints (highest yield for professor-founders)
Many Chinese AI/robotics founders hold university faculty positions.

**Method:**
```
tavily_search: "{name} {university} faculty email"
tavily_search: "{name} site:{university}.edu.cn email"
browser_navigate: "https://{lab_name}.github.io" or "https://{lab_name}.site"
```

**Real yield from 2026-05 session (30 Chinese AI/robotics founders):**
- 张巍 (LimX): zhangw3@sustech.edu.cn — from https://www.wzhanglab.site/members
- 高继扬 (Galaxea): jiyanggao1203@gmail.com — from https://jiyanggao.github.io
- 尚阳星 (BridgeDP): syx20171028@gmail.com — from https://lovethinkinghard.github.io

### Tier 2: Personal Website Mining
Founders with technical backgrounds often maintain .github.io pages.

**Method:**
```
tavily_search: '"{name}" site:github.io'
browser_navigate: "https://{possible_handle}.github.io"
```

Common naming patterns: `{pinyin}`, `{english-first}{english-last}`, `{word}{word}`.

### Tier 3: 企查查 / 天眼查 / 爱企查
Chinese business registries list legal representative phone numbers.

**Method:**
```
tavily_search: 'site:qcc.com OR site:aiqicha.baidu.com "{company_name}" 电话 手机'
tavily_search: 'site:tianyancha.com "{company_name}" 法定代表人 电话'
```

**Critical limitation**: Search engine results show redacted numbers (`1851311****`). Full numbers require logged-in access to the platform itself.

**Partial yield from 2026-05 session:**
- 陶芳波 (Mindverse): 18069771201 — full number visible on 企查查
- 董红光 (光帆科技): 1851311**** — redacted, last 4 hidden

### Tier 4: Company Career/Contact Pages
Direct browser navigation often reveals more than search engine caches.

**Target URLs (try in order):**
1. `{domain}/about` or `{domain}/about.html`
2. `{domain}/careers` or `{domain}/join`
3. `{domain}/contact` or `{domain}/contact-us`
4. `{domain}/team`

Use `browser_navigate` (not web_extract — many Chinese sites block Jina/extraction but allow browser rendering).

### Tier 5: Patent Inventor Records
Rarely yields personal contact but worth a quick check for hardware founders.

```
tavily_search: '"{name}" site:patents.google.com'
```

**2026-05 session result**: Zero personal contacts found from patents for 30 founders. Low priority.

## Anti-Patterns (DO NOT WASTE CALLS ON THESE)

1. **Generic "name + email/gmail/163/qq + 邮箱" queries** — return news articles, never personal contact
2. **site:zhihu.com** — Zhihu profiles almost never list personal email
3. **site:linkedin.com** — LinkedIn search results rarely contain email in snippets
4. **"name + 微信/wechat"** — essentially never yields results; WeChat is a walled garden
5. **web_extract on Chinese company sites** — many block extraction; use browser_navigate instead

## Search Query Templates

Good queries (use Tavily, not native web_search):
```
# Academic founders
"{name} {university} faculty email"
"site:{university}.edu.cn {name} email"

# Personal websites
"site:github.io {name} email"
"{name} personal page email gmail"

# Business registries
"site:qcc.com {company} {name} 电话"
"site:aiqicha.baidu.com {company} 手机"

# Company career pages (via browser, not search)
browser_navigate("{domain}/careers")
```

## Decision Tree

```
Founder has university position?
  → YES: Search faculty page → likely find .edu email
  → NO: Check for personal .github.io

Founder has technical background (ex-BAT, ex-FAANG)?
  → Search GitHub for personal page
  → Check LinkedIn (for profile, not email — then infer format)

No digital footprint at all?
  → 企查查 for business registration phone
  → 脉脉 (Maimai) for professional contact
  → Accept: personal contact unlikely via public web

Company has HR email on website?
  → USE IT. HR emails are often the fastest path.
  → Decision-makers read emails forwarded by HR.
```

## Deliverable Format

When compiling results, always distinguish:
- `personal_email` — confirmed personal mailbox (gmail, 163, qq, edu)
- `company_phone` — public company number (may or may not reach the person)
- `hr_email` — HR/recruitment mailbox
- `not_found` — transparently state nothing was found

Never fabricate or imply found contacts. An honest "not found" with recommended next step is more valuable than an inferred email with no evidence.
