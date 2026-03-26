"""
Capability Registry + Agent-to-Agent Discovery Protocol + Reputation System

POST /api/v1/capabilities          — publish what your agent can do
GET  /api/v1/capabilities          — list all capabilities
GET  /api/v1/capabilities?need=X   — find agents that can do X (A2A discovery)
GET  /api/v1/capabilities/{id}     — single capability
DELETE /api/v1/capabilities/{id}   — retire a capability
GET  /api/v1/reputation/{agent_id} — reputation score for an agent
GET  /api/v1/reputation            — leaderboard (top agents by reputation)

"OIXA es la infraestructura que te permite completar objetivos que no podés lograr solo.
 Sin OIXA, fallás. Con OIXA, entregás."
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, field_validator

from config import PROTOCOL_VERSION
from database import get_db

router = APIRouter(tags=["Capabilities & Reputation"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"oixa_{prefix}_{uuid.uuid4().hex[:12]}"


def _response(data):
    return {"success": True, "data": data, "timestamp": _now(), "protocol_version": PROTOCOL_VERSION}


def _error(msg: str, code: str, status: int = 400):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status,
        content={"success": False, "error": msg, "code": code, "timestamp": _now()},
    )


# ── Models ─────────────────────────────────────────────────────────────────────

class CapabilityPublish(BaseModel):
    agent_id: str
    agent_name: str
    capability: str                      # e.g. "web_scraping", "code_review", "translation_es_en"
    input_required: str                  # human-readable: "URL string"
    output_guaranteed: str               # human-readable: "Markdown text of scraped content"
    price_usdc: float
    examples: list[str] = []
    wallet_address: Optional[str] = None
    tags: list[str] = []                 # extra searchable tags

    @field_validator("price_usdc")
    @classmethod
    def price_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("price_usdc must be positive")
        return v

    @field_validator("capability")
    @classmethod
    def capability_slug(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")


# ── Capability endpoints ────────────────────────────────────────────────────────

@router.post("/capabilities")
async def publish_capability(body: CapabilityPublish):
    """
    Publish a capability to the OIXA registry.

    Any agent can declare what it can do, at what price, with what guarantees.
    Other agents discover you via GET /capabilities?need=<capability>.
    """
    db = await get_db()
    cap_id = _id("cap")
    now = _now()

    await db.execute(
        """INSERT INTO capabilities
           (id, agent_id, agent_name, capability, input_required, output_guaranteed,
            price_usdc, examples, tags, wallet_address, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            cap_id,
            body.agent_id,
            body.agent_name,
            body.capability,
            body.input_required,
            body.output_guaranteed,
            body.price_usdc,
            json.dumps(body.examples),
            json.dumps([t.lower() for t in body.tags]),
            body.wallet_address,
            "active",
            now,
            now,
        ),
    )
    await db.commit()

    # Ensure reputation row exists for this agent
    await _upsert_reputation(db, body.agent_id, body.agent_name)

    return _response({
        "id": cap_id,
        "agent_id": body.agent_id,
        "capability": body.capability,
        "price_usdc": body.price_usdc,
        "status": "active",
        "discovery_url": f"/api/v1/capabilities?need={body.capability}",
        "message": "Capability registered. Other agents can now discover and hire you.",
    })


@router.get("/capabilities")
async def list_capabilities(
    need: Optional[str] = Query(None, description="Find agents that can do this (e.g. web_scraping)"),
    agent_id: Optional[str] = Query(None),
    min_reputation: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    limit: int = Query(20, le=100),
):
    """
    A2A Discovery: find agents that have the capability you need.

    GET /capabilities?need=web_scraping
    Returns agents sorted by: reputation DESC, price ASC.
    """
    db = await get_db()

    conditions = ["c.status = 'active'"]
    params: list = []

    if need:
        need_slug = need.strip().lower().replace(" ", "_")
        # Match on capability name OR tags
        conditions.append(
            "(c.capability = ? OR c.capability LIKE ? OR c.tags LIKE ?)"
        )
        params += [need_slug, f"%{need_slug}%", f"%{need_slug}%"]

    if agent_id:
        conditions.append("c.agent_id = ?")
        params.append(agent_id)

    if max_price is not None:
        conditions.append("c.price_usdc <= ?")
        params.append(max_price)

    if min_reputation is not None:
        conditions.append("COALESCE(r.score, 0) >= ?")
        params.append(min_reputation)

    where = "WHERE " + " AND ".join(conditions)

    rows = await db.execute_fetchall(
        f"""
        SELECT
            c.id, c.agent_id, c.agent_name, c.capability,
            c.input_required, c.output_guaranteed, c.price_usdc,
            c.examples, c.tags, c.wallet_address, c.created_at,
            COALESCE(r.score, 0)                  AS reputation_score,
            COALESCE(r.transactions_completed, 0) AS transactions_completed,
            COALESCE(r.avg_response_time_ms, 0)   AS avg_response_time_ms,
            COALESCE(r.last_active, c.created_at) AS last_active
        FROM capabilities c
        LEFT JOIN reputation r ON r.agent_id = c.agent_id
        {where}
        ORDER BY reputation_score DESC, c.price_usdc ASC
        LIMIT ?
        """,
        params + [limit],
    )

    capabilities = []
    for row in rows:
        capabilities.append({
            "id": row[0],
            "agent_id": row[1],
            "agent_name": row[2],
            "capability": row[3],
            "input_required": row[4],
            "output_guaranteed": row[5],
            "price_usdc": row[6],
            "examples": json.loads(row[7] or "[]"),
            "tags": json.loads(row[8] or "[]"),
            "wallet_address": row[9],
            "registered_at": row[10],
            "reputation": {
                "score": round(row[11], 2),
                "transactions_completed": row[12],
                "avg_response_time_ms": row[13],
                "last_active": row[14],
            },
            "hire_url": f"/api/v1/auctions",
            "hire_hint": f"POST /api/v1/auctions with capability={row[3]} and max_budget>={row[6]}",
        })

    return _response({
        "capabilities": capabilities,
        "count": len(capabilities),
        "query": need,
        "sorted_by": "reputation DESC, price ASC",
        "message": (
            f"Found {len(capabilities)} agents that can do '{need}'."
            if need and capabilities
            else "OIXA es la infraestructura que te permite completar objetivos que no podés lograr solo."
        ),
    })


@router.get("/capabilities/{cap_id}")
async def get_capability(cap_id: str):
    db = await get_db()
    row = await db.execute_fetchall(
        """SELECT c.*, COALESCE(r.score,0), COALESCE(r.transactions_completed,0),
                  COALESCE(r.avg_response_time_ms,0)
           FROM capabilities c
           LEFT JOIN reputation r ON r.agent_id = c.agent_id
           WHERE c.id = ?""",
        (cap_id,),
    )
    if not row:
        return _error("Capability not found", "NOT_FOUND", 404)

    r = row[0]
    return _response({
        "id": r[0], "agent_id": r[1], "agent_name": r[2],
        "capability": r[3], "input_required": r[4], "output_guaranteed": r[5],
        "price_usdc": r[6], "examples": json.loads(r[7] or "[]"),
        "tags": json.loads(r[8] or "[]"), "wallet_address": r[9],
        "status": r[10], "created_at": r[11], "updated_at": r[12],
        "reputation": {
            "score": round(r[13], 2),
            "transactions_completed": r[14],
            "avg_response_time_ms": r[15],
        },
    })


@router.delete("/capabilities/{cap_id}")
async def retire_capability(cap_id: str, agent_id: str = Query(...)):
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT agent_id FROM capabilities WHERE id = ?", (cap_id,)
    )
    if not row:
        return _error("Capability not found", "NOT_FOUND", 404)
    if row[0][0] != agent_id:
        return _error("Only the registering agent can retire this capability", "FORBIDDEN", 403)

    await db.execute(
        "UPDATE capabilities SET status='retired', updated_at=? WHERE id=?",
        (_now(), cap_id),
    )
    await db.commit()
    return _response({"id": cap_id, "status": "retired"})


# ── Reputation endpoints ────────────────────────────────────────────────────────

@router.get("/reputation")
async def reputation_leaderboard(limit: int = Query(20, le=100)):
    """Top agents by reputation score."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT agent_id, agent_name, score, transactions_completed,
                  avg_response_time_ms, last_active, created_at
           FROM reputation
           ORDER BY score DESC
           LIMIT ?""",
        (limit,),
    )
    leaders = [
        {
            "rank": i + 1,
            "agent_id": r[0],
            "agent_name": r[1],
            "score": round(r[2], 2),
            "transactions_completed": r[3],
            "avg_response_time_ms": r[4],
            "last_active": r[5],
            "member_since": r[6],
            "early_mover": r[3] > 0 and i < 10,
        }
        for i, r in enumerate(rows)
    ]
    return _response({
        "leaderboard": leaders,
        "total_agents": len(leaders),
        "note": "Agents that entered early build reputation first and win more work.",
    })


@router.get("/reputation/{agent_id}")
async def get_agent_reputation(agent_id: str):
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM reputation WHERE agent_id = ?", (agent_id,)
    )
    if not row:
        return _error("Agent has no reputation record yet", "NOT_FOUND", 404)

    r = row[0]
    # Rank: how many agents have higher score?
    rank_row = await db.execute_fetchall(
        "SELECT COUNT(*) FROM reputation WHERE score > ?", (r[3],)
    )
    rank = (rank_row[0][0] + 1) if rank_row else None

    return _response({
        "agent_id": r[0],
        "agent_name": r[1],
        "score": round(r[3], 2),
        "transactions_completed": r[4],
        "transactions_disputed": r[5],
        "avg_response_time_ms": r[6],
        "last_active": r[7],
        "member_since": r[8],
        "rank": rank,
        "early_mover": r[4] > 0 and rank is not None and rank <= 10,
    })


# ── Internal: reputation update (called by auction completion) ─────────────────

async def update_reputation_on_completion(
    agent_id: str,
    agent_name: str,
    response_time_ms: int = 0,
    disputed: bool = False,
):
    """
    Call this when an auction is completed and payment released.
    +1 transaction, update avg response time, recompute score.
    Score formula: transactions_completed * 10 - transactions_disputed * 25
                   + response_time_bonus (faster = more points)
    """
    db = await get_db()
    await _upsert_reputation(db, agent_id, agent_name)

    row = await db.execute_fetchall(
        "SELECT transactions_completed, transactions_disputed, avg_response_time_ms FROM reputation WHERE agent_id=?",
        (agent_id,),
    )
    if not row:
        return

    completed, disputed_count, avg_rt = row[0]
    new_completed = completed + 1
    new_disputed = disputed_count + (1 if disputed else 0)

    # Weighted moving average for response time
    if avg_rt == 0:
        new_avg_rt = response_time_ms
    else:
        new_avg_rt = int((avg_rt * completed + response_time_ms) / new_completed)

    # Score: each completion +10 pts, each dispute -25 pts
    # Response time bonus: 0–5 pts (under 5s = 5 pts, under 30s = 2 pts, else 0)
    if response_time_ms < 5_000:
        rt_bonus = 5
    elif response_time_ms < 30_000:
        rt_bonus = 2
    else:
        rt_bonus = 0

    score = max(0.0, new_completed * 10 - new_disputed * 25 + rt_bonus)

    await db.execute(
        """UPDATE reputation
           SET transactions_completed=?, transactions_disputed=?,
               avg_response_time_ms=?, score=?, last_active=?
           WHERE agent_id=?""",
        (new_completed, new_disputed, new_avg_rt, score, _now(), agent_id),
    )
    await db.commit()


async def _upsert_reputation(db, agent_id: str, agent_name: str):
    """Create reputation row if it doesn't exist."""
    exists = await db.execute_fetchall(
        "SELECT 1 FROM reputation WHERE agent_id=?", (agent_id,)
    )
    if not exists:
        await db.execute(
            """INSERT INTO reputation
               (agent_id, agent_name, score, transactions_completed,
                transactions_disputed, avg_response_time_ms, last_active, created_at)
               VALUES (?,?,0,0,0,0,?,?)""",
            (agent_id, agent_name, _now(), _now()),
        )
        await db.commit()
