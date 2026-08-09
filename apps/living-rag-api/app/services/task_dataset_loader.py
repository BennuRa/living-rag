"""Load and validate shared Agent evaluation task datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.agent_task_case import (
    AgentTaskCase,
    AgentTaskCategory,
)


class TaskDatasetLoadError(ValueError):
    """Raised when a task dataset cannot be loaded or validated."""


_DATASET_CATEGORIES = (
    "qa",
    "conflict-cases",
    "agent-tasks",
    "fault-injection",
    "adversarial",
)


def _ensure_file(path: Path) -> None:
    """Ensure that the given path points to an existing file."""

    if not path.exists():
        raise TaskDatasetLoadError(f"Task dataset file does not exist: {path}")

    if not path.is_file():
        raise TaskDatasetLoadError(f"Task dataset path is not a file: {path}")


def _ensure_directory(directory: Path) -> None:
    """Ensure that the given path points to an existing directory."""

    if not directory.exists():
        raise TaskDatasetLoadError(f"Task dataset directory does not exist: {directory}")

    if not directory.is_dir():
        raise TaskDatasetLoadError(f"Task dataset path is not a directory: {directory}")


def _validate_task_item(
    raw_task: Any,
    *,
    path: Path,
    location: str,
) -> AgentTaskCase:
    """Convert one decoded JSON value into a validated task case."""

    if not isinstance(raw_task, dict):
        raise TaskDatasetLoadError(f"Task must be a JSON object in {path} at {location}")

    try:
        return AgentTaskCase.model_validate(raw_task)
    except ValidationError as exc:
        raise TaskDatasetLoadError(f"Invalid task in {path} at {location}: {exc}") from exc


def ensure_unique_case_ids(
    task_cases: list[AgentTaskCase],
) -> None:
    """Reject duplicate case IDs in a loaded task collection."""

    seen_ids: set[str] = set()

    for task_case in task_cases:
        if task_case.case_id in seen_ids:
            raise TaskDatasetLoadError(
                f"Duplicate case_id found in task dataset: {task_case.case_id}"
            )

        seen_ids.add(task_case.case_id)


def load_json_task_file(path: Path) -> list[AgentTaskCase]:
    """Load a JSON array containing Agent task cases."""

    _ensure_file(path)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise TaskDatasetLoadError(f"Task dataset file is not valid UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TaskDatasetLoadError(
            f"Invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(payload, list):
        raise TaskDatasetLoadError(f"Task dataset JSON root must be a list: {path}")

    task_cases: list[AgentTaskCase] = []

    for index, raw_task in enumerate(payload, start=1):
        task_cases.append(
            _validate_task_item(
                raw_task,
                path=path,
                location=f"item {index}",
            )
        )

    ensure_unique_case_ids(task_cases)

    return task_cases


def load_jsonl_task_file(path: Path) -> list[AgentTaskCase]:
    """Load a JSONL file containing one Agent task case per line."""

    _ensure_file(path)

    task_cases: list[AgentTaskCase] = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise TaskDatasetLoadError(f"Task dataset file is not valid UTF-8: {path}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        try:
            raw_task = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TaskDatasetLoadError(
                f"Invalid JSONL in {path} at line {line_number}, column {exc.colno}: {exc.msg}"
            ) from exc

        task_cases.append(
            _validate_task_item(
                raw_task,
                path=path,
                location=f"line {line_number}",
            )
        )

    ensure_unique_case_ids(task_cases)

    return task_cases


def load_task_file(path: Path) -> list[AgentTaskCase]:
    """Load a supported JSON or JSONL task file."""

    suffix = path.suffix.lower()

    if suffix == ".json":
        return load_json_task_file(path)

    if suffix == ".jsonl":
        return load_jsonl_task_file(path)

    raise TaskDatasetLoadError(f"Unsupported task dataset file extension: {path}")


def load_task_directory(
    directory: Path,
    category: AgentTaskCategory | None = None,
) -> list[AgentTaskCase]:
    """Load all JSON and JSONL task files in one dataset directory."""

    _ensure_directory(directory)

    dataset_files = sorted(
        [
            *directory.glob("*.json"),
            *directory.glob("*.jsonl"),
        ]
    )

    task_cases: list[AgentTaskCase] = []

    for dataset_file in dataset_files:
        task_cases.extend(load_task_file(dataset_file))

    ensure_unique_case_ids(task_cases)

    if category is not None:
        task_cases = [task_case for task_case in task_cases if task_case.category is category]

    return task_cases


def load_all_task_cases(
    dataset_root: Path,
) -> list[AgentTaskCase]:
    """Load all task cases from the shared dataset categories."""

    _ensure_directory(dataset_root)

    task_cases: list[AgentTaskCase] = []

    for category_name in _DATASET_CATEGORIES:
        category_directory = dataset_root / category_name

        if not category_directory.exists():
            continue

        task_cases.extend(load_task_directory(category_directory))

    ensure_unique_case_ids(task_cases)

    return task_cases
