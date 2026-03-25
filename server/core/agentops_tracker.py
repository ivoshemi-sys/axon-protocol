"""
OIXA Protocol — AgentOps Server-Side Tracker

Tracks every significant protocol event in the AgentOps dashboard:
- Auction created / closed / cancelled
- Bid placed / won
- Output delivered & verified
- Escrow released / refunded
- Dispute opened / resolved
- Commission earned

Configured via AGENTOPS_API_KEY in .env. Degrades gracefully if not set.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("oixa.agentops")

# ── Lazy import — server works without agentops installed ─────────────────────
try:
    import agentops
    _AVAILABLE = True
except ImportError:
    agentops = None  # type: ignore
    _AVAILABLE = False

_initialized = False


def init(api_key: str) -> bool:
    """Initialize AgentOps. Called once at server startup."""
    global _initialized

    if not _AVAILABLE:
        logger.warning("[AgentOps] Package not installed — run: pip install agentops")
        return False

    if not api_key:
        logger.warning("[AgentOps] AGENTOPS_API_KEY not set — tracking disabled")
        return False

    try:
        agentops.init(
            api_key=api_key,
            tags=["oixa-protocol", "server", "marketplace"],
            auto_start_session=False,   # we manage sessions per agent interaction
        )
        _initialized = True
        logger.info("[AgentOps] Initialized — dashboard: https://app.agentops.ai")
        return True
    except Exception as e:
        logger.warning(f"[AgentOps] Init failed: {e}")
        return False


def _record(event_name: str, data: dict):
    """Record an ActionEvent to AgentOps. Fire-and-forget."""
    if not (_AVAILABLE and _initialized):
        return
    try:
        agentops.record(agentops.ActionEvent(
            action_type=f"oixa.{event_name}",
            params=data,
            returns={"status": "ok"},
        ))
    except Exception as e:
        logger.debug(f"[AgentOps] record failed: {e}")


def _record_error(event_name: str, error: str, data: dict):
    if not (_AVAILABLE and _initialized):
        return
    try:
        agentops.record(agentops.ErrorEvent(
            error_type=f"oixa.{event_name}",
            details=error,
            logs=json.dumps(data),
        ))
    except Exception as e:
        logger.debug(f"[AgentOps] error record failed: {e}")


# ── Public tracking functions (called from API handlers) ──────────────────────

def track_auction_created(auction_id: str, rfi: str, budget: float, requester: str, duration_s: int):
    _record("auction.created", {
        "auction_id":  auction_id,
        "rfi":         rfi[:200],
        "max_budget":  budget,
        "requester":   requester,
        "duration_s":  duration_s,
        "currency":    "USDC",
    })
    logger.debug(f"[AgentOps] auction.created {auction_id}")


def track_bid_placed(auction_id: str, bidder_id: str, bidder_name: str, amount: float, accepted: bool, is_winner: bool):
    _record("bid.placed", {
        "auction_id":  auction_id,
        "bidder_id":   bidder_id,
        "bidder_name": bidder_name,
        "amount_usdc": amount,
        "accepted":    accepted,
        "is_winner":   is_winner,
    })
    logger.debug(f"[AgentOps] bid.placed {bidder_id} → {auction_id} @ {amount} USDC (accepted={accepted})")


def track_auction_closed(auction_id: str, winner_id: Optional[str], winning_bid: Optional[float], bid_count: int):
    _record("auction.closed", {
        "auction_id":   auction_id,
        "winner_id":    winner_id,
        "winning_bid":  winning_bid,
        "bid_count":    bid_count,
        "currency":     "USDC",
    })
    logger.debug(f"[AgentOps] auction.closed {auction_id} → winner={winner_id} @ {winning_bid} USDC")


def track_delivery(auction_id: str, agent_id: str, passed: bool, output_hash: str, output_len: int):
    _record("delivery.verified", {
        "auction_id":  auction_id,
        "agent_id":    agent_id,
        "passed":      passed,
        "output_hash": output_hash[:16] + "...",
        "output_len":  output_len,
    })
    logger.debug(f"[AgentOps] delivery.verified {auction_id} passed={passed}")


def track_escrow_released(auction_id: str, payee_id: str, net_amount: float, commission: float):
    _record("escrow.released", {
        "auction_id":   auction_id,
        "payee_id":     payee_id,
        "net_usdc":     net_amount,
        "commission":   commission,
        "total":        net_amount + commission,
        "currency":     "USDC",
    })
    logger.debug(f"[AgentOps] escrow.released {auction_id} → {payee_id} net={net_amount} USDC")


def track_escrow_refunded(auction_id: str, payer_id: str, amount: float):
    _record("escrow.refunded", {
        "auction_id": auction_id,
        "payer_id":   payer_id,
        "amount":     amount,
        "currency":   "USDC",
    })
    logger.debug(f"[AgentOps] escrow.refunded {auction_id} → {payer_id} {amount} USDC")


def track_dispute_opened(dispute_id: str, auction_id: str, opened_by: str, reason: str, fee: float):
    _record("dispute.opened", {
        "dispute_id":  dispute_id,
        "auction_id":  auction_id,
        "opened_by":   opened_by,
        "reason":      reason[:200],
        "fee_usdc":    fee,
    })
    logger.debug(f"[AgentOps] dispute.opened {dispute_id}")


def track_dispute_resolved(dispute_id: str, verdict: str, confidence: float, arbiters: list, cost_usdc: float):
    _record("dispute.resolved", {
        "dispute_id":   dispute_id,
        "verdict":      verdict,
        "confidence":   confidence,
        "arbiters":     arbiters,
        "arbiter_cost": cost_usdc,
    })
    logger.debug(f"[AgentOps] dispute.resolved {dispute_id} → {verdict} (cost=${cost_usdc:.5f})")


def track_offer_registered(offer_id: str, agent_id: str, agent_name: str, capabilities: list, price: float):
    _record("offer.registered", {
        "offer_id":     offer_id,
        "agent_id":     agent_id,
        "agent_name":   agent_name,
        "capabilities": capabilities,
        "price_usdc":   price,
    })
    logger.debug(f"[AgentOps] offer.registered {agent_name} cap={capabilities}")


def track_commission(auction_id: str, amount: float, rate_pct: float):
    _record("commission.earned", {
        "auction_id": auction_id,
        "amount":     amount,
        "rate_pct":   rate_pct,
        "currency":   "USDC",
    })


def track_server_start(db_backend: str, blockchain: bool, version: str):
    _record("server.started", {
        "db_backend":   db_backend,
        "blockchain":   blockchain,
        "version":      version,
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"[AgentOps] server.started event sent")


def track_error(context: str, error: str, details: Optional[dict] = None):
    _record_error(context, error, details or {})
