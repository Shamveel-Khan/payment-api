import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.database.database import SessionLocal
from app.main import app
from app.models.payment import Payment
from app.models.user import User
from app.models.refund import Refund


client = TestClient(app)


@pytest.fixture
def test_user():
    db = SessionLocal()

    user = User(
        email=f"refund_test_{uuid.uuid4().hex}@example.com",
        full_name="Refund Test User",
        hashed_password="test-password",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    # Get all payments belonging to this test user.
    payments = db.query(Payment).filter(
        Payment.user_id == user.id
    ).all()

    payment_ids = [payment.id for payment in payments]

    # Delete refunds first because they reference payments.
    if payment_ids:
        db.query(Refund).filter(
            Refund.payment_id.in_(payment_ids)
        ).delete(
            synchronize_session=False
        )

        # Now payments can be safely deleted.
        db.query(Payment).filter(
            Payment.id.in_(payment_ids)
        ).delete(
            synchronize_session=False
        )

    # Finally delete the test user.
    db.delete(user)
    db.commit()
    db.close()

@pytest.fixture
def authenticated_client(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user

    yield client

    app.dependency_overrides.clear()


def create_payment(authenticated_client, amount=5000):
    response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": f"refund-test-{uuid.uuid4().hex}",
        },
        json={
            "amount": amount,
            "currency": "INR",
        },
    )

    assert response.status_code == 201

    return response.json()


def mark_payment_succeeded(payment_id):
    db = SessionLocal()

    payment = db.get(Payment, payment_id)
    payment.status = "succeeded"

    db.commit()
    db.close()


def test_partial_refund(authenticated_client):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 1000,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["refunded_amount"] == 1000
    assert data["status"] == "partially_refunded"


def test_multiple_partial_refunds(authenticated_client):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    first_response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 1000,
        },
    )

    second_response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 2000,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    data = second_response.json()

    assert data["refunded_amount"] == 3000
    assert data["status"] == "partially_refunded"


def test_full_refund_after_partial_refund(authenticated_client):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    first_response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 1000,
        },
    )

    assert first_response.status_code == 200

    second_response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 4000,
        },
    )

    assert second_response.status_code == 200

    data = second_response.json()

    assert data["refunded_amount"] == 5000
    assert data["status"] == "refunded"


def test_over_refund_is_rejected(authenticated_client):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 5001,
        },
    )

    assert response.status_code == 400

    assert "exceeds the remaining refundable amount" in (
        response.json()["detail"]
    )


def test_refund_of_failed_payment_is_rejected(
    authenticated_client,
):
    payment = create_payment(authenticated_client)

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 1000,
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Only refundable payments can be refunded."
    )

def test_unauthenticated_user_cannot_refund():
    response = client.post(
        "/payments/1/refund",
        json={
            "amount": 1000,
        },
    )

    assert response.status_code == 401


def test_pending_payment_cannot_be_refunded(
    authenticated_client,
):
    payment = create_payment(authenticated_client)

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 1000,
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Only refundable payments can be refunded."
    )


def test_zero_refund_is_rejected(
    authenticated_client,
):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 0,
        },
    )

    assert response.status_code == 422


def test_negative_refund_is_rejected(
    authenticated_client,
):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": -100,
        },
    )

def test_unauthenticated_user_cannot_refund():
    response = client.post(
        "/payments/1/refund",
        json={
            "amount": 1000,
        },
    )

    assert response.status_code == 401


def test_pending_payment_cannot_be_refunded(
    authenticated_client,
):
    payment = create_payment(authenticated_client)

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 1000,
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Only refundable payments can be refunded."
    )


def test_zero_refund_is_rejected(
    authenticated_client,
):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": 0,
        },
    )

    assert response.status_code == 422


def test_negative_refund_is_rejected(
    authenticated_client,
):
    payment = create_payment(authenticated_client)

    mark_payment_succeeded(payment["id"])

    response = authenticated_client.post(
        f"/payments/{payment['id']}/refund",
        json={
            "amount": -100,
        },
    )

    assert response.status_code == 422