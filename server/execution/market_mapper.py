"""
Market mapping between Kalshi and DFlow prediction markets
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class MarketMapping:
    kalshi_ticker: str
    kalshi_question: str
    dflow_market_id: str
    dflow_question: str
    confidence_score: float  # 0.0 - 1.0 similarity score


class MarketMapper:
    """Maps between Kalshi tickers and DFlow market IDs based on question similarity"""

    def __init__(self):
        self.mappings: Dict[str, MarketMapping] = {}
        self.kalshi_markets: List[Dict] = []
        self.dflow_markets: List[Dict] = []

    def normalize_question(self, question: str) -> str:
        """Normalize a market question for comparison"""
        # Remove common prefixes/suffixes
        question = re.sub(r'^Will\s+', '', question, flags=re.IGNORECASE)
        question = re.sub(r'\s+by\s+\d{4}[-/]\d{2}[-/]\d{2}.*?$', '', question, flags=re.IGNORECASE)
        question = re.sub(r'\s+before\s+\d{4}[-/]\d{2}[-/]\d{2}.*?$', '', question, flags=re.IGNORECASE)

        # Convert to lowercase and remove punctuation
        question = re.sub(r'[^\w\s]', ' ', question.lower())

        # Remove extra whitespace
        question = ' '.join(question.split())

        return question

    def extract_keywords(self, question: str) -> set[str]:
        """Extract important keywords from a market question"""
        normalized = self.normalize_question(question)

        # Common stop words to ignore
        stop_words = {
            'will', 'be', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'among', 'is', 'are', 'was', 'were', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'can', 'could', 'should', 'would', 'may',
            'might', 'must', 'shall', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
            'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her',
            'its', 'our', 'their'
        }

        words = set(normalized.split())
        keywords = words - stop_words

        # Filter out very short words (less than 3 characters)
        keywords = {w for w in keywords if len(w) >= 3}

        return keywords

    def calculate_similarity(self, kalshi_question: str, dflow_question: str) -> float:
        """Calculate similarity score between two market questions"""
        kalshi_keywords = self.extract_keywords(kalshi_question)
        dflow_keywords = self.extract_keywords(dflow_question)

        if not kalshi_keywords or not dflow_keywords:
            return 0.0

        # Jaccard similarity: intersection / union
        intersection = kalshi_keywords.intersection(dflow_keywords)
        union = kalshi_keywords.union(dflow_keywords)

        jaccard_score = len(intersection) / len(union) if union else 0.0

        # Bonus for exact phrase matches
        kalshi_norm = self.normalize_question(kalshi_question)
        dflow_norm = self.normalize_question(dflow_question)

        # Check for common phrases
        phrase_bonus = 0.0
        kalshi_phrases = set(kalshi_norm.split())
        dflow_phrases = set(dflow_norm.split())

        common_phrases = kalshi_phrases.intersection(dflow_phrases)
        if common_phrases:
            phrase_bonus = min(0.3, len(common_phrases) * 0.1)

        return min(1.0, jaccard_score + phrase_bonus)

    def create_mappings(self, kalshi_markets: List[Dict], dflow_markets: List[Dict]) -> Dict[str, MarketMapping]:
        """Create mappings between Kalshi and DFlow markets"""
        self.kalshi_markets = kalshi_markets
        self.dflow_markets = dflow_markets
        self.mappings = {}

        for kalshi_market in kalshi_markets:
            kalshi_ticker = kalshi_market.get('address', '')
            kalshi_question = kalshi_market.get('question', '')

            if not kalshi_ticker or not kalshi_question:
                continue

            best_match = None
            best_score = 0.0

            for dflow_market in dflow_markets:
                dflow_id = dflow_market.get('market_id', '')
                dflow_question = dflow_market.get('question', '')

                if not dflow_id or not dflow_question:
                    continue

                similarity = self.calculate_similarity(kalshi_question, dflow_question)

                if similarity > best_score and similarity >= 0.3:  # Minimum threshold
                    best_score = similarity
                    best_match = MarketMapping(
                        kalshi_ticker=kalshi_ticker,
                        kalshi_question=kalshi_question,
                        dflow_market_id=dflow_id,
                        dflow_question=dflow_question,
                        confidence_score=similarity
                    )

            if best_match:
                self.mappings[kalshi_ticker] = best_match

        return self.mappings

    def get_dflow_market_id(self, kalshi_ticker: str) -> Optional[str]:
        """Get DFlow market ID for a given Kalshi ticker"""
        mapping = self.mappings.get(kalshi_ticker)
        return mapping.dflow_market_id if mapping else None

    def get_mapping(self, kalshi_ticker: str) -> Optional[MarketMapping]:
        """Get the full mapping for a Kalshi ticker"""
        return self.mappings.get(kalshi_ticker)

    def get_high_confidence_mappings(self, min_confidence: float = 0.7) -> Dict[str, MarketMapping]:
        """Get only high-confidence mappings"""
        return {
            ticker: mapping
            for ticker, mapping in self.mappings.items()
            if mapping.confidence_score >= min_confidence
        }

    def print_mapping_summary(self):
        """Print a summary of created mappings"""
        if not self.mappings:
            print("No mappings created")
            return

        print(f"\nMarket Mapping Summary:")
        print(f"Total Kalshi markets: {len(self.kalshi_markets)}")
        print(f"Total DFlow markets: {len(self.dflow_markets)}")
        print(f"Successful mappings: {len(self.mappings)}")

        high_conf = len([m for m in self.mappings.values() if m.confidence_score >= 0.7])
        med_conf = len([m for m in self.mappings.values() if 0.5 <= m.confidence_score < 0.7])
        low_conf = len([m for m in self.mappings.values() if m.confidence_score < 0.5])

        print(f"High confidence (≥0.7): {high_conf}")
        print(f"Medium confidence (0.5-0.7): {med_conf}")
        print(f"Low confidence (<0.5): {low_conf}")

        # Show top 5 mappings by confidence
        top_mappings = sorted(self.mappings.values(), key=lambda m: m.confidence_score, reverse=True)[:5]

        print(f"\nTop {len(top_mappings)} mappings:")
        for i, mapping in enumerate(top_mappings, 1):
            print(f"{i}. [{mapping.confidence_score:.2f}] {mapping.kalshi_ticker}")
            print(f"   Kalshi: {mapping.kalshi_question[:80]}...")
            print(f"   DFlow: {mapping.dflow_question[:80]}...")
            print()


# Singleton mapper instance
_mapper = MarketMapper()

def get_market_mapper() -> MarketMapper:
    """Get the global market mapper instance"""
    return _mapper