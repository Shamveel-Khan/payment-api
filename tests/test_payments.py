import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.database.database import SessionLocal
from app.main import app
from app.models.payment import Payment
from app.models.user import User


client = TestClient(app)


@pytest.fixture
def test_user():
    db = SessionLocal()

    user = User(
        email=f"test_{uuid.uuid4().hex}@example.com",
        full_name="Payment Test User",
        hashed_password="test-password",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    # Clean up payments created during the test
    db.query(Payment).filter(
        Payment.user_id == user.id
    ).delete()

    db.delete(user)
    db.commit()
    db.close()


@pytest.fixture
def authenticated_client(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user

    yield client

    app.dependency_overrides.clear()


def test_create_payment(
    authenticated_client,
):
    response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": f"test-{uuid.uuid4().hex}",
        },
        json={
            "amount": 4002,
            "currency": "INR",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["amount"] == 4002
    assert data["currency"] == "INR"
    assert data["status"] == "pending"


def test_idempotency_same_request_returns_existing_payment(
    authenticated_client,
):
    idempotency_key = f"test-{uuid.uuid4().hex}"

    first_response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": idempotency_key,
        },
        json={
            "amount": 4002,
            "currency": "INR",
        },
    )

    second_response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": idempotency_key,
        },
        json={
            "amount": 4002,
            "currency": "INR",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_data = first_response.json()
    second_data = second_response.json()

    assert first_data["id"] == second_data["id"]


def test_idempotency_different_parameters_returns_conflict(
    authenticated_client,
):
    idempotency_key = f"test-{uuid.uuid4().hex}"

    first_response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": idempotency_key,
        },
        json={
            "amount": 4002,
            "currency": "INR",
        },
    )

    second_response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": idempotency_key,
        },
        json={
            "amount": 4001,
            "currency": "INR",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    assert (
        second_response.json()["detail"]
        == "Idempotency key already used with different payment parameters."
    )


# Create a normal payment that should pass fraud detection
def test_safe_payment_passes_fraud_check(
    authenticated_client,
):
    response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": f"fraud-test-{uuid.uuid4().hex}",
        },
        json={
            "amount": 5000,
            "currency": "INR",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["is_suspicious"] is False
    assert data["fraud_score"] == 0
    assert data["fraud_reasons"] is None

# test an amount that triggers it:
def test_high_amount_payment_is_flagged(
    authenticated_client,
):
    response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": f"fraud-test-{uuid.uuid4().hex}",
        },
        json={
            "amount": 1000000000,
            "currency": "INR",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["is_suspicious"] is True
    assert data["fraud_score"] > 0
    assert "high_amount" in data["fraud_reasons"]
    assert data["status"] == "failed"

# Rapid repeated payments Test
def test_rapid_repeated_payment_is_flagged(
    authenticated_client,
):
    # Create 3 recent payments first.
    for _ in range(3):
        response = authenticated_client.post(
            "/payments/",
            headers={
                "Idempotency-Key": f"fraud-test-{uuid.uuid4().hex}",
            },
            json={
                "amount": 5000,
                "currency": "INR",
            },
        )

        assert response.status_code == 201

    # The 4th payment triggers the rapid-payment rule.
    response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": f"fraud-test-{uuid.uuid4().hex}",
        },
        json={
            "amount": 5000,
            "currency": "INR",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["is_suspicious"] is False
    assert data["fraud_score"] == 30
    assert "rapid_repeated_payments" in data["fraud_reasons"]
    assert data["status"] == "pending"