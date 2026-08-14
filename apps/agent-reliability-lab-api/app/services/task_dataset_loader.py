from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.agent_task_case import AgentTaskCase


def shared_agent_task_dataset_dir() -> Path:
    """Return the Monorepo directory containing shared Agent task JSONL files."""

    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "shared" / "datasets" / "agent-tasks"


def load_agent_task_cases(dataset_dir: Path) -> list[AgentTaskCase]:
    """Load and validate all JSONL task cases from one dataset directory."""

    if not dataset_dir.is_dir():
        raise ValueError(
            f"Agent task dataset directory does not exist: {dataset_dir}"
        )

    cases: list[AgentTaskCase] = []
    known_case_ids: set[str] = set()

    for dataset_file in sorted(dataset_dir.glob("*.jsonl")):
        with dataset_file.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                content = line.strip()
                if not content:
                    continue

                try:
                    payload = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON in {dataset_file.name} "
                        f"at line {line_number}"
                    ) from exc

                try:
                    task_case = AgentTaskCase.model_validate(payload)
                except ValidationError as exc:
                    raise ValueError(
                        f"Invalid task case in {dataset_file.name} "
                        f"at line {line_number}: {exc}"
                    ) from exc

                if task_case.case_id in known_case_ids:
                    raise ValueError(
                        f"Duplicate Agent task case_id: {task_case.case_id!r}"
                    )

                known_case_ids.add(task_case.case_id)
                cases.append(task_case)

    if not cases:
        raise ValueError(
            f"No Agent task cases found in dataset directory: {dataset_dir}"
        )

    return cases


def load_shared_agent_task_cases() -> list[AgentTaskCase]:
    """Load the Monorepo's shared Agent task dataset."""

    return load_agent_task_cases(shared_agent_task_dataset_dir())