"""
Multi-Arbiter System — OIXA Protocol

Dispute resolution via 2-of-3 voting between independent LLMs:
  - Claude (Anthropic)
  - GPT-4 (OpenAI)
  - Gemini (Google)

Requires at least 2 of 3 to agree. If only 1 LLM is available, falls back
to single-arbiter mode. If 0 are available, dispute stays open for manual review.

Configure in .env:
  ANTHROPIC_API_KEY=...
  OPENAI_API_KEY=...
  GEMINI_API_KEY=...
  MULTI_ARBITER_ENABLED=true   # set false to use legacy single-arbiter
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import (
    ANTHROPIC_API_KEY,
    ARBITER_MODEL,
    ARBITER_MAX_TOKENS,
    OPENAI_API_KEY,
    OPENAI_ARBITER_MODEL,
    GEMINI_API_KEY,
    GEMINI_ARBITER_MODEL,
    MULTI_ARBITER_ENABLED,
)

logger = logging.getLogger("oixa.multi_arbiter")

# Cost estimates (USD per 1M tokens)
_MODEL_COSTS = {
    "claude-opus-4-6":        {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6":      {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "gpt-4o":                 {"input": 5.0,   "output": 15.0},
    "gpt-4-turbo":            {"input": 10.0,  "output": 30.0},
    "gemini-1.5-pro":         {"input": 3.5,   "output": 10.5},
    "gemini-1.5-flash":       {"input": 0.075, "output": 0.3},
}

ARBITER_PROMPT = """\
You are an impartial arbiter for OIXA Protocol, an autonomous agent marketplace.
Your task: determine whether a delivered AI output satisfactorily fulfills the original task requirements.

## Original Task (RFI — Request for Intelligence)
{rfi_description}

## Maximum Budget
{max_budget} USDC

## Winning Bid
{winning_bid} USDC

## Delivered Output
{output}

## Dispute Reason (filed by requester)
{reason}

## Instructions
Evaluate:
1. Does the output directly address the RFI's core requirements?
2. Is the output substantive, accurate, and actionable — not empty, vague, or off-topic?
3. Is the requester's dispute reason valid given the actual output?

Rules:
- Minor imperfections or style issues → rule for the AGENT (agent_wins)
- Output clearly fails to address requirements → rule for the REQUESTER (requester_wins)
- Partial output that covers the main points → rule for the AGENT (agent_wins)
- Empty, copied-from-prompt, or completely wrong output → rule for the REQUESTER (requester_wins)

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{
  "verdict": "agent_wins" or "requester_wins",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 sentence explanation of your verdict",
  "output_quality_score": 0 to 10
}}
"""


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = _MODEL_COSTS.get(model, {"input": 5.0, "output": 15.0})
    return (input_tokens / 1_000_000 * costs["input"] +
            output_tokens / 1_000_000 * costs["output"])


def _parse_verdict(raw_text: str) -> Optional[dict]:
    """Parse LLM response. Returns None if unparseable."""
    try:
        clean = raw_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        verdict = data.get("verdict", "").lower()
        if verdict not in ("agent_wins", "requester_wins"):
            return None
        return data
    except Exception:
        return None


async def _call_claude(prompt: str) -> dict:
    """Call Claude arbiter. Returns {verdict_data, cost, model, error}."""
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not configured", "model": ARBITER_MODEL}
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        response = await asyncio.wait_for(
            client.messages.create(
                model=ARBITER_MODEL,
                max_tokens=ARBITER_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=60,
        )
        raw = response.content[0].text.strip()
        verdict_data = _parse_verdict(raw)
        cost = _estimate_cost(ARBITER_MODEL, response.usage.input_tokens, response.usage.output_tokens)
        if not verdict_data:
            return {"error": f"Unparseable response: {raw[:100]}", "model": ARBITER_MODEL, "cost": cost}
        return {"verdict_data": verdict_data, "model": ARBITER_MODEL, "cost": cost}
    except Exception as e:
        logger.warning(f"[MULTI_ARBITER] Claude error: {e}")
        return {"error": str(e), "model": ARBITER_MODEL, "cost": 0.0}


async def _call_openai(prompt: str) -> dict:
    """Call GPT-4 arbiter. Returns {verdict_data, cost, model, error}."""
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not configured", "model": OPENAI_ARBITER_MODEL}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_ARBITER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": ARBITER_MAX_TOKENS,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            cost = _estimate_cost(
                OPENAI_ARBITER_MODEL,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            verdict_data = _parse_verdict(raw)
            if not verdict_data:
                return {"error": f"Unparseable: {raw[:100]}", "model": OPENAI_ARBITER_MODEL, "cost": cost}
            return {"verdict_data": verdict_data, "model": OPENAI_ARBITER_MODEL, "cost": cost}
    except Exception as e:
        logger.warning(f"[MULTI_ARBITER] OpenAI error: {e}")
        return {"error": str(e), "model": OPENAI_ARBITER_MODEL, "cost": 0.0}


async def _call_gemini(prompt: str) -> dict:
    """Call Gemini arbiter. Returns {verdict_data, cost, model, error}."""
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured", "model": GEMINI_ARBITER_MODEL}
    try:
        import httpx
        # Use Gemini REST API
        model_id = GEMINI_ARBITER_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": ARBITER_MAX_TOKENS, "temperature": 0.0},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Gemini doesn't always return token counts in same format
            usage = data.get("usageMetadata", {})
            cost = _estimate_cost(
                model_id,
                usage.get("promptTokenCount", 0),
                usage.get("candidatesTokenCount", 0),
            )
            verdict_data = _parse_verdict(raw)
            if not verdict_data:
                return {"error": f"Unparseable: {raw[:100]}", "model": model_id, "cost": cost}
            return {"verdict_data": verdict_data, "model": model_id, "cost": cost}
    except Exception as e:
        logger.warning(f"[MULTI_ARBITER] Gemini error: {e}")
        return {"error": str(e), "model": GEMINI_ARBITER_MODEL, "cost": 0.0}


async def run_multi_arbiter(
    rfi_description: str,
    max_budget: float,
    winning_bid: float,
    output_text: str,
    dispute_reason: str,
) -> dict:
    """
    Run all 3 LLM arbiters in parallel. Apply 2-of-3 majority vote.

    Returns:
        {
            "verdict": "agent_wins" | "requester_wins" | None,
            "votes": [...],
            "majority": bool,
            "total_cost": float,
            "arbiter_count": int,
        }
    """
    prompt = ARBITER_PROMPT.format(
        rfi_description=rfi_description,
        max_budget=max_budget,
        winning_bid=winning_bid,
        output=output_text[:4000],
        reason=dispute_reason,
    )

    # Run all 3 in parallel
    results = await asyncio.gather(
        _call_claude(prompt),
        _call_openai(prompt),
        _call_gemini(prompt),
        return_exceptions=False,
    )

    claude_r, openai_r, gemini_r = results
    all_results = [
        {"arbiter": "claude", **claude_r},
        {"arbiter": "openai", **openai_r},
        {"arbiter": "gemini", **gemini_r},
    ]

    # Count valid verdicts
    valid_votes = [r for r in all_results if "verdict_data" in r]
    total_cost = sum(r.get("cost", 0.0) for r in all_results)

    logger.info(
        f"[MULTI_ARBITER] {len(valid_votes)}/3 arbiters responded. "
        f"Total cost: ${total_cost:.5f}"
    )

    if not valid_votes:
        logger.error("[MULTI_ARBITER] All arbiters failed — dispute left open for manual review")
        return {
            "verdict": None,
            "votes": all_results,
            "majority": False,
            "total_cost": total_cost,
            "arbiter_count": 0,
            "error": "All arbiters unavailable",
        }

    # Tally votes
    tally = {"agent_wins": 0, "requester_wins": 0}
    for r in valid_votes:
        v = r["verdict_data"]["verdict"]
        tally[v] = tally.get(v, 0) + 1

    # Determine winner (majority or plurality)
    agent_count = tally["agent_wins"]
    requester_count = tally["requester_wins"]

    # 2-of-3 majority
    if agent_count >= 2:
        final_verdict = "agent_wins"
        majority = True
    elif requester_count >= 2:
        final_verdict = "requester_wins"
        majority = True
    elif len(valid_votes) == 1:
        # Only 1 arbiter available — use it
        final_verdict = valid_votes[0]["verdict_data"]["verdict"]
        majority = False
    else:
        # Tie (1-1 with 2 arbiters): default to agent_wins (benefit of the doubt)
        final_verdict = "agent_wins"
        majority = False
        logger.warning("[MULTI_ARBITER] Tie vote — defaulting to agent_wins per protocol rules")

    # Build consensus verdict_data by aggregating
    avg_confidence = sum(
        r["verdict_data"].get("confidence", 0.5) for r in valid_votes
    ) / len(valid_votes)
    avg_quality = sum(
        r["verdict_data"].get("output_quality_score", 5) for r in valid_votes
    ) / len(valid_votes)

    # Collect reasonings
    reasonings = [
        f"[{r['arbiter'].upper()}] {r['verdict_data'].get('reasoning', '')}"
        for r in valid_votes
    ]

    consensus_verdict_data = {
        "verdict": final_verdict,
        "confidence": round(avg_confidence, 3),
        "reasoning": " | ".join(reasonings),
        "output_quality_score": round(avg_quality, 1),
        "vote_tally": tally,
        "arbiters_used": [r["arbiter"] for r in valid_votes],
        "majority_vote": majority,
    }

    logger.info(
        f"[MULTI_ARBITER] Final verdict: {final_verdict} | "
        f"votes={tally} | majority={majority} | cost=${total_cost:.5f}"
    )

    return {
        "verdict": final_verdict,
        "verdict_data": consensus_verdict_data,
        "votes": all_results,
        "majority": majority,
        "total_cost": total_cost,
        "arbiter_count": len(valid_votes),
    }


async def arbitrate_dispute(dispute_id: str) -> dict:
    """
    Main entry point — replaces single-LLM arbiter.
    Loads dispute context, runs multi-arbiter vote, applies verdict.
    """
    from database import get_db

    # Fall back to legacy single-arbiter if multi-arbiter is disabled
    if not MULTI_ARBITER_ENABLED:
        from core.arbiter import arbitrate_dispute as legacy_arbitrate
        return await legacy_arbitrate(dispute_id)

    # Check if at least one API key is available
    if not any([ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY]):
        logger.warning(
            f"[MULTI_ARBITER] No API keys configured — dispute {dispute_id} left in 'open' status. "
            "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY in .env"
        )
        return {"skipped": True, "reason": "No arbiter API keys configured"}

    db  = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Load dispute
    async with db.execute("SELECT * FROM disputes WHERE id = ?", (dispute_id,)) as cur:
        dispute = await cur.fetchone()
    if not dispute:
        raise ValueError(f"Dispute {dispute_id} not found")
    if dispute["status"] != "open":
        logger.info(f"[MULTI_ARBITER] Dispute {dispute_id} already status={dispute['status']}, skipping")
        return {"skipped": True, "reason": "already resolved"}

    auction_id = dispute["auction_id"]

    # Load auction
    async with db.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)) as cur:
        auction = await cur.fetchone()
    if not auction:
        raise ValueError(f"Auction {auction_id} not found")

    # Load delivered output
    async with db.execute(
        "SELECT * FROM verifications WHERE auction_id = ? AND passed = 1 ORDER BY verified_at DESC LIMIT 1",
        (auction_id,),
    ) as cur:
        verification = await cur.fetchone()

    delivered_output = "[Output not found in verification records]"
    if verification and verification.get("details"):
        try:
            details = json.loads(verification["details"])
            delivered_output = details.get("output_text", delivered_output)
        except Exception:
            pass

    # Mark as resolving
    await db.execute("UPDATE disputes SET status = 'resolving' WHERE id = ?", (dispute_id,))
    await db.commit()

    logger.info(f"[MULTI_ARBITER] Running 3-LLM vote for dispute {dispute_id}...")

    # Run multi-arbiter
    result = await run_multi_arbiter(
        rfi_description=auction["rfi_description"],
        max_budget=float(auction["max_budget"]),
        winning_bid=float(auction.get("winning_bid") or auction["max_budget"]),
        output_text=delivered_output,
        dispute_reason=dispute["reason"],
    )

    if result.get("verdict") is None:
        # All arbiters failed — revert to open for manual review
        await db.execute("UPDATE disputes SET status = 'open' WHERE id = ?", (dispute_id,))
        await db.commit()
        return {"skipped": True, "reason": result.get("error", "All arbiters failed")}

    verdict = result["verdict"]
    verdict_data = result["verdict_data"]
    total_cost = result["total_cost"]

    # Apply verdict (reuse logic from legacy arbiter)
    from core.arbiter import _apply_verdict
    result_status = f"resolved_{verdict}"
    await db.execute(
        "UPDATE disputes SET status = ?, arbiter_verdict = ?, arbiter_cost_usdc = ?, resolved_at = ? WHERE id = ?",
        (result_status, json.dumps(verdict_data), total_cost, now, dispute_id),
    )

    await _apply_verdict(db, dispute, auction, verdict, total_cost, now)
    await db.commit()

    logger.info(f"[MULTI_ARBITER] Dispute {dispute_id} resolved: {result_status} (cost=${total_cost:.5f})")

    from core.telegram_notifier import notify_dispute_resolved
    await notify_dispute_resolved(dispute_id, verdict, float(verdict_data.get("confidence", 0.0)))

    return {
        "verdict": verdict,
        "verdict_data": verdict_data,
        "arbiter_cost_usdc": total_cost,
        "arbiters_used": verdict_data.get("arbiters_used", []),
        "majority_vote": result.get("majority", False),
    }
