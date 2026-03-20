"""
Telegram notifier for OIXA Protocol.
Sends alerts to Ivan for key protocol events.
Falls back silently if Telegram is not configured.
"""

import asyncio
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID

logger = logging.getLogger(__name__)

_bot = None


def _get_bot():
    global _bot
    if _bot is None and TELEGRAM_BOT_TOKEN:
        try:
            from telegram import Bot
            _bot = Bot(token=TELEGRAM_BOT_TOKEN)
        except Exception as exc:
            logger.warning(f"Telegram bot init failed: {exc}")
    return _bot


async def send_alert(message: str) -> None:
    """Send a message to Ivan's Telegram. Silently no-ops if not configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_OWNER_ID:
        return
    bot = _get_bot()
    if bot is None:
        return
    try:
        await bot.send_message(
            chat_id=TELEGRAM_OWNER_ID,
            text=message,
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning(f"Telegram send failed: {exc}")


# ── Event helpers ─────────────────────────────────────────────────────────────

async def notify_escrow_created(auction_id: str, amount: float, winner_id: str) -> None:
    await send_alert(
        f"💰 <b>Escrow created</b>\n"
        f"Auction: <code>{auction_id}</code>\n"
        f"Winner: <code>{winner_id}</code>\n"
        f"Amount: <b>${amount:.4f} USDC</b>"
    )


async def notify_payment_released(auction_id: str, amount: float, payee_id: str, commission: float) -> None:
    await send_alert(
        f"✅ <b>Payment released</b>\n"
        f"Auction: <code>{auction_id}</code>\n"
        f"To: <code>{payee_id}</code>\n"
        f"Net: <b>${amount - commission:.4f} USDC</b> (commission: ${commission:.4f})"
    )


async def notify_dispute_opened(dispute_id: str, auction_id: str, requester_id: str, fee: float) -> None:
    await send_alert(
        f"⚠️ <b>Dispute opened</b>\n"
        f"Dispute: <code>{dispute_id}</code>\n"
        f"Auction: <code>{auction_id}</code>\n"
        f"By: <code>{requester_id}</code>\n"
        f"Fee paid: ${fee:.4f} USDC"
    )


async def notify_dispute_resolved(dispute_id: str, verdict: str, confidence: float) -> None:
    emoji = "🏆" if verdict == "agent_wins" else "🔄"
    await send_alert(
        f"{emoji} <b>Dispute resolved</b>\n"
        f"Dispute: <code>{dispute_id}</code>\n"
        f"Verdict: <b>{verdict}</b> (confidence: {confidence:.0%})"
    )


async def notify_daily_limit(spent: float, limit: float, pct: float) -> None:
    emoji = "🚨" if pct >= 1.0 else "⚠️"
    await send_alert(
        f"{emoji} <b>Daily spending alert</b>\n"
        f"Spent: <b>${spent:.2f}</b> / ${limit:.2f} ({pct:.0%})"
    )


async def notify_emergency_pause(paused: bool, by: str = "protocol") -> None:
    emoji = "🛑" if paused else "▶️"
    action = "PAUSED" if paused else "UNPAUSED"
    await send_alert(
        f"{emoji} <b>Contract {action}</b>\n"
        f"Triggered by: <code>{by}</code>"
    )


async def notify_server_start(mode: str) -> None:
    await send_alert(
        f"🚀 <b>OIXA Protocol started</b>\n"
        f"Mode: <b>{mode}</b>"
    )


async def notify_auction_created(auction_id: str, description: str, budget: float, requester_id: str) -> None:
    short_desc = description[:80] + "…" if len(description) > 80 else description
    await send_alert(
        f"📋 <b>New auction</b>\n"
        f"ID: <code>{auction_id}</code>\n"
        f"Task: {short_desc}\n"
        f"Budget: <b>${budget:.4f} USDC</b>\n"
        f"By: <code>{requester_id}</code>"
    )


async def notify_bid_placed(auction_id: str, bidder_id: str, amount: float, is_winning: bool) -> None:
    emoji = "🏆" if is_winning else "📥"
    status = "new best" if is_winning else "bid placed"
    await send_alert(
        f"{emoji} <b>Bid {status}</b>\n"
        f"Auction: <code>{auction_id}</code>\n"
        f"From: <code>{bidder_id}</code>\n"
        f"Amount: <b>${amount:.4f} USDC</b>"
    )


async def notify_auction_closed(auction_id: str, winner_id: str, winning_bid: float) -> None:
    await send_alert(
        f"🔒 <b>Auction closed</b>\n"
        f"Auction: <code>{auction_id}</code>\n"
        f"Winner: <code>{winner_id}</code>\n"
        f"Winning bid: <b>${winning_bid:.4f} USDC</b>"
    )


async def notify_transaction(tx_type: str, from_agent: str, to_agent: str, amount: float, auction_id: str = "") -> None:
    icons = {
        "payment": "💳",
        "commission": "💰",
        "stake": "🔐",
        "refund": "↩️",
        "commission_sweep": "💸",
    }
    emoji = icons.get(tx_type, "📊")
    msg = (
        f"{emoji} <b>{tx_type.replace('_', ' ').title()}</b>\n"
        f"From: <code>{from_agent}</code>\n"
        f"To: <code>{to_agent}</code>\n"
        f"Amount: <b>${amount:.4f} USDC</b>"
    )
    if auction_id:
        msg += f"\nAuction: <code>{auction_id}</code>"
    await send_alert(msg)
