"""Seed the Living RAG development database from versioned CSV sample data.

The script is intentionally idempotent:
- users are matched by external_id;
- membership accounts are matched by membership_number;
- orders are matched by order_number;
- refund requests are matched by request_number.

Run inside the API container:

    python scripts/seed_database.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal
from app.models.membership_account import (
    MembershipAccount,
    MembershipAccountStatus,
    MembershipTier,
)
from app.models.order import Order, OrderStatus
from app.models.refund_request import RefundRequest, RefundRequestStatus
from app.models.user import User, UserStatus


DATA_DIRECTORY = Path("/data/sample_documents")

USERS_CSV = "users.csv"
MEMBERSHIP_ACCOUNTS_CSV = "membership_accounts.csv"
ORDERS_CSV = "orders.csv"
REFUND_REQUESTS_CSV = "refund_requests.csv"

USERS_FIELDS = (
    "external_id",
    "email",
    "display_name",
    "status",
    "metadata_json",
)

MEMBERSHIP_ACCOUNT_FIELDS = (
    "user_external_id",
    "membership_number",
    "tier",
    "status",
    "points",
    "started_at",
    "expires_at",
    "metadata_json",
)

ORDER_FIELDS = (
    "membership_number",
    "order_number",
    "status",
    "total_amount",
    "currency",
    "ordered_at",
    "paid_at",
    "completed_at",
    "metadata_json",
)

REFUND_REQUEST_FIELDS = (
    "order_number",
    "request_number",
    "status",
    "requested_amount",
    "approved_amount",
    "reason",
    "rejection_reason",
    "requested_at",
    "reviewed_at",
    "completed_at",
    "metadata_json",
)

EnumType = TypeVar("EnumType")


class SeedDataError(ValueError):
    """Raised when a CSV file does not satisfy the seed data contract."""


@dataclass
class SeedStats:
    """Count created and matched records for one database table."""

    created: int = 0
    updated: int = 0


def fail(source: str, message: str) -> SeedDataError:
    """Build a consistent CSV validation error."""

    return SeedDataError(f"{source}: {message}")


def require_value(value: str | None, source: str, field_name: str) -> str:
    """Return a non-empty CSV value or raise a descriptive error."""

    if value is None or not value.strip():
        raise fail(source, f"field '{field_name}' is required")

    return value.strip()


def optional_value(value: str | None) -> str | None:
    """Convert an empty CSV cell to None."""

    if value is None:
        return None

    stripped_value = value.strip()
    return stripped_value or None


def parse_datetime(value: str | None, source: str, field_name: str) -> datetime:
    """Parse one required timezone-aware ISO 8601 datetime."""

    raw_value = require_value(value, source, field_name)

    try:
        parsed_value = datetime.fromisoformat(raw_value)
    except ValueError as error:
        raise fail(
            source,
            f"field '{field_name}' must be a valid ISO 8601 datetime: {raw_value!r}",
        ) from error

    if parsed_value.tzinfo is None:
        raise fail(
            source,
            f"field '{field_name}' must include a timezone offset: {raw_value!r}",
        )

    return parsed_value


def parse_optional_datetime(
    value: str | None,
    source: str,
    field_name: str,
) -> datetime | None:
    """Parse an optional timezone-aware ISO 8601 datetime."""

    if optional_value(value) is None:
        return None

    return parse_datetime(value, source, field_name)


def parse_decimal(
    value: str | None,
    source: str,
    field_name: str,
    *,
    allow_zero: bool,
) -> Decimal:
    """Parse a Decimal and enforce the model's positive/non-negative constraint."""

    raw_value = require_value(value, source, field_name)

    try:
        parsed_value = Decimal(raw_value)
    except InvalidOperation as error:
        raise fail(
            source,
            f"field '{field_name}' must be a decimal number: {raw_value!r}",
        ) from error

    if allow_zero and parsed_value < 0:
        raise fail(source, f"field '{field_name}' must be greater than or equal to zero")

    if not allow_zero and parsed_value <= 0:
        raise fail(source, f"field '{field_name}' must be greater than zero")

    return parsed_value


def parse_optional_decimal(
    value: str | None,
    source: str,
    field_name: str,
) -> Decimal | None:
    """Parse an optional strictly positive Decimal."""

    if optional_value(value) is None:
        return None

    return parse_decimal(value, source, field_name, allow_zero=False)


def parse_non_negative_integer(
    value: str | None,
    source: str,
    field_name: str,
) -> int:
    """Parse an integer and enforce points >= 0."""

    raw_value = require_value(value, source, field_name)

    try:
        parsed_value = int(raw_value)
    except ValueError as error:
        raise fail(
            source,
            f"field '{field_name}' must be an integer: {raw_value!r}",
        ) from error

    if parsed_value < 0:
        raise fail(source, f"field '{field_name}' must be greater than or equal to zero")

    return parsed_value


def parse_metadata(value: str | None, source: str) -> dict[str, object]:
    """Parse a JSON object for a JSONB metadata column."""

    raw_value = require_value(value, source, "metadata_json")

    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise fail(source, f"field 'metadata_json' is not valid JSON: {error.msg}") from error

    if not isinstance(parsed_value, dict):
        raise fail(source, "field 'metadata_json' must contain a JSON object")

    return parsed_value


def parse_enum(
    enum_class: type[EnumType],
    value: str | None,
    source: str,
    field_name: str,
) -> EnumType:
    """Parse a CSV value into one of the ORM StrEnum members."""

    raw_value = require_value(value, source, field_name)

    try:
        return enum_class(raw_value)
    except ValueError as error:
        allowed_values = ", ".join(member.value for member in enum_class)
        raise fail(
            source,
            f"field '{field_name}' has invalid value {raw_value!r}; "
            f"allowed values: {allowed_values}",
        ) from error


def read_csv_rows(file_name: str, expected_fields: Sequence[str]) -> list[dict[str, str]]:
    """Read one CSV file and enforce its exact header contract."""

    file_path = DATA_DIRECTORY / file_name

    if not file_path.is_file():
        raise SeedDataError(f"Required CSV file was not found: {file_path}")

    with file_path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        actual_fields = tuple(reader.fieldnames or ())

        if actual_fields != tuple(expected_fields):
            raise SeedDataError(
                f"{file_path}: unexpected CSV header. "
                f"Expected {list(expected_fields)!r}, got {list(actual_fields)!r}"
            )

        rows = list(reader)

    if not rows:
        raise SeedDataError(f"{file_path}: CSV file must contain at least one data row")

    return rows


def ensure_unique_values(
    rows: Iterable[dict[str, str]],
    *,
    field_name: str,
    file_name: str,
) -> None:
    """Reject duplicate natural keys within one input CSV."""

    seen_values: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        source = f"{file_name} row {row_number}"
        value = require_value(row.get(field_name), source, field_name)

        if value in seen_values:
            raise fail(source, f"duplicate value for unique field '{field_name}': {value!r}")

        seen_values.add(value)


def ensure_references_exist(
    rows: Iterable[dict[str, str]],
    *,
    foreign_key_field: str,
    known_values: set[str],
    file_name: str,
    target_name: str,
) -> None:
    """Validate business-key references before the database transaction begins."""

    for row_number, row in enumerate(rows, start=2):
        source = f"{file_name} row {row_number}"
        value = require_value(row.get(foreign_key_field), source, foreign_key_field)

        if value not in known_values:
            raise fail(
                source,
                f"field '{foreign_key_field}' references unknown {target_name}: {value!r}",
            )


def validate_csv_contracts(
    users_rows: list[dict[str, str]],
    membership_rows: list[dict[str, str]],
    order_rows: list[dict[str, str]],
    refund_rows: list[dict[str, str]],
) -> None:
    """Validate CSV-level uniqueness, references, types and enum values."""

    ensure_unique_values(users_rows, field_name="external_id", file_name=USERS_CSV)
    ensure_unique_values(
        membership_rows,
        field_name="membership_number",
        file_name=MEMBERSHIP_ACCOUNTS_CSV,
    )
    ensure_unique_values(order_rows, field_name="order_number", file_name=ORDERS_CSV)
    ensure_unique_values(
        refund_rows,
        field_name="request_number",
        file_name=REFUND_REQUESTS_CSV,
    )

    user_external_ids = {
        require_value(row.get("external_id"), USERS_CSV, "external_id") for row in users_rows
    }
    membership_numbers = {
        require_value(
            row.get("membership_number"),
            MEMBERSHIP_ACCOUNTS_CSV,
            "membership_number",
        )
        for row in membership_rows
    }
    order_numbers = {
        require_value(row.get("order_number"), ORDERS_CSV, "order_number") for row in order_rows
    }

    ensure_references_exist(
        membership_rows,
        foreign_key_field="user_external_id",
        known_values=user_external_ids,
        file_name=MEMBERSHIP_ACCOUNTS_CSV,
        target_name="user external_id",
    )
    ensure_references_exist(
        order_rows,
        foreign_key_field="membership_number",
        known_values=membership_numbers,
        file_name=ORDERS_CSV,
        target_name="membership number",
    )
    ensure_references_exist(
        refund_rows,
        foreign_key_field="order_number",
        known_values=order_numbers,
        file_name=REFUND_REQUESTS_CSV,
        target_name="order number",
    )

    for row_number, row in enumerate(users_rows, start=2):
        source = f"{USERS_CSV} row {row_number}"
        require_value(row.get("external_id"), source, "external_id")
        require_value(row.get("display_name"), source, "display_name")
        parse_enum(UserStatus, row.get("status"), source, "status")
        parse_metadata(row.get("metadata_json"), source)

    for row_number, row in enumerate(membership_rows, start=2):
        source = f"{MEMBERSHIP_ACCOUNTS_CSV} row {row_number}"
        parse_enum(MembershipTier, row.get("tier"), source, "tier")
        parse_enum(MembershipAccountStatus, row.get("status"), source, "status")
        parse_non_negative_integer(row.get("points"), source, "points")
        parse_datetime(row.get("started_at"), source, "started_at")
        parse_optional_datetime(row.get("expires_at"), source, "expires_at")
        parse_metadata(row.get("metadata_json"), source)

    for row_number, row in enumerate(order_rows, start=2):
        source = f"{ORDERS_CSV} row {row_number}"
        parse_enum(OrderStatus, row.get("status"), source, "status")
        parse_decimal(row.get("total_amount"), source, "total_amount", allow_zero=True)
        currency = require_value(row.get("currency"), source, "currency")

        if len(currency) != 3:
            raise fail(source, "field 'currency' must contain exactly three characters")

        parse_datetime(row.get("ordered_at"), source, "ordered_at")
        parse_optional_datetime(row.get("paid_at"), source, "paid_at")
        parse_optional_datetime(row.get("completed_at"), source, "completed_at")
        parse_metadata(row.get("metadata_json"), source)

    for row_number, row in enumerate(refund_rows, start=2):
        source = f"{REFUND_REQUESTS_CSV} row {row_number}"
        requested_amount = parse_decimal(
            row.get("requested_amount"),
            source,
            "requested_amount",
            allow_zero=False,
        )
        approved_amount = parse_optional_decimal(
            row.get("approved_amount"),
            source,
            "approved_amount",
        )

        if approved_amount is not None and approved_amount > requested_amount:
            raise fail(
                source,
                "field 'approved_amount' must not be greater than 'requested_amount'",
            )

        parse_enum(RefundRequestStatus, row.get("status"), source, "status")
        require_value(row.get("reason"), source, "reason")
        parse_datetime(row.get("requested_at"), source, "requested_at")
        parse_optional_datetime(row.get("reviewed_at"), source, "reviewed_at")
        parse_optional_datetime(row.get("completed_at"), source, "completed_at")
        parse_metadata(row.get("metadata_json"), source)


def seed_users(session: Session, rows: Iterable[dict[str, str]]) -> SeedStats:
    """Create or synchronize User records by external_id."""

    stats = SeedStats()

    for row in rows:
        external_id = row["external_id"]
        user = session.scalar(select(User).where(User.external_id == external_id))

        if user is None:
            user = User(external_id=external_id, display_name=row["display_name"])
            session.add(user)
            stats.created += 1
        else:
            stats.updated += 1

        user.email = optional_value(row.get("email"))
        user.display_name = row["display_name"].strip()
        user.status = UserStatus(row["status"].strip())
        user.metadata_ = parse_metadata(row.get("metadata_json"), f"{USERS_CSV} {external_id}")

    session.flush()
    return stats


def seed_membership_accounts(
    session: Session,
    rows: Iterable[dict[str, str]],
) -> SeedStats:
    """Create or synchronize MembershipAccount records by membership_number."""

    stats = SeedStats()

    for row in rows:
        membership_number = row["membership_number"]
        source = f"{MEMBERSHIP_ACCOUNTS_CSV} {membership_number}"
        user = session.scalar(
            select(User).where(User.external_id == row["user_external_id"].strip())
        )

        if user is None:
            raise SeedDataError(
                f"{source}: referenced user was not found in the database: "
                f"{row['user_external_id']!r}"
            )

        membership_account = session.scalar(
            select(MembershipAccount).where(
                MembershipAccount.membership_number == membership_number
            )
        )

        if membership_account is None:
            membership_account = MembershipAccount(
                user_id=user.id,
                membership_number=membership_number,
                tier=MembershipTier.STANDARD,
                status=MembershipAccountStatus.ACTIVE,
                points=0,
                started_at=parse_datetime(row.get("started_at"), source, "started_at"),
            )
            session.add(membership_account)
            stats.created += 1
        else:
            stats.updated += 1

        membership_account.user_id = user.id
        membership_account.tier = MembershipTier(row["tier"].strip())
        membership_account.status = MembershipAccountStatus(row["status"].strip())
        membership_account.points = parse_non_negative_integer(row.get("points"), source, "points")
        membership_account.started_at = parse_datetime(row.get("started_at"), source, "started_at")
        membership_account.expires_at = parse_optional_datetime(
            row.get("expires_at"),
            source,
            "expires_at",
        )
        membership_account.metadata_ = parse_metadata(row.get("metadata_json"), source)

    session.flush()
    return stats


def seed_orders(session: Session, rows: Iterable[dict[str, str]]) -> SeedStats:
    """Create or synchronize Order records by order_number."""

    stats = SeedStats()

    for row in rows:
        order_number = row["order_number"]
        source = f"{ORDERS_CSV} {order_number}"
        membership_account = session.scalar(
            select(MembershipAccount).where(
                MembershipAccount.membership_number == row["membership_number"].strip()
            )
        )

        if membership_account is None:
            raise SeedDataError(
                f"{source}: referenced membership account was not found in the database: "
                f"{row['membership_number']!r}"
            )

        order = session.scalar(select(Order).where(Order.order_number == order_number))

        if order is None:
            order = Order(
                membership_account_id=membership_account.id,
                order_number=order_number,
                status=OrderStatus.PENDING,
                total_amount=Decimal("0"),
                currency="CNY",
                ordered_at=parse_datetime(row.get("ordered_at"), source, "ordered_at"),
            )
            session.add(order)
            stats.created += 1
        else:
            stats.updated += 1

        order.membership_account_id = membership_account.id
        order.status = OrderStatus(row["status"].strip())
        order.total_amount = parse_decimal(
            row.get("total_amount"),
            source,
            "total_amount",
            allow_zero=True,
        )
        order.currency = row["currency"].strip()
        order.ordered_at = parse_datetime(row.get("ordered_at"), source, "ordered_at")
        order.paid_at = parse_optional_datetime(row.get("paid_at"), source, "paid_at")
        order.completed_at = parse_optional_datetime(
            row.get("completed_at"),
            source,
            "completed_at",
        )
        order.metadata_ = parse_metadata(row.get("metadata_json"), source)

    session.flush()
    return stats


def seed_refund_requests(session: Session, rows: Iterable[dict[str, str]]) -> SeedStats:
    """Create or synchronize RefundRequest records by request_number."""

    stats = SeedStats()

    for row in rows:
        request_number = row["request_number"]
        source = f"{REFUND_REQUESTS_CSV} {request_number}"
        order = session.scalar(select(Order).where(Order.order_number == row["order_number"].strip()))

        if order is None:
            raise SeedDataError(
                f"{source}: referenced order was not found in the database: "
                f"{row['order_number']!r}"
            )

        refund_request = session.scalar(
            select(RefundRequest).where(RefundRequest.request_number == request_number)
        )

        if refund_request is None:
            refund_request = RefundRequest(
                order_id=order.id,
                request_number=request_number,
                status=RefundRequestStatus.PENDING,
                requested_amount=Decimal("0.01"),
                reason="Seed placeholder",
                requested_at=parse_datetime(
                    row.get("requested_at"),
                    source,
                    "requested_at",
                ),
            )
            session.add(refund_request)
            stats.created += 1
        else:
            stats.updated += 1

        requested_amount = parse_decimal(
            row.get("requested_amount"),
            source,
            "requested_amount",
            allow_zero=False,
        )
        approved_amount = parse_optional_decimal(
            row.get("approved_amount"),
            source,
            "approved_amount",
        )

        if approved_amount is not None and approved_amount > requested_amount:
            raise SeedDataError(
                f"{source}: approved_amount must not be greater than requested_amount"
            )

        refund_request.order_id = order.id
        refund_request.status = RefundRequestStatus(row["status"].strip())
        refund_request.requested_amount = requested_amount
        refund_request.approved_amount = approved_amount
        refund_request.reason = row["reason"].strip()
        refund_request.rejection_reason = optional_value(row.get("rejection_reason"))
        refund_request.requested_at = parse_datetime(
            row.get("requested_at"),
            source,
            "requested_at",
        )
        refund_request.reviewed_at = parse_optional_datetime(
            row.get("reviewed_at"),
            source,
            "reviewed_at",
        )
        refund_request.completed_at = parse_optional_datetime(
            row.get("completed_at"),
            source,
            "completed_at",
        )
        refund_request.metadata_ = parse_metadata(row.get("metadata_json"), source)

    session.flush()
    return stats


def load_and_validate_input() -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Load all CSV files and validate their cross-file contract before writing."""

    users_rows = read_csv_rows(USERS_CSV, USERS_FIELDS)
    membership_rows = read_csv_rows(MEMBERSHIP_ACCOUNTS_CSV, MEMBERSHIP_ACCOUNT_FIELDS)
    order_rows = read_csv_rows(ORDERS_CSV, ORDER_FIELDS)
    refund_rows = read_csv_rows(REFUND_REQUESTS_CSV, REFUND_REQUEST_FIELDS)

    validate_csv_contracts(users_rows, membership_rows, order_rows, refund_rows)

    return users_rows, membership_rows, order_rows, refund_rows


def print_stats(table_name: str, stats: SeedStats) -> None:
    """Print one stable, human-readable seed result line."""

    print(f"{table_name}: created={stats.created}, updated={stats.updated}")


def main() -> None:
    """Load sample CSV files and write them in one atomic database transaction."""

    print(f"Reading CSV seed data from: {DATA_DIRECTORY}")

    users_rows, membership_rows, order_rows, refund_rows = load_and_validate_input()

    try:
        with SessionLocal() as session:
            with session.begin():
                user_stats = seed_users(session, users_rows)
                membership_stats = seed_membership_accounts(session, membership_rows)
                order_stats = seed_orders(session, order_rows)
                refund_stats = seed_refund_requests(session, refund_rows)
    except Exception:
        print("Seed failed. The database transaction was rolled back.", file=sys.stderr)
        raise

    print("Seed completed successfully.")
    print_stats("users", user_stats)
    print_stats("membership_accounts", membership_stats)
    print_stats("orders", order_stats)
    print_stats("refund_requests", refund_stats)


if __name__ == "__main__":
    main()