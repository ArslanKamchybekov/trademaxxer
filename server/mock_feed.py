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
    # ── Geopolitics ──────────────────────────────────────────────
    ("US deploys additional carrier strike group to Persian Gulf amid rising tensions with Iran", "", ("geopolitics",)),
    ("Pentagon confirms US military assets targeted in Strait of Hormuz attack", "", ("geopolitics",)),
    ("Iran's IRGC claims responsibility for missile strikes on US base in Iraq", "", ("geopolitics",)),
    ("UN Security Council calls emergency session on Iran-US escalation", "", ("geopolitics",)),
    ("Israel conducts airstrikes on Iranian nuclear facilities — IDF confirms", "", ("geopolitics",)),
    ("Saudi Arabia closes airspace to commercial flights amid regional conflict", "", ("geopolitics",)),
    ("NATO allies invoke Article 4 consultations over Middle East crisis", "", ("geopolitics",)),
    ("Russia warns of 'catastrophic consequences' if Iran conflict escalates", "", ("geopolitics",)),
    ("China urges restraint as US-Iran tensions reach highest level since 1979", "", ("geopolitics",)),
    ("Strait of Hormuz shipping lanes disrupted by Iranian naval mines — Lloyd's", "", ("geopolitics",)),
    ("UK Foreign Office advises all nationals to leave Iran immediately", "", ("geopolitics",)),
    ("Turkey closes border with Iraq citing security concerns", "", ("geopolitics",)),
    ("Iran threatens to block all oil shipments through Strait of Hormuz", "", ("geopolitics",)),
    ("US State Department orders non-essential embassy staff out of Baghdad", "", ("geopolitics",)),
    ("France deploys naval frigates to Gulf of Oman for evacuation contingency", "", ("geopolitics",)),
    # ── Politics ─────────────────────────────────────────────────
    ("Trump signs executive order imposing maximum sanctions on Iranian oil exports", "", ("politics",)),
    ("Biden administration releases statement condemning Iranian aggression", "", ("politics",)),
    ("Senate passes bipartisan resolution authorizing use of force against Iran", "", ("politics",)),
    ("Trump to address nation on Middle East crisis at 9 AM ET Saturday", "", ("politics",)),
    ("House passes emergency $12B defense supplemental for Middle East operations", "", ("politics",)),
    ("EU foreign ministers hold emergency summit on Iran sanctions", "", ("politics",)),
    ("Democratic senators call for diplomatic off-ramp with Tehran", "", ("politics",)),
    ("Trump threatens 'obliteration' if Iran retaliates further", "", ("politics",)),
    ("Congressional leaders briefed on classified intelligence regarding Iran", "", ("politics",)),
    ("UK Parliament recalled for emergency debate on Middle East", "", ("politics",)),
    # ── Macro ────────────────────────────────────────────────────
    ("Federal Reserve signals potential emergency rate cut amid market turmoil", "", ("macro",)),
    ("US CPI comes in at 4.1% YoY, above consensus 3.8% — BLS", "", ("macro", "economic_data")),
    ("US jobless claims surge to 285K, highest since March 2024", "", ("macro", "economic_data")),
    ("10-year Treasury yield spikes to 5.2% on inflation fears", "", ("macro",)),
    ("Fed Chair Powell: 'We are monitoring geopolitical risks to price stability'", "", ("macro",)),
    ("US GDP growth revised down to 1.1% for Q4 2025", "", ("macro", "economic_data")),
    ("ECB holds rates steady at 3.75%, cites Middle East uncertainty", "", ("macro",)),
    ("Bank of Japan intervenes to support yen as USD/JPY hits 162", "", ("macro", "forex")),
    ("US consumer confidence drops to 82.3, lowest reading in 14 months", "", ("macro", "economic_data")),
    ("Global flight to safety drives gold above $2,800/oz", "", ("macro", "commodities")),
    ("VIX spikes to 38 as equities sell off on geopolitical risk", "", ("macro",)),
    ("IMF warns global growth could slow to 2.1% if oil disruption persists", "", ("macro",)),
    ("US manufacturing PMI contracts to 46.2, weakest since 2020", "", ("macro", "economic_data")),
    ("Dollar index surges to 108.5 on safe-haven flows", "", ("macro", "forex")),
    ("Fed funds futures now pricing 75% chance of emergency cut", "", ("macro",)),
    # ── Commodities ──────────────────────────────────────────────
    ("Brent crude surges past $125/barrel on Strait of Hormuz fears", "", ("commodities",)),
    ("WTI crude hits $118 as Iran threatens to block oil shipments", "", ("commodities",)),
    ("OPEC+ calls emergency meeting as oil supply disruption fears mount", "", ("commodities",)),
    ("Natural gas futures jump 12% on Middle East supply concerns", "", ("commodities",)),
    ("Gold hits all-time high of $2,850/oz as investors flee to safety", "", ("commodities",)),
    ("Wheat futures surge 8% on Black Sea shipping disruption fears", "", ("commodities",)),
    ("US Strategic Petroleum Reserve release authorized — DOE", "", ("commodities",)),
    ("IEA warns of 4M barrel/day supply gap if Hormuz disrupted for 30 days", "", ("commodities",)),
    ("Copper falls 5% as global recession fears intensify", "", ("commodities",)),
    ("Saudi Aramco pauses IPO plans citing market instability", "", ("commodities",)),
    # ── Crypto ───────────────────────────────────────────────────
    ("Bitcoin surges past $135K as institutional buyers seek hedge against geopolitical risk", "", ("crypto",)),
    ("Ethereum breaks $8,200 on record DeFi inflows during market turmoil", "", ("crypto",)),
    ("Solana TVL hits $28B as traders migrate from centralized exchanges", "", ("crypto",)),
    ("Tether treasury mints $2B USDT in 24 hours amid flight from fiat", "", ("crypto",)),
    ("SEC approves spot Ethereum ETF — trading begins Monday", "", ("crypto", "regulation")),
    ("Bitcoin hash rate hits all-time high as miners price in $150K target", "", ("crypto",)),
    ("Coinbase reports 3x surge in institutional trading volume", "", ("crypto",)),
    ("MicroStrategy announces additional $1.5B Bitcoin purchase", "", ("crypto",)),
    ("Binance sees record $45B daily volume as volatility spikes", "", ("crypto",)),
    ("El Salvador buys 500 BTC during dip, treasury now holds 12,400 BTC", "", ("crypto",)),
    ("BlackRock Bitcoin ETF sees $2.1B single-day inflow — largest ever", "", ("crypto",)),
    ("Circle pauses USDC redemptions for 4 hours citing banking partner issues", "", ("crypto",)),
    ("Ripple wins SEC appeal — XRP surges 28% in one hour", "", ("crypto",)),
    ("Vitalik Buterin proposes emergency EIP for gas limit increase", "", ("crypto",)),
    ("Bitcoin dominance rises to 58% as altcoins sell off", "", ("crypto",)),
    # ── Stocks / Earnings ────────────────────────────────────────
    ("S&P 500 drops 3.2% in worst single-day decline since March 2023", "", ("stocks",)),
    ("Lockheed Martin surges 14% on $8B Pentagon contract for Middle East ops", "", ("stocks",)),
    ("Defense stocks rally: RTX +9%, NOC +11%, LMT +14% on escalation", "", ("stocks",)),
    ("Apple reports Q1 earnings miss — revenue down 4% on supply chain disruption", "", ("stocks", "earnings")),
    ("NVIDIA beats estimates with $38B revenue, guides higher on AI demand", "", ("stocks", "earnings")),
    ("Airline stocks plunge — UAL -8%, DAL -7%, AAL -9% on fuel cost fears", "", ("stocks",)),
    ("Tesla delivers 520K vehicles in Q1, beating estimates by 12%", "", ("stocks", "earnings")),
    ("JPMorgan reports record trading revenue on volatility surge", "", ("stocks", "earnings")),
    ("ExxonMobil posts $14B quarterly profit as crude prices spike", "", ("stocks", "earnings")),
    ("Amazon Web Services revenue up 22% YoY, margins expand to 31%", "", ("stocks", "earnings")),
    # ── Regulation ───────────────────────────────────────────────
    ("SEC files lawsuit against Uniswap Labs for operating unregistered exchange", "", ("regulation",)),
    ("EU MiCA framework goes into full effect — all crypto exchanges must register", "", ("regulation",)),
    ("CFTC clears Solana futures for CME listing starting March 2026", "", ("regulation",)),
    ("US Treasury proposes new KYC rules for DeFi protocols", "", ("regulation",)),
    ("Japan FSA approves framework for tokenized government bonds", "", ("regulation",)),
    # ── Forex ────────────────────────────────────────────────────
    ("EUR/USD drops to 1.02 as dollar strengthens on safe-haven demand", "", ("forex",)),
    ("GBP/USD falls to 1.18 as UK recession fears intensify", "", ("forex",)),
    ("Swiss franc surges to 15-year high against euro on risk-off flows", "", ("forex",)),
    ("Emerging market currencies plunge — Turkish lira -6%, South African rand -4%", "", ("forex",)),
    ("Indian rupee hits record low of 87.5 vs dollar, RBI intervenes", "", ("forex",)),
]

SOURCES = ["Reuters", "Bloomberg", "AP", "TASS", "AFP", "Dow Jones", "FT"]
MOCK_SOURCE_TYPES = [SourceType.TWITTER, SourceType.TELEGRAM, SourceType.RSS, SourceType.NEWS_WIRE]


def _make_item(headline: str, body: str, categories: tuple[str, ...]) -> RawNewsItem:
    return RawNewsItem(
        id=uuid.uuid4().hex[:12],
        timestamp=datetime.now(timezone.utc),
        headline=headline,
        body=body,
        source_type=random.choice(MOCK_SOURCE_TYPES),
        source_handle=random.choice(SOURCES),
        source_description="",
        source_url="",
        source_avatar="",
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

    roll = random.random()
    if roll < 0.35:
        action = "YES"
        confidence = round(random.uniform(0.55, 0.95), 2)
    elif roll < 0.65:
        action = "NO"
        confidence = round(random.uniform(0.50, 0.90), 2)
    else:
        action = "SKIP"
        confidence = round(random.uniform(0.10, 0.50), 2)

    reasoning = random.choice(MOCK_REASONING[action])

    return Decision(
        action=action,
        confidence=confidence,
        reasoning=reasoning,
        market_address=market.address,
        story_id=story.id,
        latency_ms=round(latency, 1),
        prompt_version="mock",
    )
