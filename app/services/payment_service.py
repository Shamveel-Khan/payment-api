import uuid

import stripe
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.payment import Payment


stripe.api_key = settings.STRIPE_SECRET_KEY


def create_payment_intent(
    amount: int,
    currency: str,
) -> str:
    """Create a payment intent through the configured payment provider."""

    if settings.PAYMENT_PROVIDER == "mock":
        return f"mock_pi_{uuid.uuid4().hex}"

    if settings.PAYMENT_PROVIDER != "stripe":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unsupported payment provider",
        )

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe integration is not configured",
        )

    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency.lower(),
        )

        return payment_intent.id

    except stripe.StripeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe payment intent",
        )

VALID_STATUS_TRANSITIONS = {
    "pending": {"succeeded", "failed"},
    "succeeded": {"partially_refunded", "refunded"},
    "partially_refunded": {"partially_refunded", "refunded"},
    "failed": set(),
    "refunded": set(),
}


def update_payment_status(payment, new_status: str) -> bool:
    """
    Update payment status only when the transition is valid.

    Returns True if the status was changed.
    """
    allowed_statuses = VALID_STATUS_TRANSITIONS.get(
        payment.status,
        set(),
    )

    if new_status not in allowed_statuses:
        return False

    payment.status = new_status
    return True

def create_refund(payment: Payment) -> str:
    """
    Create a refund for a payment.

    Currently uses the mock provider.
    Returns a mock refund ID.
    """

    if settings.PAYMENT_PROVIDER == "mock":
        # return f"mock_refund_{payment.id}"
        return f"mock_refund_{uuid.uuid4().hex}"

    # Stripe implementation will be added when using
    # the real Stripe provider.
    raise NotImplementedError(
        "Stripe refund provider is not configured."
    )