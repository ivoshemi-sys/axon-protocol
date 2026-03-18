from pydantic import BaseModel, ConfigDict


class EscrowCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auction_id: str
    payer_id: str
    payee_id: str
    amount: float


class Escrow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    auction_id: str
    payer_id: str
    payee_id: str
    amount: float
    commission: float
    status: str
    simulated: bool = True
    created_at: str
    released_at: str | None = None


class SimulatePayment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auction_id: str
    amount: float
    payer_id: str
    payee_id: str
