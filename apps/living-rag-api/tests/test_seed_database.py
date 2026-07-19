"""Tests for the idempotent CSV business-data seed script."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.membership_account import MembershipAccount
from app.models.order import Order
from app.models.refund_request import RefundRequest
from app.models.user import User


API_ROOT = Path(__file__).resolve().parents[1]
SEED_SCRIPT_PATH = API_ROOT / "scripts" / "seed_database.py"


def _load_seed_module() -> ModuleType:
    """Load the script as a testable module without executing its main function."""

    module_spec = importlib.util.spec_from_file_location(
        "seed_database_for_tests",
        SEED_SCRIPT_PATH,
    )
    assert module_spec is not None
    assert module_spec.loader is not None

    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module


def _write_csv(
    directory: Path,
    file_name: str,
    field_names: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    """Write one UTF-8 CSV fixture with deterministic field ordering."""

    with (directory / file_name).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(rows)


def _write_valid_seed_files(directory: Path, module: ModuleType) -> None:
    """Create one valid User → MembershipAccount → Order → RefundRequest dataset."""

    metadata_json = json.dumps({"source": "pytest"}, ensure_ascii=False)

    _write_csv(
        directory,
        module.USERS_CSV,
        module.USERS_FIELDS,
        [
            {
                "external_id": "TEST-USER-001",
                "email": "test-user@example.com",
                "display_name": "测试用户",
                "status": "active",
                "metadata_json": metadata_json,
            }
        ],
    )
    _write_csv(
        directory,
        module.MEMBERSHIP_ACCOUNTS_CSV,
        module.MEMBERSHIP_ACCOUNT_FIELDS,
        [
            {
                "user_external_id": "TEST-USER-001",
                "membership_number": "TEST-MEMBER-001",
                "tier": "gold",
                "status": "active",
                "points": "100",
                "started_at": "2026-01-01T00:00:00+08:00",
                "expires_at": "2027-01-01T00:00:00+08:00",
                "metadata_json": metadata_json,
            }
        ],
    )
    _write_csv(
        directory,
        module.ORDERS_CSV,
        module.ORDER_FIELDS,
        [
            {
                "membership_number": "TEST-MEMBER-001",
                "order_number": "TEST-ORDER-001",
                "status": "completed",
                "total_amount": "199.00",
                "currency": "CNY",
                "ordered_at": "2026-01-02T10:00:00+08:00",
                "paid_at": "2026-01-02T10:01:00+08:00",
                "completed_at": "2026-01-05T10:00:00+08:00",
                "metadata_json": metadata_json,
            }
        ],
    )
    _write_csv(
        directory,
        module.REFUND_REQUESTS_CSV,
        module.REFUND_REQUEST_FIELDS,
        [
            {
                "order_number": "TEST-ORDER-001",
                "request_number": "TEST-REFUND-001",
                "status": "approved",
                "requested_amount": "199.00",
                "approved_amount": "199.00",
                "reason": "测试退款申请",
                "rejection_reason": "",
                "requested_at": "2026-01-06T10:00:00+08:00",
                "reviewed_at": "2026-01-06T11:00:00+08:00",
                "completed_at": "",
                "metadata_json": metadata_json,
            }
        ],
    )


def _seed_rows(
    module: ModuleType,
    db_session: Session,
) -> tuple[object, object, object, object]:
    """Run the script's four seed stages using the rollback-only test session."""

    users, memberships, orders, refunds = module.load_and_validate_input()

    user_stats = module.seed_users(db_session, users)
    membership_stats = module.seed_membership_accounts(db_session, memberships)
    order_stats = module.seed_orders(db_session, orders)
    refund_stats = module.seed_refund_requests(db_session, refunds)

    return user_stats, membership_stats, order_stats, refund_stats


def test_reject_unknown_membership_reference_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An order with an unknown membership number is rejected before DB access."""

    module = _load_seed_module()
    _write_valid_seed_files(tmp_path, module)
    monkeypatch.setattr(module, "DATA_DIRECTORY", tmp_path)

    orders_path = tmp_path / module.ORDERS_CSV
    content = orders_path.read_text(encoding="utf-8")
    orders_path.write_text(
        content.replace("TEST-MEMBER-001", "UNKNOWN-MEMBER-001"),
        encoding="utf-8",
    )

    with pytest.raises(module.SeedDataError, match="unknown membership number"):
        module.load_and_validate_input()


def test_seed_business_rows_is_idempotent(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running identical seed data twice creates no duplicate business records."""

    module = _load_seed_module()
    _write_valid_seed_files(tmp_path, module)
    monkeypatch.setattr(module, "DATA_DIRECTORY", tmp_path)

    first_stats = _seed_rows(module, db_session)

    assert first_stats[0].created == 1
    assert first_stats[1].created == 1
    assert first_stats[2].created == 1
    assert first_stats[3].created == 1

    second_stats = _seed_rows(module, db_session)

    assert second_stats[0].created == 0
    assert second_stats[1].created == 0
    assert second_stats[2].created == 0
    assert second_stats[3].created == 0

    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert db_session.scalar(select(func.count()).select_from(MembershipAccount)) == 1
    assert db_session.scalar(select(func.count()).select_from(Order)) == 1
    assert db_session.scalar(select(func.count()).select_from(RefundRequest)) == 1

    order = db_session.scalar(select(Order).where(Order.order_number == "TEST-ORDER-001"))
    refund_request = db_session.scalar(
        select(RefundRequest).where(
            RefundRequest.request_number == "TEST-REFUND-001"
        )
    )

    assert order is not None
    assert refund_request is not None
    assert order.total_amount == Decimal("199.00")
    assert refund_request.approved_amount == Decimal("199.00")