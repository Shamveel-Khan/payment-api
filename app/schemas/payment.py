from datetime import datetime

from pydantic import BaseModel, Field

class PaymentCreate(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)

class PaymentResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    currency: str
    status: str
    stripe_payment_intent_id: str | None
    # refund_id: str | None
    refunded_amount: int
    is_suspicious: bool
    fraud_score: int
    fraud_reasons: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class RefundRequest(BaseModel):
    amount: int = Field(gt=0)