from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.audit_log import (
    AuditActorType,
    AuditLog,
    AuditResult,
)


@pytest.fixture
def client(db_session) -> TestClient:
    """Use the isolated database session for audit-log API tests."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_audit_log(
    db_session,
    *,
    action: str,
    resource_type: str,
    resource_id,
    trace_id,
    reason: str,
) -> AuditLog:
    """Create one audit record for API filtering tests."""

    audit_log = AuditLog(
        actor_type=AuditActorType.AGENT,
        actor_id=uuid4(),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=AuditResult.PENDING,
        reason=reason,
        before_snapshot={},
        after_snapshot={
            "status": "pending",
        },
        trace_id=trace_id,
        metadata_={
            "source": "pytest",
        },
    )

    db_session.add(audit_log)
    db_session.flush()

    return audit_log


def test_list_audit_logs_returns_records(
    client: TestClient,
    db_session,
) -> None:
    """The audit-log endpoint should return stored audit records."""

    resource_id = uuid4()
    trace_id = uuid4()

    audit_log = _create_audit_log(
        db_session,
        action="create_approval_task",
        resource_type="approval_task",
        resource_id=resource_id,
        trace_id=trace_id,
        reason="Direct refund requires approval.",
    )

    response = client.get("/audit-logs")

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["id"] == str(audit_log.id)
    assert payload[0]["actor_type"] == "agent"
    assert payload[0]["action"] == "create_approval_task"
    assert payload[0]["resource_type"] == "approval_task"
    assert payload[0]["resource_id"] == str(resource_id)
    assert payload[0]["result"] == "pending"
    assert payload[0]["trace_id"] == str(trace_id)
    assert payload[0]["metadata"] == {
        "source": "pytest",
    }


def test_list_audit_logs_filters_by_resource(
    client: TestClient,
    db_session,
) -> None:
    """Audit logs should be filterable by resource type and ID."""

    approval_resource_id = uuid4()
    refund_resource_id = uuid4()
    trace_id = uuid4()

    approval_log = _create_audit_log(
        db_session,
        action="create_approval_task",
        resource_type="approval_task",
        resource_id=approval_resource_id,
        trace_id=trace_id,
        reason="Approval task created.",
    )

    _create_audit_log(
        db_session,
        action="create_refund_request",
        resource_type="refund_request",
        resource_id=refund_resource_id,
        trace_id=uuid4(),
        reason="Refund request created.",
    )

    response = client.get(
        "/audit-logs",
        params={
            "resource_type": "approval_task",
            "resource_id": str(approval_resource_id),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["id"] == str(approval_log.id)
    assert payload[0]["resource_type"] == "approval_task"
    assert payload[0]["resource_id"] == str(
        approval_resource_id,
    )


def test_list_audit_logs_filters_by_trace_id(
    client: TestClient,
    db_session,
) -> None:
    """Trace filtering should return all events in one business flow."""

    trace_id = uuid4()

    first_log = _create_audit_log(
        db_session,
        action="create_approval_task",
        resource_type="approval_task",
        resource_id=uuid4(),
        trace_id=trace_id,
        reason="Approval task created.",
    )

    second_log = _create_audit_log(
        db_session,
        action="approve_approval_task",
        resource_type="approval_task",
        resource_id=first_log.resource_id,
        trace_id=trace_id,
        reason="Approval task approved.",
    )

    _create_audit_log(
        db_session,
        action="create_refund_request",
        resource_type="refund_request",
        resource_id=uuid4(),
        trace_id=uuid4(),
        reason="Unrelated refund request.",
    )

    response = client.get(
        "/audit-logs",
        params={
            "trace_id": str(trace_id),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 2

    actions = {
        item["action"]
        for item in payload
    }

    assert actions == {
        "create_approval_task",
        "approve_approval_task",
    }

    trace_ids = {
        item["trace_id"]
        for item in payload
    }

    assert trace_ids == {
        str(trace_id),
    }

    returned_ids = {
        item["id"]
        for item in payload
    }

    assert returned_ids == {
        str(first_log.id),
        str(second_log.id),
    }


def test_list_audit_logs_filters_by_action(
    client: TestClient,
    db_session,
) -> None:
    """Audit logs should be filterable by action name."""

    approved_log = _create_audit_log(
        db_session,
        action="approve_approval_task",
        resource_type="approval_task",
        resource_id=uuid4(),
        trace_id=uuid4(),
        reason="Task approved.",
    )

    _create_audit_log(
        db_session,
        action="reject_approval_task",
        resource_type="approval_task",
        resource_id=uuid4(),
        trace_id=uuid4(),
        reason="Task rejected.",
    )

    response = client.get(
        "/audit-logs",
        params={
            "action": "approve_approval_task",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["id"] == str(approved_log.id)
    assert payload[0]["action"] == (
        "approve_approval_task"
    )


def test_invalid_uuid_filter_returns_validation_error(
    client: TestClient,
) -> None:
    """Invalid UUID filters should be rejected by FastAPI."""

    response = client.get(
        "/audit-logs",
        params={
            "trace_id": "not-a-uuid",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]