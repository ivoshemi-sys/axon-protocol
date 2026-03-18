from pydantic import BaseModel, ConfigDict


class LedgerEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transaction_type: str
    from_agent: str
    to_agent: str
    amount: float
    currency: str
    auction_id: str | None
    description: str | None
    created_at: str


class LedgerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_type: str
    from_agent: str
    to_agent: str
    amount: float
    currency: str = "USDC"
    auction_id: str | None = None
    description: str | None = None
