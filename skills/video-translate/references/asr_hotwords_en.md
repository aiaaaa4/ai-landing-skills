# ASR Hotwords - English Trading Videos

Purpose: maintain English ASR hotwords for Alibaba Fun-ASR. These entries are for recognition accuracy only. Chinese translations belong in `trading_glossary.md` and `term_repair_rules.json`.

Remote vocabulary:

- Workspace ID: `llm-1hm3fq7ypcv3c74q`
- Vocabulary ID: `vocab-trade-840d5a601f0c46da87088d19ca9122a8`
- Auth: local `DASHSCOPE_API_KEY` from `.env`

Maintenance rules:

- Keep ASR hotwords concise. Prefer proper names, tickers, platform names, acronyms, and multi-word terms that ASR often splits or mishears.
- Do not put Chinese translations here.
- Do not add ordinary English words unless repeated ASR errors prove they are necessary.
- For pure English/ASCII entries, keep each item at 7 space-separated fragments or fewer.
- Deduplicate case-insensitively before updating the remote vocabulary.

## Maintenance SOP

Use this file as the local source of truth for ASR hotwords. The remote Alibaba vocabulary should mirror this list after approved maintenance.

### Decide ASR Hotword vs Translation/QC Rule

Add a term to the ASR hotword list when the problem happens before translation:

- `SRC_RAW` contains the wrong word, a split word, or a misheard proper noun.
- Fun-ASR repeatedly splits a multi-word product, platform, indicator, ticker, person, or brand name.
- The term is a high-value acronym/ticker/indicator that should be recognized exactly even if it appears only once.

Examples:

- `r hyth mic` should become `Rithmic`.
- `trade ev ade` should become `Trade Evade`.
- `from Tony` in a date/number context may need review because the intended phrase can be `from twenty`.
- `GEX`, `NQ`, `First Red Day`, `Net Convexity`, and product/person names belong here when they affect ASR recognition.

Do not add a term to ASR hotwords when the audio was recognized correctly and only the Chinese wording is wrong. Put those fixes in `trading_glossary.md` or `term_repair_rules.json`.

Examples:

- `scalper` recognized correctly but translated as `黄牛`: translation/QC rule.
- `first red day` recognized correctly but translated as `第一个红日`: translation/QC rule.
- `gamma/delta/vega/theta` recognized correctly but rendered as Chinese: translation/QC rule.
- Awkward Chinese style, overly long subtitles, punctuation, or line breaks: QA/export rule, not ASR hotword.

### Promotion Threshold

Promote a candidate into ASR hotwords when one of these is true:

- The same ASR mistake appears in two or more videos.
- The term is a known recurring domain term, ticker, product name, platform name, indicator, or speaker/person name for the current video set.
- The term is rare but high-impact: one ASR error would likely break alignment, confuse translation, or damage domain credibility.

Do not promote one-off common English words unless a repeated ASR failure proves they are needed.

### Review Cadence

- After every 3-5 same-domain videos, review `final_qa_report.md`, `segments.txt`, and obvious ASR mistakes in `SRC_RAW`/`SRC_DISPLAY`.
- For a single large batch, review once after the batch finishes.
- Update the remote ASR vocabulary only after collecting a small stable batch of candidates, unless a high-impact proper noun or ticker must be fixed immediately.

### Update Procedure

1. Add approved terms to this file.
2. Query the remote vocabulary.
3. Merge old terms and new terms.
4. Deduplicate case-insensitively.
5. Preserve existing terms.
6. Submit the full merged vocabulary to Alibaba, because update is treated as a full vocabulary update rather than a simple append.
7. Re-query and verify key terms exist.
8. Keep `.env` pointing to the active `ALIYUN_ASR_VOCABULARY_ID`.

Never expose `DASHSCOPE_API_KEY` or package `.env`.

## Current Hotword Set

### Tickers And Markets

- NQ
- ES
- SPX
- SPY
- QQQ
- AAPL
- TSLA
- NFLX
- Nasdaq
- S&P 500

### Options, Gamma, And Volatility

- Gamma
- Delta
- Vega
- Theta
- Vanna
- Charm
- Volatility
- Implied Volatility
- Open Interest
- Put Call Ratio
- Put Call Interest
- Put Call Volume
- Gamma Exposure
- GEX
- GEXBot
- Gexbot
- Net Gamma
- Net Convexity
- Convexity

### Trading Concepts

- Price Action
- Volume Profile
- Fixed Profile
- Value Area
- Value Area High
- Value Area Low
- Point of Control
- POC
- VWAP
- Cumulative Volume Delta
- CVD
- Fair Value Gap
- FVG
- Order Flow
- Footprint Chart
- Absorption
- Imbalance
- Liquidity
- Breakout
- Pullback
- Reversion
- Mean Reversion
- Momentum
- Support
- Resistance
- Consolidation
- Regime
- Regime Bot
- Regime Bots
- First Red Day
- EOD
- TA

### Brands, Platforms, Communities, And Names

- Apex Trader Funding
- TradePro Academy
- TradingView
- Chart Fanatics
- Discord
- YouTube
- Papazov
- Ivan Labrie
- Freddie
- Fredy
- Jass
- Tradovate
- Rithmic
- NinjaTrader
- Wealth Charts
- Bookmap
- Interactive Brokers
