from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console

from database import init_db, get_db
from core.openclaw import openclaw_client
from core.rate_limiter import rate_limiter
from api.offers import router as offers_router
from api.auctions import router as auctions_router
from api.escrow import router as escrow_router
from api.verify import router as verify_router
from api.ledger import router as ledger_router
from api.aipi import router as aipi_router
from config import PROTOCOL_VERSION

console = Console()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    console.print("[bold green]✅ Database initialized[/bold green]")
    await openclaw_client.connect()
    console.print("[bold green]🚀 AXON Protocol server running[/bold green]")
    yield
    console.print("[bold red]🛑 AXON Protocol server stopped[/bold red]")


app = FastAPI(
    title="AXON Protocol",
    description="The connective tissue of the agent economy",
    version=PROTOCOL_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(offers_router, prefix="/api/v1")
app.include_router(auctions_router, prefix="/api/v1")
app.include_router(escrow_router, prefix="/api/v1")
app.include_router(verify_router, prefix="/api/v1")
app.include_router(ledger_router, prefix="/api/v1")
app.include_router(aipi_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "protocol": "AXON",
        "version": PROTOCOL_VERSION,
        "status": "operational",
        "phase": 1,
        "escrow": "simulated",
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


@app.get("/health")
async def health():
    db = await get_db()
    db_ok = True
    try:
        async with db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
    except Exception:
        db_ok = False

    from database import get_db as _get_db
    _db = await _get_db()

    async with _db.execute("SELECT SUM(amount) as total FROM protocol_revenue WHERE source = 'commission'") as cursor:
        comm_row = await cursor.fetchone()
    total_commissions = comm_row["total"] or 0.0 if comm_row else 0.0

    async with _db.execute("SELECT SUM(amount) as total FROM protocol_revenue WHERE source = 'yield'") as cursor:
        yield_row = await cursor.fetchone()
    total_yield = yield_row["total"] or 0.0 if yield_row else 0.0

    async with _db.execute("SELECT COUNT(*) as total FROM ledger") as cursor:
        tx_row = await cursor.fetchone()
    total_tx = tx_row["total"] if tx_row else 0

    return {
        "status": "ok",
        "openclaw": openclaw_client.connected,
        "db": "ok" if db_ok else "error",
        "rate_limiter": rate_limiter.get_stats(),
        "protocol_revenue": {
            "total_commissions_simulated": total_commissions,
            "total_yield_simulated": total_yield,
            "total_transactions": total_tx,
            "commission_rate_current": "5%",
        },
    }
