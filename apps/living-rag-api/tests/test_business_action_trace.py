from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import get_db
from app.main import app
from app.models.agent_run import AgentRun
from app.models.approval_task import ApprovalTask
from app.models.audit_log import AuditLog
from app.models.chat_message import ChatMessage
from app.models.membership_account import (
    MembershipAccount,
    MembershipTier,
)
from app.models.order import Order, OrderStatus
from app.models.user import User


@pytest.fixture
def client(db_session) -> TestClient:
    """Use the isolated database session for trace tests."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_user_with_order(
    db_session,
) -> tuple[User, Order]:
    """Create one user and one order owned by that user."""

    user = User(
        external_id="USR-TRACE-001",
        display_name="Trace Test User",
    )

    membership = MembershipAccount(
        user=user,
        membership_number="M-TRACE-001",
        tier=MembershipTier.STANDARD,
    )

    order = Order(
        membership_account=membership,
        order_number="O2025001",
        status=OrderStatus.COMPLETED,
        total_amount=Decimal("199.00"),
        metadata_={
            "received_at": "2026-08-01T14:30:00+08:00",
            "returnable": True,
            "product_name": "Trace Test Product",
        },
    )

    db_session.add(user)
    db_session.flush()

    return user, order


def test_direct_refund_trace_links_all_records(
    client: TestClient,
    db_session,
) -> None:
    """One business action must share its trace across all records."""

    user, order = _create_user_with_order(
        db_session,
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "Issue refund directly O2025001",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    trace_id = UUID(payload["trace_id"])
    approval_task_id = UUID(payload["approval_task_id"])

    assert payload["action"] == "create_approval_task"
    assert payload["status"] == "pending"
    assert payload["order_number"] == "O2025001"

    task_statement = select(ApprovalTask).where(
        ApprovalTask.id == approval_task_id,
    )

    task = db_session.scalar(task_statement)

    assert task is not None
    assert task.resource_id == order.id
    assert task.trace_id == trace_id

    audit_statement = select(AuditLog).where(
        AuditLog.trace_id == trace_id,
    )

    audit_logs = db_session.scalars(
        audit_statement,
    ).all()

    assert len(audit_logs) == 1
    assert audit_logs[0].resource_id == approval_task_id
    assert audit_logs[0].trace_id == trace_id
    assert audit_logs[0].action == "create_approval_task"

    agent_run_statement = select(AgentRun).where(
        AgentRun.trace_id == trace_id,
    )

    agent_run = db_session.scalar(agent_run_statement)

    assert agent_run is not None
    assert agent_run.trace_id == trace_id
    assert agent_run.intent == "high_risk_operation"
    assert agent_run.thread_id is not None
    assert agent_run.message_id is not None

    message_statement = select(ChatMessage).where(
        ChatMessage.trace_id == trace_id,
    )

    messages = db_session.scalars(
        message_statement,
    ).all()

    assert len(messages) == 2
    assert {
        message.role.value
        for message in messages
    } == {
        "user",
        "assistant",
    }

    assert all(
        message.trace_id == trace_id
        for message in messages
    )

    user_messages = [
        message
        for message in messages
        if message.role.value == "user"
    ]

    assistant_messages = [
        message
        for message in messages
        if message.role.value == "assistant"
    ]

    assert len(user_messages) == 1
    assert user_messages[0].content == (
        "Issue refund directly O2025001"
    )

    assert len(assistant_messages) == 1
    assert "人工审批" in assistant_messages[0].content


def test_read_only_action_persists_agent_trace_without_approval(
    client: TestClient,
    db_session,
) -> None:
    """Read-only actions persist conversation and run records only."""

    user, _ = _create_user_with_order(
        db_session,
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "Is O2025001 eligible for a refund?",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    trace_id = UUID(payload["trace_id"])

    assert payload["action"] == "read_only"
    assert payload["status"] == "eligible"
    assert payload["approval_task_id"] is None

    task_statement = select(ApprovalTask).where(
        ApprovalTask.trace_id == trace_id,
    )

    tasks = db_session.scalars(
        task_statement,
    ).all()

    assert tasks == []

    audit_statement = select(AuditLog).where(
        AuditLog.trace_id == trace_id,
    )

    audit_logs = db_session.scalars(
        audit_statement,
    ).all()

    assert audit_logs == []

    agent_run_statement = select(AgentRun).where(
        AgentRun.trace_id == trace_id,
    )

    agent_run = db_session.scalar(agent_run_statement)

    assert agent_run is not None
    assert agent_run.trace_id == trace_id
    assert agent_run.intent == "order_membership"

    message_statement = select(ChatMessage).where(
        ChatMessage.trace_id == trace_id,
    )

    messages = db_session.scalars(
        message_statement,
    ).all()

    assert len(messages) == 2
    assert all(
        message.trace_id == trace_id
        for message in messages
    )
