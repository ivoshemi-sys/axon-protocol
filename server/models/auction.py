from pydantic import BaseModel, ConfigDict


class RFI(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rfi_description: str
    max_budget: float
    requester_id: str
    currency: str = "USDC"


class Bid(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auction_id: str
    bidder_id: str
    bidder_name: str
    amount: float


class BidCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bidder_id: str
    bidder_name: str
    amount: float


class Auction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rfi_description: str
    max_budget: float
    requester_id: str
    currency: str
    status: str
    auction_duration_seconds: int
    created_at: str
    winner_id: str | None = None
    winning_bid: float | None = None
    closed_at: str | None = None
    completed_at: str | None = None
    bids: list[Bid] = []


class DeliverOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    output: str
