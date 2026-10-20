import json
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.models.payment import Payment
from app.services.payment_service import update_payment_status


router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    payload = await request.body()

    if settings.PAYMENT_PROVIDER == "stripe":
        signature = request.headers.get("stripe-signature")

        if not signature or not settings.STRIPE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe webhook signature",
            )

        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.SignatureVerificationError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe webhook",
            )
    else:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook payload",
            )

    event_id = event.get("id")
    event_type = event.get("type")
    event_data = event.get("data", {}).get("object", {})

    payment_intent_id = event_data.get("id")

    if event_type == "payment_intent.succeeded":
        status_value = "succeeded"
    elif event_type == "payment_intent.payment_failed":
        status_value = "failed"
    else:
        return {"status": "ignored"}

    payment = (
        db.query(Payment)
        .filter(
            Payment.stripe_payment_intent_id == payment_intent_id
        )
        .first()
    )

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if event_id:
        existing_event = (
            db.query(Payment)
            .filter(Payment.webhook_event_id == event_id)
            .first()
        )

        if existing_event:
            return {
                "status": "already_processed",
                "payment_status": existing_event.status,
            }

    status_updated = update_payment_status(
        payment,
        status_value,
    )

    if event_id:
        payment.webhook_event_id = event_id

    if status_updated:
        db.commit()

    return {
        "status": "processed",
        "payment_status": payment.status,
    }