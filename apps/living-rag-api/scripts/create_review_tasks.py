"""Create review tasks for real open policy conflicts."""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.review_task import ReviewTask
from app.services.review_task_service import (
    create_review_tasks_for_open_conflicts,
)


def main() -> None:
    """Create and persist review tasks for open conflicts."""

    db = SessionLocal()

    try:
        tasks = create_review_tasks_for_open_conflicts(
            db,
        )

        db.commit()

        print(f"created_tasks={len(tasks)}")

        for task in tasks:
            print(
                f"task_id={task.id} "
                f"conflict_id={task.conflict_id} "
                f"task_type={task.task_type} "
                f"status={task.status}"
            )

        total_statement = select(ReviewTask)
        total_tasks = db.scalars(total_statement).all()

        print(f"total_review_tasks={len(total_tasks)}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()