# Chinese AI/Robotics Startup Lead Mining

For recruitment/headhunting use cases targeting 2026-funded Chinese AI, robotics, embodied intelligence (具身智能), and hardware startups. Distinct from foreign-trade B2B — sources, search lanes, and contact discovery methods differ completely.

## Key Search Sources (Chinese Tech Media)

| Source | URL | Best For |
|--------|-----|----------|
| 36kr | 36kr.com | All AI/tech funding news, founder interviews |
| 投资界 Pedaily | pedaily.cn | VC-backed funding announcements with investor details |
| 钛媒体 TMTPost | tmtpost.com | Deep tech funding stories, CEO interviews |
| 瑞财经 Rccaijing | rccaijing.com | Quick funding news with company registration details |
| 机器人世界 Robotsj | robotsj.cn | Monthly robotics funding roundups (2026年X月融资汇总) |
| 知乎专栏 | zhuanlan.zhihu.com | Monthly funding summaries by sector |
| 亿欧 iyiou | iyiou.com | AI/robotics industry analysis and funding |
| 量子位 QbitAI | qbitai.com | AI-specific funding news, technical deep-dives |

## Search Lanes for 2026 AI/Robotics Startups

Multi-lane approach to maximize coverage:

```
Lane 1: 2026年 具身智能 融资 天使轮 A轮 亿元 site:36kr.com
Lane 2: 2026年 AI机器人 完成 融资 创始人 CEO site:pedaily.cn
Lane 3: 2026年X月 国内具身智能机器人企业融资情况汇总 site:robotsj.cn
Lane 4: 2026年 AI硬件 机器人 融资 华人 初创 天使轮
Lane 5: 2026年 消费机器人 清洁机器人 庭院机器人 融资 亿元
Lane 6: 2026年 AI芯片 大模型 融资 天使轮 A轮 初创
Lane 7: 2026年 手术机器人 医疗机器人 AI 融资 亿元
Lane 8: 2026年 低空经济 无人机 AI 融资
```

Always run at least 4 lanes. The robotsj.cn monthly roundups (e.g. `robotsj.cn/shichangdongtai/1741.html`) are especially high-yield — they list 15-30 companies per month with funding amounts and investor names.

## Decision Maker Discovery (Chinese Startup Context)

### Tier A: Academic/Professor Founders (MOST PRODUCTIVE)
Chinese AI/robotics professors at SUSTech, Tsinghua, PKU, SJTU, ZJU, CUHK, HKU typically have faculty pages with public emails.
- Search: `"{name}" email site:sustech.edu.cn OR site:tsinghua.edu.cn`
- Pattern: `zhangw3@sustech.edu.cn`, `{first}{last}@tsinghua.edu.cn`
- Also check their lab pages: `{name} lab site:edu.cn`

### Tier B: Personal Websites / GitHub Pages
Younger founders (especially 00后, 95后) often have .github.io pages with personal Gmail.
- Search: `"{name}" github.io`
- Found examples: jiyanggao1203@gmail.com, syx20171028@gmail.com

### Tier C: Company Career/Recruitment Pages
- 飞书招聘 (Feishu Jobs): `{company}.jobs.feishu.cn` — ByteDance-style career pages used by many startups
- BOSS直聘: search company name on zhipin.com
- Company career pages: `{domain}/careers`, `{domain}/jobs`, `{domain}/join`

### Tier D: 企查查 / 天眼查 (Business Registration)
- Free tier shows partially-redacted phone numbers (e.g. 1851311****)
- Paid tier reveals full numbers
- Search: `site:qcc.com OR site:aiqicha.baidu.com {company} 电话 手机`
- Useful for legal representative (法定代表人) phone numbers — these are business registration phones, may or may not reach the founder directly

### Tier E: Media-only (No Public Contact Found)
Many founders (especially 华为/大厂/自动驾驶背景) have zero public contact info. They appear only in media interviews.
- Recommended path: 脉脉 (maimai.cn), LinkedIn, 猎头 networks
- Mark these as `media_only` and note the secondary path

## Contact Quality Tiers

| Tier | Description | Action |
|------|-------------|--------|
| `email_confirmed` | Personal or corporate email verified on official site | Ready for outreach |
| `hr_email_found` | HR/recruitment email found (hr@, zhaopin@, jobs@) | Send to HR, ask for decision-maker intro |
| `career_page_only` | 飞书招聘/BOSS直聘 page found, no direct email | Apply portal path |
| `media_only` | Only media mentions, no direct contact | 脉脉/LinkedIn/企查查 secondary breakthrough needed |
| `no_contact` | Nothing found at all | Deep digging needed — try 脉脉 + LinkedIn + industry networks |

## Typical Contact Distribution (from 30-company batch)

- `email_confirmed` (academic or personal website): ~10%
- `hr_email_found` (company career page): ~25%
- `career_page_only` (飞书/BOSS直聘): ~20%
- `media_only` (need 脉脉/LinkedIn): ~35%
- `no_contact` (nothing found): ~10%

Expect ~35% of Chinese AI startup founders to have NO publicly discoverable contact info. This is normal.

## Pitfalls

1. **企查查 phone redaction**: Free search shows `1851311****`. Need paid account or direct website visit for full numbers.
2. **36kr paywall**: Some articles behind login. Use Tavily search snippets or google cache.
3. **robotsj.cn blocks web_extract**: Can't scrape monthly roundups directly. Use Tavily to search the content instead.
4. **Company website blocks**: Many Chinese startup sites block automated extraction. Use browser navigate for crucial pages.
5. **Founder name ambiguity**: Common Chinese names have many hits. Always verify company name appears in profile snippet alongside the name.
6. **Duplicate detection**: Many startups appear in both existing CSVs and new searches. Maintain a skip list of ~30 company names.
7. **Sector overlap**: Companies like 追觅 span consumer electronics + robotics + AI. Classify by primary funding narrative.

## Outreach Style Preferences (Recruitment/Headhunting Use Case)

When writing outreach emails to Chinese AI/robotics startup founders:

- **No phone-call CTA unless user explicitly asks**: Default to lightweight CTA ("希望能了解您的用人方向", "希望能有机会"). User explicitly rejected "15分钟电话" as too aggressive.
- **Open with a founder-specific hook**: Personal website quotes, career transitions, funding milestones — show you did your homework. "从你个人主页那句..." beats "贵公司成绩斐然".
- **Show you understand their hiring pain**: Name the specific roles that are hard to hire for (具身基础模型, 运动控制, 海外BD). Generic "we help you hire" is weak.
- **Close with company-specific mission**: "祝星海图早日实现 Physical AGI" > "祝工作顺利". Shows you read their vision.
- **Subject line pattern**: `{company}的{key moment} — {service intro}`. Example: "星海图百亿估值后的关键人才战 — 猎头服务介绍".
