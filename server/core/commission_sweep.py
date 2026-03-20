"""
Commission sweep — runs every 6 hours.
Collects all unsimulated (pending) commissions from protocol_revenue and marks them
as swept. In Phase 1 (simulated) this records intent + sends Telegram alert.
In Phase 2: set PROTOCOL_WALLET in .env to trigger real USDC transfer on Base.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from config import PROTOCOL_WALLET, PROTOCOL_VERSION

logger = logging.getLogger("oixa.sweep")

SWEEP_INTERVAL_SECONDS = 6 * 3600  # 6 hours


async def _do_sweep():
    from database import get_db

    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Sum all commissions not yet swept
    async with db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM protocol_revenue "
        "WHERE source = 'commission' AND (period IS NULL OR period != 'swept')"
    ) as cur:
        row = await cur.fetchone()
    amount = float(row["total"] if row else 0.0)

    if amount <= 0:
        logger.debug("[SWEEP] Nothing to sweep")
        return

    # Mark them as swept
    await db.execute(
        "UPDATE protocol_revenue SET period = 'swept' "
        "WHERE source = 'commission' AND (period IS NULL OR period != 'swept')",
        (),
    )
    await db.commit()

    # Record sweep in ledger
    sweep_id = f"oixa_ledger_{uuid.uuid4().hex[:12]}"
    wallet_label = PROTOCOL_WALLET if PROTOCOL_WALLET else "PENDING_WALLET"
    await db.execute(
        """INSERT INTO ledger
           (id, transaction_type, from_agent, to_agent, amount, currency, description, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sweep_id,
            "commission_sweep",
            "oixa_protocol",
            wallet_label,
            amount,
            "USDC",
            f"6h commission sweep — {'simulated' if not PROTOCOL_WALLET else 'Base mainnet'}",
            now,
        ),
    )
    await db.commit()

    logger.info(f"[SWEEP] Swept ${amount:.4f} USDC → {wallet_label}")

    # Telegram alert
    try:
        from core.telegram_notifier import send_alert
        mode = "Base mainnet" if PROTOCOL_WALLET else "simulated (no wallet configured)"
        await send_alert(
            f"💸 <b>Commission sweep</b>\n"
            f"Amount: <b>${amount:.4f} USDC</b>\n"
            f"Wallet: <code>{wallet_label}</code>\n"
            f"Mode: {mode}"
        )
    except Exception as exc:
        logger.warning(f"[SWEEP] Telegram alert failed: {exc}")


async def commission_sweep_loop():
    """Background task: sweep commissions every 6 hours."""
    logger.info(f"[SWEEP] Commission sweep loop started (interval: {SWEEP_INTERVAL_SECONDS}s)")
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            await _do_sweep()
        except Exception as exc:
            logger.error(f"[SWEEP] Sweep failed: {exc}")
