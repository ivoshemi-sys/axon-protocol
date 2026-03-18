from pydantic import BaseModel, ConfigDict


class DisputeOpen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auction_id: str
    opened_by: str   # agent_id of the requester opening the dispute
    reason: str


class DisputeResolve(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verdict: str          # "requester_wins" | "agent_wins"
    reasoning: str
    resolved_by: str = "manual"   # "claude_arbiter" | "manual"


class Dispute(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    auction_id: str
    opened_by: str
    reason: str
    status: str           # open | resolving | resolved_agent_wins | resolved_requester_wins
    fee_amount: float
    arbiter_verdict: str | None
    arbiter_cost_usdc: float | None
    created_at: str
    resolved_at: str | None
