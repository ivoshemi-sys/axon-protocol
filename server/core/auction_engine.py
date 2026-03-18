import asyncio
import json
import uuid
from datetime import datetime, timezone

from database import get_db
from config import STAKE_PERCENTAGE, COMMISSION_RATE


def calculate_auction_duration(max_budget: float) -> int:
    if max_budget < 0.10:
        return 2
    elif max_budget < 10.0:
        return 5
    elif max_budget < 1000.0:
        return 15
    else:
        return 60


def calculate_commission(amount: float) -> float:
    if amount < 1.0:
        return amount * 0.03
    elif amount <= 100.0:
        return amount * 0.05
    else:
        return amount * 0.02


async def process_bid(auction_id: str, bidder_id: str, bidder_name: str, amount: float) -> dict:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    async with db.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)) as cursor:
        auction = await cursor.fetchone()

    if not auction:
        return {"accepted": False, "reason": "Auction not found"}

    if auction["status"] != "open":
        return {"accepted": False, "reason": f"Auction is not open (status: {auction['status']})"}

    if amount >= auction["max_budget"]:
        return {"accepted": False, "reason": f"Bid {amount} must be less than max_budget {auction['max_budget']}"}

    if auction["winning_bid"] is not None and amount >= auction["winning_bid"]:
        return {
            "accepted": False,
            "reason": f"Bid {amount} must be lower than current best {auction['winning_bid']} (inverse auction)",
        }

    stake_amount = amount * STAKE_PERCENTAGE

    bid_id = f"axon_bid_{uuid.uuid4().hex[:12]}"
    await db.execute(
        """INSERT INTO bids (id, auction_id, bidder_id, bidder_name, amount, stake_amount, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (bid_id, auction_id, bidder_id, bidder_name, amount, stake_amount, "active", now),
    )

    if auction["winner_id"]:
        await db.execute(
            "UPDATE bids SET status = 'refunded' WHERE auction_id = ? AND bidder_id = ? AND status = 'active' AND id != ?",
            (auction_id, auction["winner_id"], bid_id),
        )

    await db.execute(
        "UPDATE auctions SET winner_id = ?, winning_bid = ? WHERE id = ?",
        (bidder_id, amount, auction_id),
    )
    await db.commit()

    return {
        "accepted": True,
        "bid_id": bid_id,
        "current_winner": bidder_id,
        "current_best": amount,
        "stake_amount": stake_amount,
    }


async def close_auction(auction_id: str) -> dict:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    async with db.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)) as cursor:
        auction = await cursor.fetchone()

    if not auction or auction["status"] != "open":
        return {"success": False, "reason": "Auction not open or not found"}

    await db.execute(
        "UPDATE auctions SET status = 'closed', closed_at = ? WHERE id = ?",
        (now, auction_id),
    )

    winner_id = auction["winner_id"]
    winning_bid = auction["winning_bid"]

    if winner_id and winning_bid is not None:
        await db.execute(
            "UPDATE bids SET status = 'winner' WHERE auction_id = ? AND bidder_id = ? AND status = 'active'",
            (auction_id, winner_id),
        )

        commission = calculate_commission(winning_bid)
        escrow_id = f"axon_escrow_{uuid.uuid4().hex[:12]}"
        await db.execute(
            """INSERT INTO escrows (id, auction_id, payer_id, payee_id, amount, commission, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                escrow_id,
                auction_id,
                auction["requester_id"],
                winner_id,
                winning_bid,
                commission,
                "held",
                now,
            ),
        )

        ledger_id = f"axon_ledger_{uuid.uuid4().hex[:12]}"
        await db.execute(
            """INSERT INTO ledger (id, transaction_type, from_agent, to_agent, amount, currency, auction_id, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ledger_id,
                "stake",
                winner_id,
                "axon_protocol",
                winning_bid * STAKE_PERCENTAGE,
                "USDC",
                auction_id,
                f"Stake held for auction {auction_id}",
                now,
            ),
        )

        await db.commit()

        from core.openclaw import openclaw_client
        await openclaw_client.broadcast(
            "auction_closed",
            {
                "auction_id": auction_id,
                "winner_id": winner_id,
                "winning_bid": winning_bid,
                "escrow_id": escrow_id,
            },
        )

        return {
            "success": True,
            "auction_id": auction_id,
            "winner_id": winner_id,
            "winning_bid": winning_bid,
            "escrow_id": escrow_id,
        }
    else:
        await db.commit()
        await close_auction_no_bids(auction_id)
        return {"success": True, "auction_id": auction_id, "winner_id": None, "reason": "No bids received"}


async def close_auction_no_bids(auction_id: str):
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE auctions SET status = 'cancelled', closed_at = ? WHERE id = ?",
        (now, auction_id),
    )
    await db.commit()


async def run_auction_timer(auction_id: str, duration_seconds: int):
    await asyncio.sleep(duration_seconds)
    db = await get_db()
    async with db.execute("SELECT status FROM auctions WHERE id = ?", (auction_id,)) as cursor:
        row = await cursor.fetchone()
    if row and row["status"] == "open":
        await close_auction(auction_id)
