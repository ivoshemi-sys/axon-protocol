import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import get_db
from models.escrow import SimulatePayment
from core.auction_engine import calculate_commission
from config import PROTOCOL_VERSION

router = APIRouter(tags=["escrow"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _response(data):
    return {"success": True, "data": data, "timestamp": _now(), "protocol_version": PROTOCOL_VERSION}


def _error(msg: str, code: str, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": msg, "code": code, "timestamp": _now()},
    )


@router.get("/escrow/{auction_id}")
async def get_escrow(auction_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM escrows WHERE auction_id = ?", (auction_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return _error("Escrow not found for this auction", "ESCROW_NOT_FOUND", 404)
    data = {**dict(row), "simulated": True}
    return _response(data)


@router.post("/escrow/simulate")
async def simulate_payment(payment: SimulatePayment):
    db = await get_db()
    now = _now()
    commission = calculate_commission(payment.amount)
    escrow_id = f"axon_escrow_{uuid.uuid4().hex[:12]}"

    await db.execute(
        """INSERT INTO escrows (id, auction_id, payer_id, payee_id, amount, commission, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            escrow_id,
            payment.auction_id,
            payment.payer_id,
            payment.payee_id,
            payment.amount,
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
            "payment",
            payment.payer_id,
            payment.payee_id,
            payment.amount,
            "USDC",
            payment.auction_id,
            f"Simulated escrow payment for auction {payment.auction_id}",
            now,
        ),
    )

    await db.commit()

    return _response(
        {
            "id": escrow_id,
            "auction_id": payment.auction_id,
            "payer_id": payment.payer_id,
            "payee_id": payment.payee_id,
            "amount": payment.amount,
            "commission": commission,
            "status": "held",
            "simulated": True,
            "created_at": now,
        }
    )
