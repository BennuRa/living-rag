"""Read-only sample-user lookup for the demo web application."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserStatus


class UserSummary(BaseModel):
    """Safe user fields needed by the demo selector."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    display_name: str


router = APIRouter(
    prefix="/api/users",
    tags=["users"],
)


@router.get("", response_model=list[UserSummary])
def list_active_users(
    db: Session = Depends(get_db),
) -> list[User]:
    """List active synthetic users for the demo UI."""

    return list(
        db.scalars(
            select(User)
            .where(User.status == UserStatus.ACTIVE)
            .order_by(User.external_id)
        ).all()
    )
