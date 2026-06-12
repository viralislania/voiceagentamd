"""All Pydantic models for the banking agent (API payloads + internal types)."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Backend request/response models ──────────────────────────────────────────

class StatementQuery(BaseModel):
    account_id: str
    from_date:  Optional[str] = None
    to_date:    Optional[str] = None
    category:   Optional[str] = None
    rail:       Optional[str] = None
    detailed:   bool = False


class DepositBookingRequest(BaseModel):
    customer_id:   str
    product_id:    str
    amount:        float
    tenure_months: int


class PaymentConsentRequest(BaseModel):
    customer_id:  str
    from_account: str
    payee_id:     str
    amount:       float
    rail:         str
    reason:       Optional[str] = None


class AuthorisationRequest(BaseModel):
    consent_id: str
    otp:        str


class ComplaintRequest(BaseModel):
    customer_id: str
    txn_id:      Optional[str] = None
    category:    str
    description: str
    topics:      list[str] = Field(default_factory=list)
    sentiment:   Optional[str] = None


# ── Agent state ───────────────────────────────────────────────────────────────

class AgentState(BaseModel):
    """Typed representation used in demo/testing; LangGraph uses TypedDict."""
    customer_id:    str
    user_msg:       str
    intent:         Optional[str] = None
    slots:          dict[str, Any] = Field(default_factory=dict)
    pending_slot:   Optional[str] = None
    pending_action: Optional[str] = None
    tool_result:    Optional[dict] = None
    response_text:  Optional[str] = None
    a2ui:           Optional[list[dict]] = None   # list of A2UI v0.9 messages
    done:           bool = False


# ── A2UI protocol types ───────────────────────────────────────────────────────

class A2UIComponent(BaseModel):
    """A single component entry in an updateComponents payload."""
    id:        str
    component: str
    model_config = {"extra": "allow"}    # allow catalog-specific props


class CreateSurface(BaseModel):
    surfaceId:     str
    catalogId:     str = "https://a2ui.org/specification/v0_9/basic_catalog.json"
    sendDataModel: bool = False
    theme:         Optional[dict] = None


class UpdateComponents(BaseModel):
    surfaceId:  str
    components: list[dict]


class UpdateDataModel(BaseModel):
    surfaceId: str
    path:      str = "/"
    value:     Any = None


class A2UIMessage(BaseModel):
    version: str = "v0.9"
    createSurface:    Optional[CreateSurface]    = None
    updateComponents: Optional[UpdateComponents] = None
    updateDataModel:  Optional[UpdateDataModel]  = None

    def to_dict(self) -> dict:
        out: dict = {"version": self.version}
        if self.createSurface:
            out["createSurface"] = self.createSurface.model_dump(exclude_none=True)
        if self.updateComponents:
            out["updateComponents"] = self.updateComponents.model_dump(exclude_none=True)
        if self.updateDataModel:
            out["updateDataModel"] = self.updateDataModel.model_dump(exclude_none=True)
        return out


# ── LLM response models ───────────────────────────────────────────────────────

class ClassifyResponse(BaseModel):
    intent: str
    slots:  dict[str, Any] = Field(default_factory=dict)


class InsightResponse(BaseModel):
    topics:    list[str] = Field(default_factory=list)
    sentiment: str = "neutral"
