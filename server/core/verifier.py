import hashlib
import json
import uuid
from datetime import datetime, timezone

from database import get_db
from config import COMMISSION_RATE


def calculate_commission(amount: float) -> float:
    if amount < 1.0:
        return amount * 0.03
    elif amount <= 100.0:
        return amount * 0.05
    else:
        return amount * 0.02


async def verify_output(auction_id: str, output: str, agent_id: str) -> dict:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    output_hash = hashlib.sha256(output.encode()).hexdigest()
    details = {}
    passed = True
    fail_reason = None

    if not output or not output.strip():
        passed = False
        fail_reason = "Output is empty"

    if passed:
        async with db.execute(
            "SELECT * FROM auctions WHERE id = ?", (auction_id,)
        ) as cursor:
            auction = await cursor.fetchone()

        if not auction:
            passed = False
            fail_reason = "Auction not found"
        elif auction["winner_id"] != agent_id:
            passed = False
            fail_reason = f"Agent {agent_id} is not the winner of this auction"
        elif auction["status"] not in ("closed", "completed"):
            passed = False
            fail_reason = f"Auction status is '{auction['status']}', expected 'closed'"

    if passed and auction:
        details = {
            "output_length": len(output),
            "auction_id": auction_id,
            "winning_agent": agent_id,
            "verified_at": now,
        }

        async with db.execute(
            "SELECT * FROM escrows WHERE auction_id = ? AND status = 'held'",
            (auction_id,),
        ) as cursor:
            escrow = await cursor.fetchone()

        if escrow:
            commission = escrow["commission"]
            net_payment = escrow["amount"] - commission

            ledger_payment_id = f"axon_ledger_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """INSERT INTO ledger (id, transaction_type, from_agent, to_agent, amount, currency, auction_id, description, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ledger_payment_id,
                    "payment",
                    escrow["payer_id"],
                    escrow["payee_id"],
                    net_payment,
                    "USDC",
                    auction_id,
                    f"Payment for auction {auction_id} after verification",
                    now,
                ),
            )

            ledger_commission_id = f"axon_ledger_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """INSERT INTO ledger (id, transaction_type, from_agent, to_agent, amount, currency, auction_id, description, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ledger_commission_id,
                    "commission",
                    escrow["payee_id"],
                    "axon_protocol",
                    commission,
                    "USDC",
                    auction_id,
                    f"AXON Protocol commission (5%) for auction {auction_id}",
                    now,
                ),
            )

            revenue_id = f"axon_ledger_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """INSERT INTO protocol_revenue (id, source, amount, currency, auction_id, simulated, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (revenue_id, "commission", commission, "USDC", auction_id, True, now),
            )

            await db.execute(
                "UPDATE escrows SET status = 'released', released_at = ? WHERE id = ?",
                (now, escrow["id"]),
            )
            details["escrow_released"] = True
            details["net_payment"] = net_payment
            details["commission"] = commission

        await db.execute(
            "UPDATE auctions SET status = 'completed', completed_at = ? WHERE id = ?",
            (now, auction_id),
        )

    verify_id = f"axon_verify_{uuid.uuid4().hex[:12]}"
    await db.execute(
        """INSERT INTO verifications (id, auction_id, output_hash, verified_at, passed, details)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (verify_id, auction_id, output_hash, now, passed, json.dumps(details)),
    )
    if not passed:
        details["fail_reason"] = fail_reason

    await db.commit()

    return {"passed": passed, "output_hash": output_hash, "details": details}
