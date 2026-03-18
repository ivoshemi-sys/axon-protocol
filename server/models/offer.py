from pydantic import BaseModel, ConfigDict


class OfferCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    agent_name: str
    capabilities: list[str]
    price_per_unit: float
    currency: str = "USDC"
    wallet_address: str | None = None  # On-chain Base wallet for receiving USDC payments


class Offer(OfferCreate):
    id: str
    status: str
    created_at: str
    updated_at: str


class OfferUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_name: str | None = None
    capabilities: list[str] | None = None
    price_per_unit: float | None = None
    currency: str | None = None
    status: str | None = None
