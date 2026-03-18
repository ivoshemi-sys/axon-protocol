import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from database import get_db

logger = logging.getLogger("axon.verifier")


def calculate_commission(amount: float) -> float:
    if amount < 1.0:
        return amount * 0.03
    elif amount <= 100.0:
        return amount * 0.05
    else:
        return amount * 0.02


async def verify_output(auction_id: str, output: str, agent_id: str) -> dict:
    db  = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    output_hash = hashlib.sha256(output.encode()).hexdigest()
    details     = {}
    passed      = True
    fail_reason = None
    auction     = None

    # ── Validation ────────────────────────────────────────────────────────────
    if not output or not output.strip():
        passed      = False
        fail_reason = "Output is empty"

    if passed:
        async with db.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)) as cur:
            auction = await cur.fetchone()

        if not auction:
            passed      = False
            fail_reason = "Auction not found"
        elif auction["winner_id"] != agent_id:
            passed      = False
            fail_reason = f"Agent {agent_id} is not the winner (winner: {auction['winner_id']})"
        elif auction["status"] not in ("closed", "completed"):
            passed      = False
            fail_reason = f"Auction status is '{auction['status']}', expected 'closed'"

    # ── On success: release escrow ────────────────────────────────────────────
    if passed and auction:
        details = {
            "output_length": len(output),
            "auction_id":    auction_id,
            "winning_agent": agent_id,
            "verified_at":   now,
        }

        async with db.execute(
            "SELECT * FROM escrows WHERE auction_id = ? AND status = 'held'",
            (auction_id,),
        ) as cur:
            escrow = await cur.fetchone()

        if escrow:
            commission   = escrow["commission"]
            net_payment  = escrow["amount"] - commission
            was_simulated = escrow.get("simulated", True)

            # ── Try on-chain release first ────────────────────────────────────
            chain_result = {"simulated": True}
            try:
                from blockchain.escrow_client import escrow_client
                if escrow_client.enabled and not was_simulated:
                    chain_result = await escrow_client.release_escrow(escrow["id"])
                    logger.info(
                        f"On-chain escrow released | {escrow['id']} | "
                        f"tx={chain_result.get('tx_hash', 'n/a')[:20]}..."
                    )
            except ImportError:
                pass
            except Exception as e:
                logger.error(f"On-chain release failed: {e} — recording as DB-only")

            on_chain = not chain_result.get("simulated", True)

            # ── DB updates ────────────────────────────────────────────────────
            release_tx = chain_result.get("tx_hash") if on_chain else None
            await db.execute(
                "UPDATE escrows SET status = 'released', released_at = ?, tx_hash = ? WHERE id = ?",
                (now, release_tx, escrow["id"]),
            )

            # Payment ledger entry
            ledger_payment_id = f"axon_ledger_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """INSERT INTO ledger
                   (id, transaction_type, from_agent, to_agent, amount, currency, auction_id, description, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ledger_payment_id, "payment",
                    escrow["payer_id"], escrow["payee_id"],
                    net_payment, "USDC", auction_id,
                    f"Payment for auction {auction_id} | on_chain={on_chain}",
                    now,
                ),
            )

            # Commission ledger entry
            ledger_commission_id = f"axon_ledger_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """INSERT INTO ledger
                   (id, transaction_type, from_agent, to_agent, amount, currency, auction_id, description, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ledger_commission_id, "commission",
                    escrow["payee_id"], "axon_protocol",
                    commission, "USDC", auction_id,
                    f"AXON Protocol commission for auction {auction_id}",
                    now,
                ),
            )

            # Protocol revenue record
            revenue_id = f"axon_revenue_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """INSERT INTO protocol_revenue
                   (id, source, amount, currency, auction_id, simulated, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (revenue_id, "commission", commission, "USDC", auction_id, not on_chain, now),
            )

            await db.execute(
                "UPDATE auctions SET status = 'completed', completed_at = ? WHERE id = ?",
                (now, auction_id),
            )

            details["escrow_released"]   = True
            details["net_payment"]       = net_payment
            details["commission"]        = commission
            details["on_chain"]          = on_chain
            details["release_tx_hash"]   = release_tx

            logger.info(
                f"Verification passed | auction={auction_id} | agent={agent_id} | "
                f"net={net_payment:.4f} USDC | commission={commission:.4f} | on_chain={on_chain}"
            )

    else:
        if not passed:
            details["fail_reason"] = fail_reason
            logger.warning(f"Verification failed | auction={auction_id} | reason={fail_reason}")

    # ── Save verification record ──────────────────────────────────────────────
    verify_id = f"axon_verify_{uuid.uuid4().hex[:12]}"
    await db.execute(
        """INSERT INTO verifications (id, auction_id, output_hash, verified_at, passed, details)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (verify_id, auction_id, output_hash, now, passed, json.dumps(details)),
    )
    await db.commit()

    return {"passed": passed, "output_hash": output_hash, "details": details}
