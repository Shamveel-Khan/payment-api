from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.payment import Payment


HIGH_AMOUNT_THRESHOLD = 100_000
RAPID_PAYMENT_WINDOW_MINUTES = 5
RAPID_PAYMENT_COUNT = 3


def check_fraud(
    payment: Payment,
    db: Session,
) -> tuple[bool, int, list[str]]:
    """
    Evaluate a payment using simple rule-based fraud detection.

    Returns:
        is_suspicious: whether the payment is suspicious
        fraud_score: accumulated risk score
        reasons: rules that were triggered
    """

    fraud_score = 0
    reasons: list[str] = []

    # Rule 1: unusually large payment
    if payment.amount > HIGH_AMOUNT_THRESHOLD:
        fraud_score += 50
        reasons.append("high_amount")

    # Rule 2: multiple payments in a short time window
    window_start = datetime.now(timezone.utc) - timedelta(
        minutes=RAPID_PAYMENT_WINDOW_MINUTES
    )

    recent_payment_count = (
        db.query(Payment)
        .filter(
            Payment.user_id == payment.user_id,
            Payment.created_at >= window_start,
            Payment.id != payment.id,
        )
        .count()
    )

    if recent_payment_count >= RAPID_PAYMENT_COUNT:
        fraud_score += 30
        reasons.append("rapid_repeated_payments")

    # Final decision
    is_suspicious = fraud_score >= 50

    return is_suspicious, fraud_score, reasons