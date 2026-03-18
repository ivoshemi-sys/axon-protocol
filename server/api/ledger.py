from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import get_db
from config import PROTOCOL_VERSION, SIMULATED_YIELD_APY

router = APIRouter(tags=["ledger"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _response(data):
    return {"success": True, "data": data, "timestamp": _now(), "protocol_version": PROTOCOL_VERSION}


def _error(msg: str, code: str, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": msg, "code": code, "timestamp": _now()},
    )


@router.get("/ledger")
async def get_ledger(page: int = 1, page_size: int = 50):
    db = await get_db()
    offset = (page - 1) * page_size
    async with db.execute(
        "SELECT * FROM ledger ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    ) as cursor:
        rows = await cursor.fetchall()
    async with db.execute("SELECT COUNT(*) as total FROM ledger") as cursor:
        total_row = await cursor.fetchone()
    total = total_row["total"] if total_row else 0
    return _response(
        {
            "entries": [dict(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )


@router.get("/ledger/stats")
async def get_stats():
    db = await get_db()

    async with db.execute("SELECT COUNT(*) as total FROM ledger") as cursor:
        total_tx = (await cursor.fetchone())["total"]

    async with db.execute(
        "SELECT SUM(amount) as total FROM ledger WHERE transaction_type = 'payment'"
    ) as cursor:
        total_volume_row = await cursor.fetchone()
    total_volume = total_volume_row["total"] or 0.0

    async with db.execute(
        "SELECT SUM(amount) as total FROM protocol_revenue WHERE source = 'commission'"
    ) as cursor:
        commissions_row = await cursor.fetchone()
    total_commissions = commissions_row["total"] or 0.0

    async with db.execute(
        "SELECT SUM(stake_amount) as total FROM bids WHERE status = 'active'"
    ) as cursor:
        active_stakes_row = await cursor.fetchone()
    active_stakes = active_stakes_row["total"] or 0.0

    simulated_yield = active_stakes * SIMULATED_YIELD_APY / 365

    async with db.execute(
        "SELECT SUM(amount) as total FROM protocol_revenue WHERE source = 'yield'"
    ) as cursor:
        yield_row = await cursor.fetchone()
    total_yield = (yield_row["total"] or 0.0) + simulated_yield

    return _response(
        {
            "total_transactions": total_tx,
            "total_volume_usdc": total_volume,
            "total_commissions_simulated": total_commissions,
            "simulated_yield_earned": total_yield,
            "active_stakes_usdc": active_stakes,
            "simulated_yield_apy": SIMULATED_YIELD_APY,
        }
    )


@router.get("/ledger/agent/{agent_id}")
async def get_agent_ledger(agent_id: str, page: int = 1, page_size: int = 50):
    db = await get_db()
    offset = (page - 1) * page_size
    async with db.execute(
        """SELECT * FROM ledger WHERE from_agent = ? OR to_agent = ?
           ORDER BY created_at DESC LIMIT ? OFFSET ?""",
        (agent_id, agent_id, page_size, offset),
    ) as cursor:
        rows = await cursor.fetchall()
    async with db.execute(
        "SELECT COUNT(*) as total FROM ledger WHERE from_agent = ? OR to_agent = ?",
        (agent_id, agent_id),
    ) as cursor:
        total_row = await cursor.fetchone()
    total = total_row["total"] if total_row else 0
    return _response(
        {
            "agent_id": agent_id,
            "entries": [dict(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )
