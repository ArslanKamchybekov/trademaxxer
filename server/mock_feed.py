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
    ("US deploys additional carrier strike group to Persian Gulf amid rising tensions with Iran", "", ("politics",)),
    ("Pentagon confirms US military assets targeted in Strait of Hormuz attack", "", ("politics",)),
    ("Iran's IRGC claims responsibility for missile strikes on US base in Iraq", "", ("politics",)),
    ("UN Security Council calls emergency session on Iran-US escalation", "", ("politics",)),
    ("Israel conducts airstrikes on Iranian nuclear facilities — IDF confirms", "", ("politics",)),
    ("NATO allies invoke Article 4 consultations over Middle East crisis", "", ("politics",)),
    ("Trump signs executive order imposing maximum sanctions on Iranian oil exports", "", ("politics",)),
    ("Senate passes bipartisan resolution authorizing use of force against Iran", "", ("politics",)),
    ("Trump to address nation on Middle East crisis at 9 AM ET Saturday", "", ("politics",)),
    ("House passes emergency $12B defense supplemental for Middle East operations", "", ("politics",)),
    ("EU foreign ministers hold emergency summit on Iran sanctions", "", ("politics",)),
    ("Trump threatens 'obliteration' if Iran retaliates further", "", ("politics",)),
    ("Congressional leaders briefed on classified intelligence regarding Iran", "", ("politics",)),
    ("SEC files lawsuit against Uniswap Labs for operating unregistered exchange", "", ("politics",)),
    ("US Treasury proposes new KYC rules for DeFi protocols", "", ("politics",)),
    # ── Economics ─────────────────────────────────────────────────
    ("Federal Reserve signals potential emergency rate cut amid market turmoil", "", ("economics",)),
    ("US CPI comes in at 4.1% YoY, above consensus 3.8% — BLS", "", ("economics",)),
    ("US jobless claims surge to 285K, highest since March 2024", "", ("economics",)),
    ("Fed Chair Powell: 'We are monitoring geopolitical risks to price stability'", "", ("economics",)),
    ("US GDP growth revised down to 1.1% for Q4 2025", "", ("economics",)),
    ("ECB holds rates steady at 3.75%, cites Middle East uncertainty", "", ("economics",)),
    ("US consumer confidence drops to 82.3, lowest reading in 14 months", "", ("economics",)),
    ("IMF warns global growth could slow to 2.1% if oil disruption persists", "", ("economics",)),
    ("US manufacturing PMI contracts to 46.2, weakest since 2020", "", ("economics",)),
    ("Fed funds futures now pricing 75% chance of emergency cut", "", ("economics",)),
    # ── Financials ────────────────────────────────────────────────
    ("S&P 500 drops 3.2% in worst single-day decline since March 2023", "", ("financials",)),
    ("10-year Treasury yield spikes to 5.2% on inflation fears", "", ("financials",)),
    ("VIX spikes to 38 as equities sell off on geopolitical risk", "", ("financials",)),
    ("Dollar index surges to 108.5 on safe-haven flows", "", ("financials",)),
    ("Brent crude surges past $125/barrel on Strait of Hormuz fears", "", ("financials",)),
    ("Gold hits all-time high of $2,850/oz as investors flee to safety", "", ("financials",)),
    ("EUR/USD drops to 1.02 as dollar strengthens on safe-haven demand", "", ("financials",)),
    ("Bank of Japan intervenes to support yen as USD/JPY hits 162", "", ("financials",)),
    ("JPMorgan reports record trading revenue on volatility surge", "", ("financials",)),
    ("ExxonMobil posts $14B quarterly profit as crude prices spike", "", ("financials",)),
    # ── Companies ─────────────────────────────────────────────────
    ("Apple reports Q1 earnings miss — revenue down 4% on supply chain disruption", "", ("companies",)),
    ("NVIDIA beats estimates with $38B revenue, guides higher on AI demand", "", ("companies",)),
    ("Tesla delivers 520K vehicles in Q1, beating estimates by 12%", "", ("companies",)),
    ("Amazon Web Services revenue up 22% YoY, margins expand to 31%", "", ("companies",)),
    ("Lockheed Martin surges 14% on $8B Pentagon contract for Middle East ops", "", ("companies",)),
    ("Saudi Aramco pauses IPO plans citing market instability", "", ("companies",)),
    ("MicroStrategy announces additional $1.5B Bitcoin purchase", "", ("companies", "crypto")),
    ("Coinbase reports 3x surge in institutional trading volume", "", ("companies", "crypto")),
    # ── Crypto ────────────────────────────────────────────────────
    ("Bitcoin surges past $135K as institutional buyers seek hedge against geopolitical risk", "", ("crypto",)),
    ("Ethereum breaks $8,200 on record DeFi inflows during market turmoil", "", ("crypto",)),
    ("Solana TVL hits $28B as traders migrate from centralized exchanges", "", ("crypto",)),
    ("Tether treasury mints $2B USDT in 24 hours amid flight from fiat", "", ("crypto",)),
    ("SEC approves spot Ethereum ETF — trading begins Monday", "", ("crypto", "politics")),
    ("Bitcoin hash rate hits all-time high as miners price in $150K target", "", ("crypto",)),
    ("BlackRock Bitcoin ETF sees $2.1B single-day inflow — largest ever", "", ("crypto",)),
    ("Circle pauses USDC redemptions for 4 hours citing banking partner issues", "", ("crypto",)),
    ("Ripple wins SEC appeal — XRP surges 28% in one hour", "", ("crypto",)),
    ("Bitcoin dominance rises to 58% as altcoins sell off", "", ("crypto",)),
    ("CFTC clears Solana futures for CME listing starting March 2026", "", ("crypto", "politics")),
    # ── Tech & Science ────────────────────────────────────────────
    ("OpenAI launches GPT-5 with real-time reasoning capabilities", "", ("tech_science",)),
    ("TSMC announces 1.4nm chip process for 2027, shares jump 6%", "", ("tech_science",)),
    ("SpaceX Starship completes first orbital refueling mission", "", ("tech_science",)),
    ("FDA grants accelerated approval for Alzheimer's antibody therapy", "", ("tech_science",)),
    ("Google DeepMind solves protein folding for all known organisms", "", ("tech_science",)),
    # ── Climate ───────────────────────────────────────────────────
    ("Category 5 hurricane makes landfall in Florida, $50B damage estimated", "", ("climate",)),
    ("EU carbon border tax takes effect — steel imports face 25% surcharge", "", ("climate",)),
    ("California wildfire burns 200K acres, state of emergency declared", "", ("climate",)),
    ("Global average temperature hits 1.6°C above pre-industrial for first time", "", ("climate",)),
    # ── Culture ───────────────────────────────────────────────────
    ("Taylor Swift Eras Tour breaks $2B all-time touring revenue record", "", ("culture",)),
    ("Disney+ reports first profitable quarter, subscriber growth accelerates", "", ("culture",)),
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
