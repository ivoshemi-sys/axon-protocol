import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import get_db
from core.verifier import verify_output
from config import PROTOCOL_VERSION

router = APIRouter(tags=["verify"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _response(data):
    return {"success": True, "data": data, "timestamp": _now(), "protocol_version": PROTOCOL_VERSION}


def _error(msg: str, code: str, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": msg, "code": code, "timestamp": _now()},
    )


class VerifyRequest:
    pass


from pydantic import BaseModel


class VerifyInput(BaseModel):
    auction_id: str
    agent_id: str
    output: str


@router.post("/verify")
async def verify(input: VerifyInput):
    result = await verify_output(input.auction_id, input.output, input.agent_id)
    return _response(result)


@router.get("/verify/{auction_id}")
async def get_verification(auction_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM verifications WHERE auction_id = ? ORDER BY verified_at DESC LIMIT 1",
        (auction_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return _error("No verification found for this auction", "VERIFICATION_NOT_FOUND", 404)
    data = dict(row)
    if data.get("details"):
        data["details"] = json.loads(data["details"])
    return _response(data)
