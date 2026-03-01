"""
Demo contracts + synthetic headline injector.

Provides a handful of always-on contracts matched to current events, plus a
background coroutine that periodically injects realistic headlines into the
live news stream. Headlines are designed to always move the needle on at
least one demo contract.
"""
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone, timedelta

from agents.schemas import MarketConfig
from news_streamer.models.news import RawNewsItem, SourceType

# ---------------------------------------------------------------------------
# Demo contracts — prepended to markets list, auto-enabled
# ---------------------------------------------------------------------------

DEMO_CONTRACTS: list[MarketConfig] = [
    MarketConfig(
        address="KXIRNUS-26APR01-T82",
        question="Will the US conduct a military strike on Iran before April 2026?",
        current_probability=0.82,
        tags=("politics",),
        expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        rules_primary="Resolves Yes if the US military carries out at least one kinetic strike on Iranian territory or Iranian military assets before April 1, 2026.",
    ),
    MarketConfig(
        address="KXKHM-26MAR15-T55",
        question="Will Iran confirm Khamenei's death before March 15, 2026?",
        current_probability=0.55,
        tags=("politics",),
        expires_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
        rules_primary="Resolves Yes if the Iranian government or a credible international body officially confirms Khamenei's death before March 15, 2026.",
    ),
    MarketConfig(
        address="KXCL130-26APR01-T41",
        question="Will Brent crude exceed $130/barrel before April 2026?",
        current_probability=0.41,
        tags=("financials", "economics"),
        expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        rules_primary="Resolves Yes if the ICE Brent Crude front-month futures contract trades at or above $130.00 at any point before April 1, 2026.",
    ),
    MarketConfig(
        address="KXFEDECUT-26APR01-T23",
        question="Will the Federal Reserve announce an emergency rate cut by April 2026?",
        current_probability=0.23,
        tags=("economics",),
        expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        rules_primary="Resolves Yes if the FOMC announces a federal funds rate reduction outside of a scheduled meeting before April 1, 2026.",
    ),
    MarketConfig(
        address="KXBTC150-26APR01-T34",
        question="Will Bitcoin exceed $150,000 before April 2026?",
        current_probability=0.34,
        tags=("crypto", "financials"),
        expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        rules_primary="Resolves Yes if the CoinDesk Bitcoin Price Index (XBX) prints at or above $150,000 at any point before April 1, 2026.",
    ),
    MarketConfig(
        address="KXVIX40-26APR01-T38",
        question="Will the VIX close above 40 before April 2026?",
        current_probability=0.38,
        tags=("financials",),
        expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        rules_primary="Resolves Yes if the CBOE Volatility Index (VIX) has a daily closing value above 40.00 before April 1, 2026.",
    ),
    MarketConfig(
        address="KXHRMZ-26MAY01-T18",
        question="Will Iran close the Strait of Hormuz to commercial shipping before May 2026?",
        current_probability=0.18,
        tags=("politics", "economics", "financials"),
        expires_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        rules_primary="Resolves Yes if Iran officially blocks or the US Navy confirms a blockade of commercial shipping through the Strait of Hormuz before May 1, 2026.",
    ),
]

# ---------------------------------------------------------------------------
# Synthetic headlines — each targets one or more demo contracts
# ---------------------------------------------------------------------------

_HEADLINES: list[tuple[str, tuple[str, ...], bool]] = [
    # (headline, categories, is_priority)

    # IRAN-STRIKE / KHAMENEI
    ("IDF spokesperson confirms second wave of strikes on Iranian military targets underway", ("politics",), True),
    ("Pentagon: US B-2 bombers deployed from Diego Garcia to support Iran operations", ("politics",), True),
    ("Iranian state TV goes off air in Tehran amid reports of communications blackout", ("politics",), True),
    ("IRGC launches retaliatory ballistic missile salvo toward US assets in Gulf region", ("politics",), True),
    ("Axios: Senior US official says Khamenei's bunker was hit in opening salvo", ("politics",), True),
    ("France calls emergency UN Security Council session on Iran conflict", ("politics",), False),
    ("Iranian foreign ministry issues statement — notably silent on Khamenei's status", ("politics",), False),
    ("CENTCOM confirms all US military personnel in region accounted for after Iranian retaliation", ("politics",), False),
    ("Turkish intelligence sources: Iran's Revolutionary Guard chain of command in disarray", ("politics",), True),
    ("Al Jazeera: Unverified footage shows heavy damage in central Tehran", ("politics",), False),
    ("Netanyahu: 'We have set Iran's nuclear program back by a decade'", ("politics",), True),
    ("Reuters: Iran's acting president calls for calm, says 'leadership is intact'", ("politics",), False),
    ("Satellite imagery shows multiple destroyed sites at Isfahan nuclear facility", ("politics", "tech_science"), True),

    # OIL / HORMUZ / FINANCIALS
    ("OPEC emergency statement: monitoring Strait of Hormuz situation closely", ("financials", "economics"), True),
    ("Lloyd's of London suspends marine insurance for Persian Gulf tanker routes", ("financials",), True),
    ("Brent crude futures gap up 8% in Asian pre-market trading", ("financials",), True),
    ("Saudi Aramco halts eastbound crude shipments through Hormuz as precaution", ("financials", "economics"), True),
    ("US DOE authorizes emergency release of 30M barrels from Strategic Petroleum Reserve", ("financials", "economics"), False),
    ("Goldman Sachs raises Brent forecast to $140 citing sustained Gulf disruption risk", ("financials",), False),
    ("Iran navy deploys fast-attack boats near Strait of Hormuz — CENTCOM monitoring", ("politics", "financials"), True),
    ("Dubai ports authority reports normal operations despite regional tensions", ("financials",), False),
    ("Japan and South Korea activate strategic oil reserves amid supply fears", ("financials", "economics"), False),
    ("Natural gas prices surge 9% in European trading on Middle East spillover risk", ("financials",), False),

    # FED / ECONOMICS
    ("CME FedWatch: probability of emergency rate cut surges to 68% overnight", ("economics",), True),
    ("Fed Governor Waller: 'We stand ready to act if financial conditions tighten sharply'", ("economics",), True),
    ("10-year Treasury yield drops 18bps as flight to safety accelerates", ("financials", "economics"), False),
    ("ECB President Lagarde: coordinating with Fed on liquidity backstops", ("economics",), False),
    ("Wall Street futures indicate S&P 500 will open down 4.2% on Monday", ("financials",), True),
    ("US consumer sentiment flash reading plunges to 71.3 on geopolitical shock", ("economics",), False),

    # CRYPTO / BTC
    ("Bitcoin spikes 7% in 2 hours as investors seek non-sovereign stores of value", ("crypto",), True),
    ("Tether mints $3B USDT in 24 hours — largest single-day issuance ever", ("crypto",), True),
    ("BlackRock IBIT Bitcoin ETF sees $1.8B inflow in single trading session", ("crypto", "financials"), True),
    ("Coinbase experiences intermittent outages due to 5x normal trading volume", ("crypto", "companies"), False),
    ("Bitcoin hash rate hits all-time high as miners price in geopolitical premium", ("crypto",), False),
    ("MicroStrategy announces $500M BTC purchase at average price of $138,200", ("crypto", "companies"), False),

    # VIX / BROAD MARKET
    ("CBOE VIX futures spike to 42 in after-hours trading on Iran escalation", ("financials",), True),
    ("S&P 500 circuit breaker triggered — trading halted for 15 minutes at open", ("financials",), True),
    ("Defense stocks rally in pre-market: LMT +11%, RTX +8%, NOC +9%", ("financials", "companies"), False),
    ("Airline stocks plunge pre-market on fuel cost fears: UAL -9%, DAL -7%", ("financials", "companies"), False),
    ("Gold surges past $2,900/oz setting new all-time high on safe-haven demand", ("financials",), True),
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
    "Axios": {
        "desc": "Axios — Smart brevity news",
        "url": "https://www.axios.com",
        "avatar": "https://logo.clearbit.com/axios.com",
    },
    "WSJ": {
        "desc": "The Wall Street Journal — Business & markets",
        "url": "https://www.wsj.com",
        "avatar": "https://logo.clearbit.com/wsj.com",
    },
    "FT": {
        "desc": "Financial Times — Global business news",
        "url": "https://www.ft.com",
        "avatar": "https://logo.clearbit.com/ft.com",
    },
}
_SOURCE_NAMES = list(_SOURCES.keys())


def _make_news_item(
    headline: str,
    categories: tuple[str, ...],
    is_priority: bool,
) -> RawNewsItem:
    source = random.choice(_SOURCE_NAMES)
    info = _SOURCES[source]
    return RawNewsItem(
        id=uuid.uuid4().hex[:12],
        timestamp=datetime.now(timezone.utc),
        headline=headline,
        body="",
        source_type=random.choice([SourceType.NEWS_WIRE, SourceType.TWITTER, SourceType.RSS]),
        source_handle=source,
        source_description=info["desc"],
        source_url=info["url"],
        source_avatar=info["avatar"],
        media_url="",
        pre_tagged_tickers=(),
        ticker_reasons=(),
        pre_tagged_categories=categories,
        pre_highlighted_keywords=(),
        is_priority=is_priority,
        is_narrative=False,
        urgency_tags=("HOT",) if is_priority and random.random() < 0.4 else (),
        economic_event_type="",
        raw_data={},
    )


async def run_demo_injector(
    callback,
    *,
    interval_range: tuple[float, float] = (8.0, 25.0),
    shutdown: asyncio.Event | None = None,
) -> None:
    """Inject synthetic headlines into the live news stream at random intervals."""
    pool = list(_HEADLINES)
    random.shuffle(pool)
    idx = 0

    while shutdown is None or not shutdown.is_set():
        headline, cats, priority = pool[idx % len(pool)]
        idx += 1
        if idx >= len(pool):
            random.shuffle(pool)
            idx = 0

        item = _make_news_item(headline, cats, priority)
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
