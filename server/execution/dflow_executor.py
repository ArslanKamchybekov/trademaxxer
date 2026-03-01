"""
DFlow on-chain executor for Solana-based prediction market trades.
Supports local keypair signing or Turnkey API signing.
"""
import asyncio
import base64
import json
import os
import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from solders.message import MessageV0, to_bytes_versioned  # type: ignore
from solders.address_lookup_table_account import AddressLookupTableAccount  # type: ignore
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
import aiohttp
import base58

# Turnkey X-Stamp auth (optional)
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    serialization = None


@dataclass
class DFlowTradeRequest:
    market_id: str
    side: str  # "YES" or "NO"
    size: float  # USD amount
    order_type: str = "market"
    price: Optional[float] = None


@dataclass
class DFlowMarket:
    address: str  # ticker
    question: str  # title
    outcome_a: str  # yesSubTitle
    outcome_b: str  # noSubTitle
    current_probability: float
    dflow_market_id: str  # ticker
    status: str
    yes_mint: Optional[str] = None  # outcome token mint for YES
    no_mint: Optional[str] = None   # outcome token mint for NO


def _normalize_hex_key(key: str) -> str:
    """Strip 0x prefix and whitespace; leave case as-is (Turnkey is case-sensitive)."""
    if not key:
        return key
    k = key.strip()
    if k.lower().startswith("0x"):
        k = k[2:].strip()
    return k


def _turnkey_stamp(body_str: str, api_public_key_hex: str, api_private_key_hex: str) -> str:
    """Build X-Stamp header value: sign body with P-256 API key, base64url-encode stamp JSON.
    Supports: (1) Private key as hex (64 hex chars, optional 0x prefix); public key as hex (66 chars compressed).
    (2) Private key as PEM (-----BEGIN EC PRIVATE KEY-----); public key is then derived from it.
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("Turnkey signing requires cryptography (pip install cryptography)")
    priv_str = (api_private_key_hex or "").strip()
    pub_str = (api_public_key_hex or "").strip()

    if "-----BEGIN" in priv_str or "PRIVATE KEY" in priv_str:
        # Load PEM (restore newlines if stored in one line)
        pem = priv_str.replace("\\n", "\n")
        try:
            ec_private = serialization.load_pem_private_key(
                pem.encode(), password=None, backend=default_backend()
            )
        except Exception as e:
            raise RuntimeError("Turnkey API private key PEM could not be loaded: " + str(e)) from e
        if not isinstance(ec_private, ec.EllipticCurvePrivateKey):
            raise RuntimeError("Turnkey API key must be P-256 (EC). Other key types are not supported.")
        pub_bytes = ec_private.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint,
        )
        pub_hex = pub_bytes.hex()
    else:
        pub_hex = _normalize_hex_key(pub_str)
        priv_hex = _normalize_hex_key(priv_str)
        try:
            ec_private = ec.derive_private_key(
                int(priv_hex, 16), ec.SECP256R1(), default_backend()
            )
        except ValueError as e:
            raise RuntimeError(
                "Turnkey API private key must be hex (64 chars) or PEM. Error: " + str(e)
            ) from e
    signature = ec_private.sign(body_str.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    stamp = {
        "publicKey": pub_hex,
        "scheme": "SIGNATURE_SCHEME_TK_API_P256",
        "signature": signature.hex(),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(stamp).encode()).decode().rstrip("=")
    return encoded


class DFlowExecutor:
    def __init__(self):
        self.private_key = os.getenv("SOLANA_PRIVATE_KEY")
        self.rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        self.quote_api = os.getenv("DFLOW_QUOTE_API", "https://quote-api.dflow.net")
        self.markets_api = os.getenv("DFLOW_MARKETS_API", "https://prediction-markets-api.dflow.net")
        self.api_key = os.getenv("DFLOW_API_KEY")

        # Turnkey: optional; when set, we sign via Turnkey API (X-Stamp auth).
        # TURNKEY_SIGN_WITH = Private Key ID or Wallet Account ID (UUID from dashboard), NOT Solana address.
        def _clean_env(s: str) -> str:
            if not s:
                return ""
            s = s.strip()
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                s = s[1:-1].strip()
            return s

        self.turnkey_base = _clean_env(os.getenv("TURNKEY_BASE_URL") or "https://api.turnkey.com")
        self.turnkey_org_id = _clean_env(os.getenv("TURNKEY_ORGANIZATION_ID") or "")
        self.turnkey_api_public_key = _clean_env(os.getenv("TURNKEY_API_PUBLIC_KEY") or "")
        self.turnkey_api_private_key = _clean_env(os.getenv("TURNKEY_API_PRIVATE_KEY") or "")
        self.turnkey_sign_with = _clean_env(os.getenv("TURNKEY_SIGN_WITH") or "")
        self._use_turnkey = bool(
            self.turnkey_org_id
            and self.turnkey_api_public_key
            and self.turnkey_api_private_key
            and self.turnkey_sign_with
        )

        if self._use_turnkey:
            self.wallet_pubkey_str = _clean_env(os.getenv("SOLANA_WALLET_ADDRESS") or "")
            if not self.wallet_pubkey_str:
                raise ValueError(
                    "When using Turnkey, set SOLANA_WALLET_ADDRESS (your Solana wallet public key)"
                )
            self.wallet_pubkey = Pubkey.from_string(self.wallet_pubkey_str)
            self.keypair = None
            self.client = AsyncClient(self.rpc_url)
            print(f"DFlow Executor initialized with Turnkey signing, wallet: {self.wallet_pubkey}")
        else:
            if not self.private_key:
                raise ValueError("SOLANA_PRIVATE_KEY not found in environment")
            self.client = AsyncClient(self.rpc_url)
            self.keypair = Keypair.from_base58_string(self.private_key)
            self.wallet_pubkey = self.keypair.pubkey()
            self.wallet_pubkey_str = str(self.wallet_pubkey)
            print(f"DFlow Executor initialized with wallet: {self.wallet_pubkey}")

        # Cache: market_id -> (yes_mint, no_mint) for order API outputMint
        self._market_mints: Dict[str, tuple] = {}

        print(f"DFlow API authentication: {'✓ Enabled' if self.api_key else '✗ No API key'}")
        if self._use_turnkey:
            sw = self.turnkey_sign_with
            if len(sw) == 36 and sw.count("-") == 4:
                print(f"Transaction signing: Turnkey (signWith={sw[:8]}...{sw[-4:]})")
            else:
                print(f"Transaction signing: Turnkey (signWith length={len(sw)} — if not a UUID, fix TURNKEY_SIGN_WITH)")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers for DFlow API requests"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            # Try both common authentication methods
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()

    async def get_dflow_markets(self) -> list[DFlowMarket]:
        """Fetch available markets from DFlow API"""
        try:
            headers = self._get_auth_headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.markets_api}/api/v1/markets", headers=headers) as response:
                    if response.status == 403:
                        print(f"DFlow markets API access denied (403) - production API requires special credentials")
                        return []
                    elif response.status != 200:
                        print(f"Failed to fetch DFlow markets: {response.status}")
                        return []

                    data = await response.json()
                    markets = []

                    for market_data in data.get("markets", []):
                        # Only include active markets (not finalized/closed)
                        if market_data.get("status") in ["finalized", "closed"]:
                            continue

                        # Parse outcome token mints from accounts (first account entry)
                        yes_mint = None
                        no_mint = None
                        accounts = market_data.get("accounts") or {}
                        account_values = list(accounts.values()) if isinstance(accounts, dict) else []
                        if account_values and isinstance(account_values[0], dict):
                            yes_mint = account_values[0].get("yesMint")
                            no_mint = account_values[0].get("noMint")

                        ticker = market_data["ticker"]
                        if yes_mint and no_mint:
                            self._market_mints[ticker] = (yes_mint, no_mint)

                        market = DFlowMarket(
                            address=ticker,
                            question=market_data["title"],
                            outcome_a=market_data.get("yesSubTitle", "YES"),
                            outcome_b=market_data.get("noSubTitle", "NO"),
                            current_probability=0.5,  # DFlow doesn't provide current probability in this format
                            dflow_market_id=ticker,
                            status=market_data.get("status", "unknown"),
                            yes_mint=yes_mint,
                            no_mint=no_mint,
                        )
                        markets.append(market)

                    print(f"Fetched {len(markets)} DFlow markets")
                    return markets

        except Exception as e:
            print(f"Error fetching DFlow markets: {e}")
            return []

    def _get_outcome_mint(self, market_id: str, side: str) -> Optional[str]:
        """Resolve YES/NO outcome token mint for a market. Returns None if not in cache."""
        mints = self._market_mints.get(market_id)
        if not mints:
            return None
        yes_mint, no_mint = mints
        return yes_mint if side.upper() == "YES" else no_mint

    async def get_order_transaction(self, market_id: str, side: str, size_usd: float) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Get unsigned transaction for a trade from DFlow. Returns (order_data, error_message)."""
        try:
            # Resolve outcome token mint (required by DFlow order API)
            output_mint = self._get_outcome_mint(market_id, side)
            if not output_mint:
                await self.get_dflow_markets()
                output_mint = self._get_outcome_mint(market_id, side)
            if not output_mint:
                info = await self.get_market_info(market_id)
                if info:
                    accounts = info.get("accounts") or {}
                    account_values = list(accounts.values()) if isinstance(accounts, dict) else []
                    if account_values and isinstance(account_values[0], dict):
                        ym, nm = account_values[0].get("yesMint"), account_values[0].get("noMint")
                        if ym and nm:
                            self._market_mints[market_id] = (ym, nm)
                            output_mint = self._get_outcome_mint(market_id, side)
            if not output_mint:
                msg = (
                    f"No outcome mint for market {market_id} (side={side}). "
                    "Market may be uninitialized on DFlow or not in the markets list."
                )
                print(f"Order failed: {msg}")
                return None, msg

            amount = int(size_usd * 1_000_000)
            if amount < 1_000_000:
                amount = 1_000_000

            payload = {
                "inputMint": "So11111111111111111111111111111111111111112",
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": 500,
                "userPublicKey": str(self.wallet_pubkey)
            }

            headers = self._get_auth_headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.quote_api}/order",
                    params=payload,
                    headers=headers
                ) as response:
                    if response.status == 403:
                        msg = "DFlow order API access denied (403). Check DFLOW_API_KEY and production access."
                        print(msg)
                        return None, msg
                    if response.status != 200:
                        error_text = await response.text()
                        msg = f"DFlow order API returned {response.status}: {error_text[:300]}"
                        print(f"Order request failed: {msg}")
                        return None, msg

                    order_data = await response.json()
                    if not order_data.get("transaction"):
                        msg = "DFlow returned 200 but no transaction field. Market may be untradeable or API format changed."
                        print(msg)
                        return None, msg
                    print(f"Got order transaction for {market_id}")
                    return order_data, None

        except Exception as e:
            msg = f"Order request error: {e}"
            print(f"Error getting order transaction: {e}")
            return None, msg

    def _sign_transaction_local(self, transaction_bytes: bytes) -> bytes:
        """Sign a VersionedTransaction with local keypair (solders: message bytes + populate)."""
        raw = VersionedTransaction.from_bytes(transaction_bytes)
        msg_bytes = to_bytes_versioned(raw.message)
        signature = self.keypair.sign_message(msg_bytes)
        signed = VersionedTransaction.populate(raw.message, [signature])
        return bytes(signed)

    async def _sign_transaction_turnkey(self, unsigned_tx_b64: str) -> bytes:
        """Sign transaction via Turnkey API (X-Stamp auth), poll for completion, return signed tx bytes.
        Turnkey expects unsignedTransaction as hex; DFlow gives base64, so we convert.
        """
        tx_bytes = base64.b64decode(unsigned_tx_b64)
        unsigned_tx_hex = tx_bytes.hex()
        body = {
            "organizationId": self.turnkey_org_id,
            "parameters": {
                "signWith": self.turnkey_sign_with,
                "type": "TRANSACTION_TYPE_SOLANA",
                "unsignedTransaction": unsigned_tx_hex,
            },
            "timestampMs": str(int(time.time() * 1000)),
            "type": "ACTIVITY_TYPE_SIGN_TRANSACTION_V2",
        }
        # Canonical JSON so signature matches server expectation (key order matters for verification)
        body_str = json.dumps(body, sort_keys=True)
        stamp = _turnkey_stamp(
            body_str,
            self.turnkey_api_public_key,
            self.turnkey_api_private_key,
        )
        url = f"{self.turnkey_base.rstrip('/')}/public/v1/submit/sign_transaction"
        headers = {"Content-Type": "application/json", "X-Stamp": stamp}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=body_str, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    if "Could not find any resource to sign with" in text or resp.status == 404:
                        raise RuntimeError(
                            "Turnkey could not find the signer. TURNKEY_SIGN_WITH must be the UUID of the key "
                            "in Turnkey, not your Solana wallet address. In the Turnkey dashboard: go to "
                            "Private Keys → click your Solana key → copy the 'Private Key ID' (looks like "
                            "a1b2c3d4-e5f6-7890-abcd-ef1234567890). Or: Wallets → your wallet → Accounts → "
                            "copy the 'Account ID' for the Solana account. Paste that UUID into .env as "
                            "TURNKEY_SIGN_WITH= with no quotes or spaces. Case-sensitive."
                        )
                    raise RuntimeError(f"Turnkey sign_transaction failed: {resp.status} {text}")
                data = await resp.json()

        act = data.get("activity") or {}
        activity_id = act.get("id")
        status = act.get("status", "")
        if not activity_id:
            raise RuntimeError("Turnkey response missing activity id")

        # Poll get_activity until terminal status
        get_url = f"{self.turnkey_base.rstrip('/')}/public/v1/query/get_activity"
        for _ in range(30):
            if status in ("ACTIVITY_STATUS_COMPLETED", "ACTIVITY_STATUS_FAILED", "ACTIVITY_STATUS_REJECTED"):
                break
            await asyncio.sleep(1.0)
            poll_body = {
                "activityId": activity_id,
                "organizationId": self.turnkey_org_id,
                "timestampMs": str(int(time.time() * 1000)),
            }
            poll_str = json.dumps(poll_body, sort_keys=True)
            poll_stamp = _turnkey_stamp(
                poll_str,
                self.turnkey_api_public_key,
                self.turnkey_api_private_key,
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    get_url, data=poll_str, headers={"Content-Type": "application/json", "X-Stamp": poll_stamp}
                ) as r:
                    if r.status != 200:
                        raise RuntimeError(f"Turnkey get_activity failed: {r.status}")
                    out = await r.json()
            act = out.get("activity") or {}
            status = act.get("status", "")

        if status != "ACTIVITY_STATUS_COMPLETED":
            raise RuntimeError(f"Turnkey signing did not complete: status={status}")

        res = act.get("result") or {}
        result = res.get("signTransactionResult") or res.get("signTransactionResultV2") or res
        if isinstance(result, dict):
            signed_b64 = result.get("signedTransaction") or result.get("signedTransactionBytes")
        else:
            signed_b64 = getattr(result, "signedTransaction", None) or getattr(result, "signedTransactionBytes", None)
        if not signed_b64:
            raise RuntimeError("Turnkey response missing signedTransaction")
        s = signed_b64.strip()
        if all(c in "0123456789abcdefABCDEF" for c in s) and len(s) % 2 == 0:
            return bytes.fromhex(s)
        return base64.b64decode(s)

    async def get_order_status(self, tx_signature: str) -> Optional[Dict[str, Any]]:
        """Monitor order status for async prediction market trades"""
        try:
            headers = self._get_auth_headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.quote_api}/order-status",
                    params={"signature": tx_signature},
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Order status request failed: {response.status} - {error_text}")
                        return None

                    status_data = await response.json()
                    print(f"Order status for {tx_signature}: {status_data}")
                    return status_data

        except Exception as e:
            print(f"Error getting order status: {e}")
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

            # PRODUCTION MODE: Use DFlow production API
            # Step 1: Get order transaction from DFlow
            order_data, order_error = await self.get_order_transaction(
                trade_req.market_id,
                trade_req.side,
                trade_req.size
            )

            if not order_data:
                return {
                    "success": False,
                    "error": order_error or "DFlow order API did not return a transaction.",
                    "venue": "dflow",
                }

            # Step 2: Decode and sign the transaction from DFlow
            transaction_b64 = order_data.get("transaction")
            if not transaction_b64:
                return {
                    "success": False,
                    "error": "No transaction data in order response",
                    "venue": "dflow"
                }

            # Step 3: Sign transaction (Turnkey API or local keypair)
            if self._use_turnkey:
                signed_bytes = await self._sign_transaction_turnkey(transaction_b64)
            else:
                transaction_bytes = base64.b64decode(transaction_b64)
                signed_bytes = self._sign_transaction_local(transaction_bytes)

            transaction = VersionedTransaction.from_bytes(signed_bytes)

            # Step 4: Submit transaction to Solana
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
                tx_signature = str(result.value)
                print(f"Transaction submitted: {tx_signature}")

                # Step 5: Monitor order status (async monitoring)
                # For now, return immediately with the tx signature
                # In production, you might want to poll /order-status endpoint

                return {
                    "success": True,
                    "tx_hash": tx_signature,
                    "venue": "dflow",
                    "market_id": trade_req.market_id,
                    "side": trade_req.side,
                    "size": trade_req.size,
                    "price": order_data.get("estimatedPrice", 0.5),  # Use estimated price from order
                    "expected_tokens": order_data.get("estimatedTokens", trade_req.size),
                    "timestamp": int(time.time()),
                    "test_mode": False,
                    "note": f"Real DFlow transaction submitted - monitor at /order-status?signature={tx_signature}"
                }
            else:
                return {
                    "success": False,
                    "error": "Transaction submission to Solana failed",
                    "venue": "dflow"
                }

        except Exception as e:
            err_msg = str(e)
            print(f"Error executing DFlow trade: {e}")
            if self._use_turnkey and ("signature" in err_msg.lower() and "verification" in err_msg.lower() or "SignatureFailure" in err_msg):
                return {
                    "success": False,
                    "error": (
                        "Transaction failed signature verification. With Turnkey, SOLANA_WALLET_ADDRESS must be "
                        "the exact Solana address (base58) of the key you use in Turnkey. In the Turnkey dashboard, "
                        "open the Private Key (or Wallet Account) you use for TURNKEY_SIGN_WITH and copy its "
                        "Solana address — set that as SOLANA_WALLET_ADDRESS in .env. They must match."
                    ),
                    "venue": "dflow",
                }
            if "insufficient lamports" in err_msg.lower() or ("insufficient" in err_msg.lower() and "need" in err_msg.lower()):
                return {
                    "success": False,
                    "error": (
                        "Insufficient SOL: your wallet doesn't have enough for the trade + fees + rent. "
                        "Send at least ~0.005 SOL to your wallet and try again."
                    ),
                    "venue": "dflow",
                }
            return {
                "success": False,
                "error": err_msg,
                "venue": "dflow"
            }

    async def get_wallet_balance(self) -> Dict[str, Any]:
        """Get SOL and token balances for the wallet. Always returns JSON-serializable dict."""
        wallet_str = str(self.wallet_pubkey)
        try:
            balance_result = await self.client.get_balance(self.wallet_pubkey)
            # Handle both attribute and dict-style response (solana-py uses .value)
            lamports = getattr(balance_result, "value", None)
            if lamports is None and isinstance(balance_result, dict):
                lamports = balance_result.get("value", 0)
            lamports = lamports if lamports is not None else 0
            sol_balance = float(lamports) / 1_000_000_000
            return {
                "sol_balance": round(sol_balance, 9),
                "wallet": wallet_str,
            }
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return {
                "sol_balance": 0.0,
                "wallet": wallet_str,
                "error": str(e),
            }

    async def get_market_info(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific market (for outcome mints)."""
        try:
            headers = self._get_auth_headers()
            async with aiohttp.ClientSession() as session:
                # Try standard metadata API path first, then legacy path
                for path in (f"/api/v1/market/{market_id}", f"/markets/{market_id}"):
                    async with session.get(f"{self.markets_api}{path}", headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                return None
        except Exception as e:
            print(f"Error getting market info: {e}")
            return None