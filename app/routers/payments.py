from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.database import get_db
from app.models import payment
from app.models.payment import Payment
from app.models.user import User
from app.models.refund import Refund
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    RefundRequest,
)
from app.services.payment_service import (
    create_payment_intent,
    create_refund,
    update_payment_status,
)
from app.services.fraud_service import check_fraud

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payment_data: PaymentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> Payment:

    # 1. Check idempotency key
    existing_payment = (
        db.query(Payment)
        .filter(Payment.idempotency_key == idempotency_key)
        .first()
    )

    if existing_payment:
        if existing_payment.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already belongs to another user.",
            )

        if (
            existing_payment.amount != payment_data.amount
            or existing_payment.currency
            != payment_data.currency.upper()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Idempotency key already used with "
                    "different payment parameters."
                ),
            )

        return existing_payment

    # 2. Build payment
    payment = Payment(
        user_id=current_user.id,
        amount=payment_data.amount,
        currency=payment_data.currency.upper(),
        status="pending",
        idempotency_key=idempotency_key,
    )

    # 3. Fraud detection
    is_suspicious, fraud_score, fraud_reasons = check_fraud(
        payment,
        db,
    )

    payment.is_suspicious = is_suspicious
    payment.fraud_score = fraud_score
    payment.fraud_reasons = (
        ",".join(fraud_reasons)
        if fraud_reasons
        else None
    )

    # 4. Stop suspicious payment
    if is_suspicious:
        payment.status = "failed"

        try:
            db.add(payment)
            db.commit()
            db.refresh(payment)
        except Exception:
            db.rollback()
            raise

        return payment

    # 5. Safe payment → create payment intent
    stripe_payment_intent_id = create_payment_intent(
        amount=payment_data.amount,
        currency=payment_data.currency,
    )

    payment.stripe_payment_intent_id = stripe_payment_intent_id

    # 6. Save payment
    try:
        db.add(payment)
        db.commit()
        db.refresh(payment)
    except Exception:
        db.rollback()
        raise

    return payment

@router.get(
    "/fraud/suspicious",
    response_model=list[PaymentResponse],
)
def list_suspicious_payments(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Payment]:

    return (
        db.query(Payment)
        .filter(
            Payment.user_id == current_user.id,
            Payment.is_suspicious.is_(True),
        )
        .order_by(Payment.created_at.desc())
        .all()
    )

@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
)
def refund_payment(
    payment_id: int,
    refund_data: RefundRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:

    payment = db.get(Payment, payment_id)

    if payment is None or payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if payment.status not in {"succeeded", "partially_refunded"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only refundable payments can be refunded.",
        )

    remaining_amount = payment.amount - payment.refunded_amount

    if refund_data.amount > remaining_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Refund amount exceeds the remaining refundable amount "
                f"of {remaining_amount}."
            ),
        )

    refund_id = create_refund(payment)

    payment.refunded_amount += refund_data.amount

    refund = Refund(
        payment_id=payment.id,
        amount=refund_data.amount,
        provider_refund_id=refund_id,
        status="succeeded",
    )

    db.add(refund)

    if payment.refunded_amount == payment.amount:
        status_updated = update_payment_status(
            payment,
        "refunded",
        )
    else:
        status_updated = update_payment_status(
        payment,
        "partially_refunded",
    )

    if not status_updated:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment cannot be refunded in its current state.",
            )

    try:
        db.commit()
        db.refresh(payment)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process refund.",
        )

    return payment

@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
def get_payment(
    payment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:

    payment = db.get(Payment, payment_id)

    if payment is None or payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return payment


@router.get(
    "/",
    response_model=list[PaymentResponse],
)
def list_payments(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Literal[
        "pending",
        "succeeded",
        "failed",
    ] | None = None,
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
) -> list[Payment]:

    query = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )

    if status_filter:
        query = query.filter(
            Payment.status == status_filter
        )

    return query.offset(skip).limit(limit).all()