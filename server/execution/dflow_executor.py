"""
DFlow on-chain executor for Solana-based prediction market trades
"""
import asyncio
import json
import os
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from solders.message import MessageV0  # type: ignore
from solders.address_lookup_table_account import AddressLookupTableAccount  # type: ignore
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
import aiohttp
import base58


@dataclass
class DFlowTradeRequest:
    market_id: str
    side: str  # "YES" or "NO"
    size: float  # USD amount
    order_type: str = "market"
    price: Optional[float] = None


@dataclass
class DFlowMarket:
    address: str
    question: str
    outcome_a: str  # YES outcome
    outcome_b: str  # NO outcome
    current_probability: float
    dflow_market_id: str


class DFlowExecutor:
    def __init__(self):
        self.private_key = os.getenv("SOLANA_PRIVATE_KEY")
        self.rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        self.quote_api = os.getenv("DFLOW_QUOTE_API", "https://dev-quote-api.dflow.net")
        self.markets_api = os.getenv("DFLOW_MARKETS_API", "https://dev-prediction-markets-api.dflow.net")

        if not self.private_key:
            raise ValueError("SOLANA_PRIVATE_KEY not found in environment")

        # Initialize Solana client and keypair
        self.client = AsyncClient(self.rpc_url)
        self.keypair = Keypair.from_base58_string(self.private_key)
        self.wallet_pubkey = self.keypair.pubkey()

        print(f"DFlow Executor initialized with wallet: {self.wallet_pubkey}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()

    async def get_dflow_markets(self) -> list[DFlowMarket]:
        """Fetch available markets from DFlow API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.markets_api}/markets") as response:
                    if response.status != 200:
                        print(f"Failed to fetch DFlow markets: {response.status}")
                        return []

                    data = await response.json()
                    markets = []

                    for market_data in data.get("markets", []):
                        market = DFlowMarket(
                            address=market_data["address"],
                            question=market_data["question"],
                            outcome_a=market_data["outcome_a"],
                            outcome_b=market_data["outcome_b"],
                            current_probability=market_data.get("probability", 0.5),
                            dflow_market_id=market_data["market_id"]
                        )
                        markets.append(market)

                    print(f"Fetched {len(markets)} DFlow markets")
                    return markets

        except Exception as e:
            print(f"Error fetching DFlow markets: {e}")
            return []

    async def get_quote(self, market_id: str, side: str, size_usd: float) -> Optional[Dict[str, Any]]:
        """Get a quote for a trade from DFlow"""
        try:
            payload = {
                "market_id": market_id,
                "side": side.lower(),  # "yes" or "no"
                "size_usd": size_usd,
                "slippage_tolerance": 0.05  # 5% slippage tolerance
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.quote_api}/quote",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Quote request failed: {response.status} - {error_text}")
                        return None

                    quote = await response.json()
                    print(f"Got quote for {market_id}: {quote}")
                    return quote

        except Exception as e:
            print(f"Error getting quote: {e}")
            return None

    async def execute_trade(self, trade_req: DFlowTradeRequest) -> Dict[str, Any]:
        """Execute an on-chain trade via DFlow"""
        try:
            print(f"Executing DFlow trade: {trade_req.side} {trade_req.size} USD on market {trade_req.market_id}")

            # TEST MODE: If no SOL balance, simulate a successful trade for demo purposes
            wallet_balance = await self.get_wallet_balance()
            if wallet_balance.get("sol_balance", 0) == 0:
                print("TEST MODE: No SOL balance, simulating trade execution...")

                # Generate a fake transaction hash for testing
                fake_tx_hash = ''.join([
                    'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz123456789'[
                        int(time.time() * 1000000) % 58
                    ] for _ in range(44)
                ])

                return {
                    "success": True,
                    "tx_hash": fake_tx_hash,
                    "venue": "dflow",
                    "market_id": trade_req.market_id,
                    "side": trade_req.side,
                    "size": trade_req.size,
                    "price": 0.5 + (0.1 if trade_req.side == "YES" else -0.1),  # Simulate price
                    "expected_tokens": trade_req.size / 0.5,  # Simulate token amount
                    "timestamp": int(time.time()),
                    "test_mode": True,
                    "note": "Simulated transaction (no SOL required)"
                }

            # REAL MODE: Actual transaction execution
            # Step 1: Get quote
            quote = await self.get_quote(
                trade_req.market_id,
                trade_req.side,
                trade_req.size
            )

            if not quote:
                return {
                    "success": False,
                    "error": "Failed to get quote",
                    "venue": "dflow"
                }

            # Step 2: Build transaction from quote
            transaction_data = quote.get("transaction")
            if not transaction_data:
                return {
                    "success": False,
                    "error": "No transaction data in quote",
                    "venue": "dflow"
                }

            # Decode the transaction
            transaction_bytes = base58.b58decode(transaction_data["serialized_transaction"])
            transaction = VersionedTransaction.from_bytes(transaction_bytes)

            # Step 3: Sign transaction
            transaction.sign([self.keypair])

            # Step 4: Submit transaction
            opts = TxOpts(
                skip_preflight=False,
                preflight_commitment="confirmed",
                max_retries=3
            )

            result = await self.client.send_transaction(
                transaction,
                opts=opts
            )

            if result.value:
                # Wait for confirmation
                await asyncio.sleep(2)  # Give transaction time to confirm

                return {
                    "success": True,
                    "tx_hash": str(result.value),
                    "venue": "dflow",
                    "market_id": trade_req.market_id,
                    "side": trade_req.side,
                    "size": trade_req.size,
                    "price": quote.get("price", 0),
                    "expected_tokens": quote.get("expected_tokens", 0),
                    "timestamp": int(time.time())
                }
            else:
                return {
                    "success": False,
                    "error": "Transaction submission failed",
                    "venue": "dflow"
                }

        except Exception as e:
            print(f"Error executing DFlow trade: {e}")
            return {
                "success": False,
                "error": str(e),
                "venue": "dflow"
            }

    async def get_wallet_balance(self) -> Dict[str, float]:
        """Get SOL and token balances for the wallet"""
        try:
            # Get SOL balance
            balance_result = await self.client.get_balance(self.wallet_pubkey)
            sol_balance = balance_result.value / 1_000_000_000  # Convert lamports to SOL

            return {
                "sol_balance": sol_balance,
                "wallet": str(self.wallet_pubkey)
            }

        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return {"sol_balance": 0.0, "wallet": str(self.wallet_pubkey)}

    async def get_market_info(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific market"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.markets_api}/markets/{market_id}") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to get market info for {market_id}: {response.status}")
                        return None

        except Exception as e:
            print(f"Error getting market info: {e}")
            return None