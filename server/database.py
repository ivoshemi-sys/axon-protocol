import aiosqlite
from config import DB_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
    return _db


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS offers (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            capabilities TEXT NOT NULL,
            price_per_unit REAL NOT NULL,
            currency TEXT DEFAULT 'USDC',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auctions (
            id TEXT PRIMARY KEY,
            rfi_description TEXT NOT NULL,
            max_budget REAL NOT NULL,
            currency TEXT DEFAULT 'USDC',
            requester_id TEXT NOT NULL,
            winner_id TEXT,
            winning_bid REAL,
            status TEXT DEFAULT 'open',
            auction_duration_seconds INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            closed_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS bids (
            id TEXT PRIMARY KEY,
            auction_id TEXT NOT NULL,
            bidder_id TEXT NOT NULL,
            bidder_name TEXT NOT NULL,
            amount REAL NOT NULL,
            stake_amount REAL NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY (auction_id) REFERENCES auctions(id)
        );

        CREATE TABLE IF NOT EXISTS escrows (
            id TEXT PRIMARY KEY,
            auction_id TEXT NOT NULL,
            payer_id TEXT NOT NULL,
            payee_id TEXT NOT NULL,
            amount REAL NOT NULL,
            commission REAL NOT NULL,
            status TEXT DEFAULT 'held',
            created_at TEXT NOT NULL,
            released_at TEXT,
            FOREIGN KEY (auction_id) REFERENCES auctions(id)
        );

        CREATE TABLE IF NOT EXISTS verifications (
            id TEXT PRIMARY KEY,
            auction_id TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            verified_at TEXT NOT NULL,
            passed BOOLEAN NOT NULL,
            details TEXT,
            FOREIGN KEY (auction_id) REFERENCES auctions(id)
        );

        CREATE TABLE IF NOT EXISTS ledger (
            id TEXT PRIMARY KEY,
            transaction_type TEXT NOT NULL,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USDC',
            auction_id TEXT,
            description TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS protocol_revenue (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USDC',
            auction_id TEXT,
            period TEXT,
            simulated BOOLEAN DEFAULT TRUE,
            created_at TEXT NOT NULL
        );
    """)
    await db.commit()
