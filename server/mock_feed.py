"""
Mock news feed and agent for testing when DBNews / Modal are unavailable.

Generates realistic financial/geopolitical headlines and fires them
through the same on_news callback as the real feed. The mock evaluator
returns random decisions with simulated latency.

Usage:
    python main.py --mock
"""
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone

from news_streamer.models.news import RawNewsItem, SourceType
from agents.schemas import Decision, MarketConfig, StoryPayload

HEADLINES: list[tuple[str, str, tuple[str, ...]]] = [
    # (headline, body, pre_tagged_categories)
    # ── Politics ──────────────────────────────────────────────────
    ("US deploys additional carrier strike group to Persian Gulf amid rising tensions with Iran",
     "The USS Eisenhower and its escort group departed Norfolk early Saturday en route to the Strait of Hormuz. Pentagon officials say the deployment is 'precautionary' but comes after Iran's IRGC warned of retaliation for Israeli airstrikes. Regional allies have been placed on heightened alert.", ("politics",)),
    ("Pentagon confirms US military assets targeted in Strait of Hormuz attack",
     "Two ballistic missiles struck near Al Udeid Air Base in Qatar early this morning, causing no casualties but damaging support infrastructure. CENTCOM is evaluating the origin of the strike. Oil futures jumped 4% in after-hours trading on the news.", ("politics",)),
    ("Iran's IRGC claims responsibility for missile strikes on US base in Iraq",
     "In a televised statement, IRGC commander Hossein Salami said the strikes were 'the first wave of retaliation' for the assassination of senior military officials. The Pentagon confirmed minor damage at Ain al-Asad airbase.", ("politics",)),
    ("UN Security Council calls emergency session on Iran-US escalation",
     "France and the UK requested the emergency session, scheduled for 3 PM ET. Russia and China have signaled opposition to any resolution condemning Iran, setting up a likely veto showdown.", ("politics",)),
    ("Israel conducts airstrikes on Iranian nuclear facilities — IDF confirms",
     "The Israeli Air Force struck targets at Natanz and Isfahan overnight using F-35I stealth fighters. IDF spokesman Daniel Hagari confirmed the operation hit centrifuge halls and missile storage facilities. Iran's atomic energy agency says damage assessment is underway.", ("politics",)),
    ("NATO allies invoke Article 4 consultations over Middle East crisis",
     "Turkey and several NATO members triggered consultations after Iranian missiles passed through Turkish airspace. The alliance's North Atlantic Council will convene Monday to discuss collective defense posture.", ("politics",)),
    ("Trump signs executive order imposing maximum sanctions on Iranian oil exports",
     "The order targets all remaining Iranian crude buyers, including waivers previously granted to China, India, and Turkey. Analysts estimate this could remove 1.5M barrels/day from global supply.", ("politics",)),
    ("Senate passes bipartisan resolution authorizing use of force against Iran",
     "The vote was 78-22, with 15 Democrats joining all Republicans. The resolution authorizes 'all necessary force to protect US personnel and assets in the Middle East.' House vote expected Monday.", ("politics",)),
    ("Trump to address nation on Middle East crisis at 9 AM ET Saturday",
     "White House officials say the address will outline the US response to overnight Iranian missile strikes. Markets are bracing for volatility with futures already down 2.1%.", ("politics",)),
    ("House passes emergency $12B defense supplemental for Middle East operations",
     "The spending package includes $7B for naval operations, $3B for missile defense, and $2B for intelligence operations. It passed 312-118 with broad bipartisan support.", ("politics",)),
    ("EU foreign ministers hold emergency summit on Iran sanctions",
     "EU High Representative Kaja Kallas convened the summit in Brussels. The bloc is expected to align with US sanctions but faces pushback from member states dependent on Iranian energy imports.", ("politics",)),
    ("Trump threatens 'obliteration' if Iran retaliates further",
     "In a Truth Social post at 6:12 AM ET, the President wrote: 'Any further attack on American forces will be met with obliteration the likes of which Iran has never seen.' Markets reacted sharply, with Dow futures down 450 points.", ("politics",)),
    ("Congressional leaders briefed on classified intelligence regarding Iran",
     "The Gang of Eight received a 90-minute briefing at the Capitol from CIA Director and Secretary of Defense. Multiple sources say the intelligence involves imminent Iranian plans for a second wave of attacks.", ("politics",)),
    ("SEC files lawsuit against Uniswap Labs for operating unregistered exchange",
     "The complaint alleges Uniswap facilitated $1.4T in unregistered securities transactions. UNI token dropped 18% on the news. Uniswap Labs CEO said the suit is 'a fundamental misunderstanding of decentralized technology.'", ("politics",)),
    ("US Treasury proposes new KYC rules for DeFi protocols",
     "The proposed rule would require DeFi front-ends to collect user identity data for transactions over $3,000. Industry groups have 60 days to comment. Crypto lobby estimates compliance costs at $2B annually.", ("politics",)),
    # ── Economics ─────────────────────────────────────────────────
    ("Federal Reserve signals potential emergency rate cut amid market turmoil",
     "In a rare inter-meeting statement, the Fed acknowledged 'significant tightening of financial conditions' and said it stands ready to act. Traders now price a 50bp emergency cut at 82% probability for next week.", ("economics",)),
    ("US CPI comes in at 4.1% YoY, above consensus 3.8% — BLS",
     "Core CPI rose 0.5% MoM, driven by energy and shelter. The hotter-than-expected print complicates the Fed's easing path. 2-year Treasury yields jumped 12bp on the release.", ("economics",)),
    ("US jobless claims surge to 285K, highest since March 2024",
     "Continuing claims also rose to 1.92M, suggesting labor market softening. The 4-week moving average is now at 262K, up from 235K a month ago. Defense and energy sectors bucked the trend.", ("economics",)),
    ("Fed Chair Powell: 'We are monitoring geopolitical risks to price stability'",
     "Speaking at a hastily arranged press conference, Powell said the Fed has tools to ensure financial market functioning but stopped short of committing to rate changes. 'We will not be behind the curve,' he stated.", ("economics",)),
    ("US GDP growth revised down to 1.1% for Q4 2025",
     "The second revision showed weaker consumer spending and business investment than initially reported. Personal consumption was revised from 2.3% to 1.8%. Trade deficit also widened more than expected.", ("economics",)),
    ("ECB holds rates steady at 3.75%, cites Middle East uncertainty",
     "President Lagarde said the Governing Council is 'closely monitoring' energy price developments. The ECB revised its 2026 inflation forecast up to 2.8% from 2.3%, primarily on oil price assumptions.", ("economics",)),
    ("US consumer confidence drops to 82.3, lowest reading in 14 months",
     "The Conference Board index fell sharply from 94.1 in the prior month. The expectations component cratered to 67.2, historically a recession warning level. Gas prices averaging $4.85/gallon cited as key drag.", ("economics",)),
    ("IMF warns global growth could slow to 2.1% if oil disruption persists",
     "The IMF's emergency assessment models show prolonged Strait of Hormuz disruption could cut global GDP by 1.2 percentage points. Emerging markets face the highest risk from energy inflation.", ("economics",)),
    ("US manufacturing PMI contracts to 46.2, weakest since 2020",
     "New orders fell to 42.8 while input prices surged to 65.1, the highest since the 2022 inflation peak. Only 2 of 18 industries reported growth. Employment sub-index also contracted.", ("economics",)),
    ("Fed funds futures now pricing 75% chance of emergency cut",
     "CME FedWatch shows markets expect 50bp of easing before the March meeting. The 10Y-2Y spread has inverted further to -45bp. Goldman Sachs has moved up its recession probability to 45%.", ("economics",)),
    # ── Financials ────────────────────────────────────────────────
    ("S&P 500 drops 3.2% in worst single-day decline since March 2023",
     "All 11 sectors closed lower, led by technology (-4.8%) and consumer discretionary (-4.1%). Only 23 S&P 500 stocks finished in the green. Trading volume was 2.3x the 20-day average.", ("financials",)),
    ("10-year Treasury yield spikes to 5.2% on inflation fears",
     "The benchmark yield rose 18bp in a single session as traders repriced inflation expectations. The 30-year hit 5.5%. Mortgage rates are now expected to breach 8% for the first time since 2023.", ("financials",)),
    ("VIX spikes to 38 as equities sell off on geopolitical risk",
     "The CBOE volatility index saw its largest single-day jump since the 2020 pandemic crash. VIX call volume hit a record 1.2M contracts. Dealers are significantly short gamma at current levels.", ("financials",)),
    ("Dollar index surges to 108.5 on safe-haven flows",
     "DXY posted its biggest weekly gain since 2022, crushing emerging market currencies. The Turkish lira fell 8%, South African rand 5.2%. Japanese yen was the only major currency to strengthen against the dollar.", ("financials",)),
    ("Brent crude surges past $125/barrel on Strait of Hormuz fears",
     "Oil prices spiked 12% as Iranian naval forces conducted live-fire exercises near the strait, through which 20% of global oil supply passes. WTI hit $118. Energy stocks surged with XLE up 6.8%.", ("financials",)),
    ("Gold hits all-time high of $2,850/oz as investors flee to safety",
     "The precious metal broke through the previous record set in October 2024. Central bank buying and safe-haven demand have driven a 22% YTD gain. Silver also surged to $38.50.", ("financials",)),
    ("EUR/USD drops to 1.02 as dollar strengthens on safe-haven demand",
     "The euro fell 2.3% in its worst week since the 2022 energy crisis. European equities underperformed US peers as the continent faces higher energy cost exposure.", ("financials",)),
    ("Bank of Japan intervenes to support yen as USD/JPY hits 162",
     "Japan's Ministry of Finance confirmed intervention of approximately ¥5.2T ($32B). This marks the third intervention this year. The yen recovered to 158 but remains near multi-decade lows.", ("financials",)),
    ("JPMorgan reports record trading revenue on volatility surge",
     "Fixed income trading revenue hit $7.2B, up 43% YoY, driven by rates and commodities desks. CEO Jamie Dimon warned that 'the geopolitical situation could deteriorate further.' Shares rose 3.8%.", ("financials",)),
    ("ExxonMobil posts $14B quarterly profit as crude prices spike",
     "Revenue jumped 28% to $98B. Upstream earnings doubled on higher realized prices. The company raised its quarterly dividend 5% and announced a $10B accelerated buyback program.", ("financials",)),
    # ── Companies ─────────────────────────────────────────────────
    ("Apple reports Q1 earnings miss — revenue down 4% on supply chain disruption",
     "iPhone revenue fell 8% as Foxconn facilities in India faced logistics delays related to the Middle East shipping crisis. Services revenue was a bright spot at $24.2B, up 14% YoY. Shares fell 5.2% after hours.", ("companies",)),
    ("NVIDIA beats estimates with $38B revenue, guides higher on AI demand",
     "Data center revenue hit $30.8B, up 112% YoY. CEO Jensen Huang said demand for Blackwell GPUs 'far exceeds supply through 2026.' Gross margins expanded to 76.2%. Stock up 8% in extended trading.", ("companies",)),
    ("Tesla delivers 520K vehicles in Q1, beating estimates by 12%",
     "Model Y accounted for 68% of deliveries. Shanghai factory hit record output of 22K units/week. Cybertruck deliveries reached 45K. Average selling price held steady at $44,200.", ("companies",)),
    ("Amazon Web Services revenue up 22% YoY, margins expand to 31%",
     "AWS generated $27.4B in revenue, with operating income of $8.5B. AI workloads drove the acceleration, with Bedrock API calls up 5x QoQ. Amazon also announced a $10B data center expansion in Virginia.", ("companies",)),
    ("Lockheed Martin surges 14% on $8B Pentagon contract for Middle East ops",
     "The contract covers Patriot PAC-3 missile production and maintenance for 36 months. Backlog now exceeds $160B. The stock hit an all-time high of $625.", ("companies",)),
    ("Saudi Aramco pauses IPO plans citing market instability",
     "The planned $12B secondary offering on the London Stock Exchange has been shelved indefinitely. CEO Amin Nasser said the decision was driven by 'unprecedented regional uncertainty.' Aramco stock fell 3% in Riyadh.", ("companies",)),
    ("MicroStrategy announces additional $1.5B Bitcoin purchase",
     "The company now holds 478,000 BTC acquired at an average price of $62,300. Executive Chairman Michael Saylor called BTC 'the ultimate safe haven in a world of sovereign risk.' MSTR shares rose 9%.", ("companies", "crypto")),
    ("Coinbase reports 3x surge in institutional trading volume",
     "Institutional spot trading volume hit $145B in February, driven by hedge funds seeking crypto exposure during geopolitical turmoil. Custody assets under management reached $320B.", ("companies", "crypto")),
    # ── Crypto ────────────────────────────────────────────────────
    ("Bitcoin surges past $135K as institutional buyers seek hedge against geopolitical risk",
     "BTC posted a 12% daily gain, its largest since November 2024. On-chain data shows $4.2B in exchange outflows, suggesting accumulation. Open interest on CME Bitcoin futures hit a record $28B.", ("crypto",)),
    ("Ethereum breaks $8,200 on record DeFi inflows during market turmoil",
     "Total Value Locked in DeFi protocols surged $18B in 24 hours as traders moved assets on-chain. ETH gas fees spiked to 120 gwei. Staking yield rose to 5.8% annualized.", ("crypto",)),
    ("Solana TVL hits $28B as traders migrate from centralized exchanges",
     "Solana DeFi protocols saw $3.2B in inflows over the weekend. Jupiter exchange processed $8.4B in daily volume. SOL price reached $420, up 15% in 48 hours.", ("crypto",)),
    ("Tether treasury mints $2B USDT in 24 hours amid flight from fiat",
     "Total USDT supply now exceeds $142B. Tether CTO Paolo Ardoino confirmed the mints were in response to 'extraordinary institutional demand.' USDT remained stable at $1.001.", ("crypto",)),
    ("SEC approves spot Ethereum ETF — trading begins Monday",
     "The SEC approved applications from BlackRock, Fidelity, and Ark/21Shares. Analysts expect $15B in inflows within the first month. ETH rallied 8% on the announcement.", ("crypto", "politics")),
    ("Bitcoin hash rate hits all-time high as miners price in $150K target",
     "Network hash rate reached 850 EH/s, up 35% YTD. Marathon Digital and Riot Platforms both reported record monthly production. Mining difficulty adjustment expected to increase 8%.", ("crypto",)),
    ("BlackRock Bitcoin ETF sees $2.1B single-day inflow — largest ever",
     "IBIT now holds 620,000 BTC worth $83B, making it the largest Bitcoin fund globally. BlackRock CEO Larry Fink said digital assets are 'becoming a permanent part of institutional portfolios.'", ("crypto",)),
    ("Circle pauses USDC redemptions for 4 hours citing banking partner issues",
     "The pause affected institutional redemptions over $10M. Circle CEO Jeremy Allaire attributed it to 'a processing delay at a banking partner' and said all pending redemptions were processed by 4 PM ET.", ("crypto",)),
    ("Ripple wins SEC appeal — XRP surges 28% in one hour",
     "The Second Circuit upheld the district court ruling that programmatic XRP sales are not securities. The SEC has 90 days to petition the Supreme Court. XRP hit $3.80, its highest since 2018.", ("crypto",)),
    ("Bitcoin dominance rises to 58% as altcoins sell off",
     "BTC.D hit its highest level since April 2021. ETH/BTC ratio fell to 0.048. Altcoin market cap shed $120B in 48 hours as traders rotated into Bitcoin during the risk-off environment.", ("crypto",)),
    ("CFTC clears Solana futures for CME listing starting March 2026",
     "The CME Group will offer monthly SOL futures with $25 margin per contract. The CFTC's approval signals growing regulatory acceptance. SOL rose 6% on the news.", ("crypto", "politics")),
    # ── Tech & Science ────────────────────────────────────────────
    ("OpenAI launches GPT-5 with real-time reasoning capabilities",
     "The new model demonstrates persistent memory, multi-step planning, and tool use without explicit prompting. API pricing starts at $30 per million tokens. Enterprise customers report 40% productivity gains in early testing.", ("tech_science",)),
    ("TSMC announces 1.4nm chip process for 2027, shares jump 6%",
     "The N14 process promises 30% power reduction and 18% performance improvement over N2. Apple and NVIDIA are confirmed as launch partners. TSMC also broke ground on its third Arizona fab.", ("tech_science",)),
    ("SpaceX Starship completes first orbital refueling mission",
     "Two Starship vehicles successfully docked and transferred 100 tons of liquid methane in low Earth orbit. NASA Administrator hailed it as 'a critical milestone for the Artemis lunar program.'", ("tech_science",)),
    ("FDA grants accelerated approval for Alzheimer's antibody therapy",
     "Eli Lilly's donanemab received full FDA approval after Phase 3 data showed 35% slowing of cognitive decline. The treatment is priced at $26,500/year. Medicare coverage decision expected within 30 days.", ("tech_science",)),
    ("Google DeepMind solves protein folding for all known organisms",
     "AlphaFold 3 has now predicted structures for all 200M known proteins, up from 1M in 2022. The database is freely available. Researchers say this accelerates drug discovery timelines by 3-5 years.", ("tech_science",)),
    # ── Climate ───────────────────────────────────────────────────
    ("Category 5 hurricane makes landfall in Florida, $50B damage estimated",
     "Hurricane Maria struck the Tampa Bay area with 165mph winds, the strongest Florida landfall since 1992. Over 2.5M customers are without power. Insurance stocks fell 8% in after-hours trading.", ("climate",)),
    ("EU carbon border tax takes effect — steel imports face 25% surcharge",
     "The Carbon Border Adjustment Mechanism now applies to steel, cement, aluminum, and fertilizers. Chinese and Indian steelmakers face the highest effective tariffs. The EU expects €14B in annual revenue.", ("climate",)),
    ("California wildfire burns 200K acres, state of emergency declared",
     "The Diablo Fire in Northern California has forced evacuation of 85,000 residents. Cal Fire has deployed 8,000 personnel. Air quality alerts extend to Sacramento and the Bay Area.", ("climate",)),
    ("Global average temperature hits 1.6°C above pre-industrial for first time",
     "The Copernicus Climate Change Service confirmed February 2026 averaged 1.62°C above the 1850-1900 baseline. Scientists warn the 1.5°C Paris Agreement target is effectively breached.", ("climate",)),
    # ── Culture ───────────────────────────────────────────────────
    ("Taylor Swift Eras Tour breaks $2B all-time touring revenue record",
     "The tour grossed $2.07B across 149 shows in 5 continents, surpassing Elton John's Farewell Tour record. Average ticket price was $456. Swift announced 12 additional stadium dates for 2026.", ("culture",)),
    ("Disney+ reports first profitable quarter, subscriber growth accelerates",
     "The streaming platform posted $47M in operating income on 174M subscribers, up 12M QoQ. Ad-supported tier now represents 38% of new sign-ups. Content spending was flat at $4.5B.", ("culture",)),
]

_SOURCES = {
    "Reuters": {
        "desc": "Reuters News Agency — Global wire service",
        "url": "https://www.reuters.com",
        "avatar": "https://logo.clearbit.com/reuters.com",
    },
    "Bloomberg": {
        "desc": "Bloomberg Terminal — Financial news & data",
        "url": "https://www.bloomberg.com",
        "avatar": "https://logo.clearbit.com/bloomberg.com",
    },
    "AP": {
        "desc": "Associated Press — Independent news agency",
        "url": "https://apnews.com",
        "avatar": "https://logo.clearbit.com/apnews.com",
    },
    "TASS": {
        "desc": "TASS — Russian state news agency",
        "url": "https://tass.com",
        "avatar": "https://logo.clearbit.com/tass.com",
    },
    "AFP": {
        "desc": "Agence France-Presse — International wire",
        "url": "https://www.afp.com",
        "avatar": "https://logo.clearbit.com/afp.com",
    },
    "Dow Jones": {
        "desc": "Dow Jones Newswires — Market-moving news",
        "url": "https://www.dowjones.com",
        "avatar": "https://logo.clearbit.com/dowjones.com",
    },
    "FT": {
        "desc": "Financial Times — Global business news",
        "url": "https://www.ft.com",
        "avatar": "https://logo.clearbit.com/ft.com",
    },
}
SOURCES = list(_SOURCES.keys())
MOCK_SOURCE_TYPES = [SourceType.TWITTER, SourceType.TELEGRAM, SourceType.RSS, SourceType.NEWS_WIRE]


def _make_item(headline: str, body: str, categories: tuple[str, ...]) -> RawNewsItem:
    source = random.choice(SOURCES)
    info = _SOURCES[source]
    return RawNewsItem(
        id=uuid.uuid4().hex[:12],
        timestamp=datetime.now(timezone.utc),
        headline=headline,
        body=body,
        source_type=random.choice(MOCK_SOURCE_TYPES),
        source_handle=source,
        source_description=info["desc"],
        source_url=info["url"],
        source_avatar=info["avatar"],
        media_url="",
        pre_tagged_tickers=(),
        ticker_reasons=(),
        pre_tagged_categories=categories,
        pre_highlighted_keywords=(),
        is_priority=random.random() < 0.3,
        is_narrative=False,
        urgency_tags=("HOT",) if random.random() < 0.15 else (),
        economic_event_type="",
        raw_data={},
    )


async def run_mock_feed(
    callback,
    *,
    interval_range: tuple[float, float] = (0.5, 3.0),
    shutdown: asyncio.Event | None = None,
) -> None:
    """Fire random headlines through the callback at realistic intervals."""
    pool = list(HEADLINES)
    random.shuffle(pool)
    idx = 0

    while shutdown is None or not shutdown.is_set():
        headline, body, cats = pool[idx % len(pool)]
        idx += 1
        if idx >= len(pool):
            random.shuffle(pool)
            idx = 0

        item = _make_item(headline, body, cats)
        await callback(item)

        delay = random.uniform(*interval_range)
        try:
            if shutdown:
                await asyncio.wait_for(shutdown.wait(), timeout=delay)
                break
            else:
                await asyncio.sleep(delay)
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------------------
# Mock agent evaluator — replaces Modal + Groq with random decisions
# ---------------------------------------------------------------------------

MOCK_REASONING = {
    "YES": [
        "Direct positive signal for this market",
        "Strong correlation with market thesis",
        "Breaking event supports YES outcome",
        "Historical precedent favors YES",
        "Multiple confirming indicators",
        "Market-moving event, high confidence YES",
    ],
    "NO": [
        "News contradicts market thesis",
        "Negative signal for YES outcome",
        "Counter-evidence to current probability",
        "Event reduces likelihood of YES resolution",
        "Bearish indicator for this market",
    ],
    "SKIP": [
        "Irrelevant to this market",
        "No material impact on outcome",
        "Tangentially related, insufficient signal",
        "Noise — no actionable information",
        "Outside scope of market question",
    ],
}


async def mock_evaluate(story: StoryPayload, market: MarketConfig) -> Decision:
    """
    Drop-in replacement for _modal_evaluate. Returns a random decision
    with simulated Groq-like latency (150–400ms).
    """
    latency = random.uniform(150, 400)
    await asyncio.sleep(latency / 1000)

    current_prob = market.current_probability
    roll = random.random()
    if roll < 0.35:
        action = "YES"
        theo = round(min(0.99, current_prob + random.uniform(0.05, 0.25)), 3)
    elif roll < 0.65:
        action = "NO"
        theo = round(max(0.01, current_prob - random.uniform(0.05, 0.25)), 3)
    else:
        action = "SKIP"
        theo = round(current_prob + random.uniform(-0.02, 0.02), 3)

    delta = abs(theo - current_prob)
    confidence = round(min(delta * 2.0, 1.0), 3)
    reasoning = random.choice(MOCK_REASONING[action])

    return Decision(
        action=action,
        confidence=confidence,
        reasoning=reasoning,
        market_address=market.address,
        story_id=story.id,
        latency_ms=round(latency, 1),
        prompt_version="mock",
        theo=theo,
    )
